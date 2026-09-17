from __future__ import annotations
from dataclasses import dataclass
from src.publication.repository import CurrentReportPointer, ChannelPointer, PublicationHistoryRecord

@dataclass(frozen=True)
class PublicationResult:
    status: str  # PUBLISHED | BLOCKED | STALE
    reason_codes: tuple[str,...] = ()

class AtomicPublicationService:
    """Validates then atomically swaps explicit pointers in the caller transaction.

    No commit/rollback is performed here. Any database exception propagates so the
    caller can rollback, preserving previously current pointers.
    """
    def __init__(self,*,staging_repository,publication_repository,guard_engine,freshness_checker,freeze_repository=None,history_service=None,cache_events=None):
        self.staging_repository=staging_repository
        self.publication_repository=publication_repository
        self.guard_engine=guard_engine
        self.freshness_checker=freshness_checker
        self.freeze_repository=freeze_repository
        self.history_service=history_service
        self.cache_events=cache_events

    def publish(self,cursor,*,stage,report,render,actor='PUBLICATION_SERVICE')->PublicationResult:
        # Serialize all attempts for the same delivery target before final checks.
        self.publication_repository.lock_target(cursor,stage.property_id,stage.report_variant,stage.channel)
        if self.freeze_repository is not None:
            active=self.freeze_repository.active(cursor,stage.property_id,stage.report_variant,stage.channel)
            if active:
                self.staging_repository.transition(cursor,stage.staging_id,from_state=stage.staging_state,to_state='BLOCKED',reason_code=active[1])
                return PublicationResult('BLOCKED',(active[1],))
        guard=self.guard_engine.evaluate(stage=stage,report=report,render=render)
        if not guard.allowed:
            self.staging_repository.transition(cursor,stage.staging_id,from_state=stage.staging_state,to_state='BLOCKED',reason_code=guard.reasons[0])
            return PublicationResult('BLOCKED',guard.reasons)
        fresh=self.freshness_checker.check(cursor,report=report)
        if fresh.status!='FRESH':
            terminal='STALE' if fresh.status=='STALE' else 'BLOCKED'
            self.staging_repository.transition(cursor,stage.staging_id,from_state=stage.staging_state,to_state=terminal,reason_code=fresh.reason_code)
            return PublicationResult(terminal,(fresh.reason_code or 'PREPUBLICATION_FRESHNESS_FAILED',))
        previous_report = self.publication_repository.get_current_report(cursor,stage.property_id,stage.report_variant) if self.history_service is not None else None
        previous_channel = self.publication_repository.get_channel_pointer(cursor,stage.property_id,stage.report_variant,stage.channel) if self.history_service is not None else None
        if self.history_service is not None and previous_channel is not None:
            self.history_service.record_pointer_replacement(cursor,property_id=stage.property_id,report_variant=stage.report_variant,channel=stage.channel,
                previous_report_id=previous_report[0] if previous_report else previous_channel[0],previous_render_id=previous_channel[1],
                new_report_id=stage.report_id,new_render_id=stage.render_id,actor=actor,reason_code='PUBLISH_REPLACEMENT',correlation_id=stage.correlation_id)
        self.publication_repository.set_current_report(cursor,CurrentReportPointer(stage.property_id,stage.report_variant,stage.report_id,updated_by=actor))
        self.publication_repository.set_channel_pointer(cursor,ChannelPointer(stage.property_id,stage.report_variant,stage.channel,stage.report_id,stage.render_id,updated_by=actor))
        self.publication_repository.append_history(cursor,PublicationHistoryRecord(stage.property_id,stage.report_variant,stage.report_id,'PUBLISHED',actor,stage.channel,stage.render_id,None,stage.correlation_id))
        if not self.staging_repository.transition(cursor,stage.staging_id,from_state=stage.staging_state,to_state='PUBLISHED'):
            raise RuntimeError('publication staging state changed during publish')
        if self.cache_events is not None:
            self.cache_events.emit(cursor,property_id=stage.property_id,report_variant=stage.report_variant,channel=stage.channel,reason_code='PUBLISHED',actor=actor,correlation_id=stage.correlation_id)
        return PublicationResult('PUBLISHED')
