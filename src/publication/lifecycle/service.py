from __future__ import annotations
from dataclasses import dataclass
from types import SimpleNamespace
from src.publication.repository import CurrentReportPointer, ChannelPointer, PublicationHistoryRecord

@dataclass(frozen=True)
class LifecycleResult:
    status:str
    reason_code:str|None=None

class ControlledPublicationLifecycle:
    """Explicit pointer lifecycle operations. Caller owns transaction boundaries."""
    def __init__(self,*,repository,guard_engine=None,freshness_checker=None,freeze_repository=None,cache_events=None,history_service=None):
        self.repo=repository; self.guard=guard_engine; self.fresh=freshness_checker
        self.freezes=freeze_repository; self.cache=cache_events; self.history=history_service

    def _lock_and_freeze(self,cursor,property_id,variant,channel):
        self.repo.lock_target(cursor,property_id,variant,channel)
        if self.freezes:
            active=self.freezes.active(cursor,property_id,variant,channel)
            if active: return LifecycleResult('FROZEN',active[1])
        return None
    def _emit(self,cursor,property_id,variant,channel,reason,actor,correlation_id=None):
        if self.cache: self.cache.emit(cursor,property_id=property_id,report_variant=variant,channel=channel,reason_code=reason,actor=actor,correlation_id=correlation_id)

    def promote_render(self,cursor,*,stage,report,render,actor='PUBLICATION_SERVICE'):
        blocked=self._lock_and_freeze(cursor,stage.property_id,stage.report_variant,stage.channel)
        if blocked:return blocked
        current=self.repo.get_current_report(cursor,stage.property_id,stage.report_variant)
        if current is None or current[0] != report.report_id: return LifecycleResult('BLOCKED','SEMANTIC_CURRENT_REPORT_MISMATCH')
        if self.guard:
            g=self.guard.evaluate(stage=stage,report=report,render=render)
            if not g.allowed:return LifecycleResult('BLOCKED',g.reasons[0])
        if self.fresh:
            f=self.fresh.check(cursor,report=report)
            if f.status!='FRESH':return LifecycleResult(f.status,f.reason_code)
        prior=self.repo.get_channel_pointer(cursor,stage.property_id,stage.report_variant,stage.channel)
        if prior and prior[1]==render.render_id:return LifecycleResult('NO_OP')
        if self.history and prior:
            self.history.record_pointer_replacement(cursor,property_id=stage.property_id,report_variant=stage.report_variant,channel=stage.channel,
                previous_report_id=prior[0],previous_render_id=prior[1],new_report_id=report.report_id,new_render_id=render.render_id,
                actor=actor,reason_code='PRESENTATION_ONLY_PROMOTION',correlation_id=getattr(stage,'correlation_id',None))
        self.repo.set_channel_pointer(cursor,ChannelPointer(stage.property_id,stage.report_variant,stage.channel,report.report_id,render.render_id,updated_by=actor))
        self.repo.append_history(cursor,PublicationHistoryRecord(stage.property_id,stage.report_variant,report.report_id,'RENDER_PROMOTED',actor,stage.channel,render.render_id,'PRESENTATION_ONLY_PROMOTION',getattr(stage,'correlation_id',None)))
        self._emit(cursor,stage.property_id,stage.report_variant,stage.channel,'RENDER_PROMOTED',actor,getattr(stage,'correlation_id',None))
        return LifecycleResult('PROMOTED')

    def unpublish(self,cursor,*,property_id,report_variant,channel,actor='PUBLICATION_SERVICE',reason_code='MANUAL_UNPUBLISH',correlation_id=None):
        blocked=self._lock_and_freeze(cursor,property_id,report_variant,channel)
        if blocked:return blocked
        prior=self.repo.get_channel_pointer(cursor,property_id,report_variant,channel)
        if prior is None:return LifecycleResult('NO_OP')
        self.repo.clear_channel_pointer(cursor,property_id,report_variant,channel)
        self.repo.append_history(cursor,PublicationHistoryRecord(property_id,report_variant,prior[0],'UNPUBLISHED',actor,channel,prior[1],reason_code,correlation_id))
        self._emit(cursor,property_id,report_variant,channel,'UNPUBLISHED',actor,correlation_id)
        return LifecycleResult('UNPUBLISHED')

    def republish(self,cursor,*,stage,report,render,actor='PUBLICATION_SERVICE'):
        result=self.promote_render(cursor,stage=stage,report=report,render=render,actor=actor)
        if result.status=='PROMOTED':
            self.repo.append_history(cursor,PublicationHistoryRecord(stage.property_id,stage.report_variant,report.report_id,'REPUBLISHED',actor,stage.channel,render.render_id,'REPUBLISH',getattr(stage,'correlation_id',None)))
            return LifecycleResult('REPUBLISHED')
        return result

    def rollback(self,cursor,*,stage,report,render,actor='PUBLICATION_SERVICE'):
        blocked=self._lock_and_freeze(cursor,stage.property_id,stage.report_variant,stage.channel)
        if blocked:return blocked
        if not self.repo.was_previously_published(cursor,stage.property_id,stage.report_variant,stage.channel,stage.report_id,stage.render_id):
            return LifecycleResult('BLOCKED','ROLLBACK_TARGET_NOT_IN_PUBLICATION_HISTORY')
        if self.guard:
            g=self.guard.evaluate(stage=stage,report=report,render=render)
            if not g.allowed:return LifecycleResult('BLOCKED',g.reasons[0])
        if self.fresh:
            f=self.fresh.check(cursor,report=report)
            if f.status!='FRESH':return LifecycleResult(f.status,f.reason_code)
        prior=self.repo.get_channel_pointer(cursor,stage.property_id,stage.report_variant,stage.channel)
        self.repo.set_current_report(cursor,CurrentReportPointer(stage.property_id,stage.report_variant,stage.report_id,updated_by=actor))
        self.repo.set_channel_pointer(cursor,ChannelPointer(stage.property_id,stage.report_variant,stage.channel,stage.report_id,stage.render_id,updated_by=actor))
        self.repo.append_history(cursor,PublicationHistoryRecord(stage.property_id,stage.report_variant,stage.report_id,'ROLLED_BACK',actor,stage.channel,stage.render_id,'ROLLBACK',getattr(stage,'correlation_id',None)))
        self._emit(cursor,stage.property_id,stage.report_variant,stage.channel,'ROLLED_BACK',actor,getattr(stage,'correlation_id',None))
        return LifecycleResult('ROLLED_BACK')

    def invalidate(self,cursor,*,property_id,report_variant,report_id,actor='PUBLICATION_SERVICE',reason_code='REPORT_INVALIDATED',correlation_id=None):
        # Serialize across all channels using semantic lock key.
        self.repo.lock_semantic_target(cursor,property_id,report_variant)
        channels=self.repo.list_channel_pointers_for_report(cursor,property_id,report_variant,report_id)
        for channel,render_id in channels:
            self.repo.clear_channel_pointer(cursor,property_id,report_variant,channel)
            self.repo.append_history(cursor,PublicationHistoryRecord(property_id,report_variant,report_id,'INVALIDATED',actor,channel,render_id,reason_code,correlation_id))
            self._emit(cursor,property_id,report_variant,channel,'INVALIDATED',actor,correlation_id)
        current=self.repo.get_current_report(cursor,property_id,report_variant)
        if current and current[0]==report_id:self.repo.clear_current_report(cursor,property_id,report_variant)
        return LifecycleResult('INVALIDATED' if channels or (current and current[0]==report_id) else 'NO_OP')

    def withdraw(self,cursor,*,property_id,report_variant,actor='PUBLICATION_SERVICE',reason_code='WITHDRAWN',correlation_id=None):
        self.repo.lock_semantic_target(cursor,property_id,report_variant)
        current=self.repo.get_current_report(cursor,property_id,report_variant)
        if current is None:return LifecycleResult('NO_OP')
        report_id=current[0]
        channels=self.repo.list_channel_pointers_for_report(cursor,property_id,report_variant,report_id)
        for channel,render_id in channels:
            self.repo.clear_channel_pointer(cursor,property_id,report_variant,channel)
            self.repo.append_history(cursor,PublicationHistoryRecord(property_id,report_variant,report_id,'WITHDRAWN',actor,channel,render_id,reason_code,correlation_id))
            self._emit(cursor,property_id,report_variant,channel,'WITHDRAWN',actor,correlation_id)
        self.repo.clear_current_report(cursor,property_id,report_variant)
        self.repo.append_history(cursor,PublicationHistoryRecord(property_id,report_variant,report_id,'SEMANTIC_WITHDRAWN',actor,None,None,reason_code,correlation_id))
        return LifecycleResult('WITHDRAWN')
