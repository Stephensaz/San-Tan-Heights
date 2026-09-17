from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4
from src.kernel.commands import IdempotencyService, ProcessedCommand
from src.kernel.events import EventWriter, EventDraft
from src.shared.hash import sha256_canonical
from src.snapshot.query import CurrentSnapshotReader
from src.regeneration.priority import PriorityRegistry, PriorityResolver
from src.regeneration.repository import RegenerationJob, RegenerationJobRepository
from src.regeneration.target import JobTargetContext, JobTargetKeyEngine
from .models import QueueRegenerationCommand, QueueRegenerationResult

class RegenerationQueueService:
    ALLOWED_TRIGGERS={'REPORT_MARKED_DIRTY','REPORT_REACTIVATED','REPORT_STALE_REBUILD_REQUIRED','REGENERATION_RETRY_REQUIRED','RELEASE_REGENERATION_REQUESTED','MANUAL_REBUILD_REQUESTED'}
    def __init__(self, root: Path, repository=None, current_snapshots=None, idempotency=None, event_writer=None):
        self.root=root; self.repository=repository or RegenerationJobRepository(); self.current_snapshots=current_snapshots or CurrentSnapshotReader()
        self.idempotency=idempotency or IdempotencyService(); self.events=event_writer or EventWriter(root)
        self.priorities=PriorityResolver(PriorityRegistry.from_repository(root)); self.keys=JobTargetKeyEngine()
    def queue(self,cursor,cmd: QueueRegenerationCommand) -> QueueRegenerationResult:
        if cmd.trigger_type not in self.ALLOWED_TRIGGERS: raise ValueError('unsupported regeneration trigger')
        if cmd.report_variant not in {'AGENT','SELLER','PUBLIC'}: raise ValueError('unsupported report variant')
        if not cmd.idempotency_key.strip(): raise ValueError('idempotency_key is required')
        semantic={'property_id':str(cmd.property_id),'report_variant':cmd.report_variant,'trigger_type':cmd.trigger_type,'target_snapshot_id':str(cmd.target_snapshot_id) if cmd.target_snapshot_id else None,'report_schema_version':cmd.report_schema_version,'content_contract_version':cmd.content_contract_version,'variant_policy_version':cmd.variant_policy_version,'release_id':str(cmd.release_id) if cmd.release_id else None,'change_class':cmd.change_class,'reason_code':cmd.reason_code}
        request_hash=sha256_canonical(semantic)
        dec=self.idempotency.check(cursor,cmd.service_name,cmd.idempotency_key,request_hash)
        if dec.status=='REPLAY':
            p=dec.prior.result_payload
            return QueueRegenerationResult(p['status'],uuid_from(p.get('job_id')),uuid_from(p.get('target_snapshot_id')),p.get('job_target_key'),p.get('priority_class'),True)
        current=self.current_snapshots.get(cursor,cmd.property_id)
        target=cmd.target_snapshot_id or (current.current_snapshot_id if current else None)
        if target is None:
            return self._record(cursor,cmd,request_hash,QueueRegenerationResult('BLOCKED',None,None,None))
        if cmd.target_snapshot_id is not None and (current is None or current.current_snapshot_id!=cmd.target_snapshot_id):
            return self._record(cursor,cmd,request_hash,QueueRegenerationResult('BLOCKED',None,target,None))
        context=JobTargetContext(cmd.property_id,cmd.report_variant,target,cmd.report_schema_version,cmd.content_contract_version,cmd.variant_policy_version)
        key=self.keys.calculate(context)
        existing=self.repository.find_active(cursor,cmd.property_id,cmd.report_variant,key)
        pri=self.priorities.resolve(trigger_type=cmd.trigger_type,change_class=cmd.change_class,reason_code=cmd.reason_code)
        if existing:
            return self._record(cursor,cmd,request_hash,QueueRegenerationResult('EXISTING_ACTIVE_JOB',existing,target,key,pri.priority_class))
        job=RegenerationJob(uuid4(),cmd.property_id,cmd.report_variant,cmd.trigger_type,target,pri.priority_class,pri.priority_score,key,cmd.correlation_id,trigger_event_id=cmd.trigger_event_id,old_report_id=cmd.old_report_id,max_attempts=cmd.max_attempts,release_id=cmd.release_id)
        self.repository.insert(cursor,job)
        self.events.write(cursor,EventDraft(event_type='REGENERATION_JOB_QUEUED',source_system='REGENERATION_SERVICE',actor_type='SYSTEM',actor_id=cmd.service_name,correlation_id=cmd.correlation_id,causation_event_id=cmd.trigger_event_id,property_id=cmd.property_id,snapshot_id=target,job_id=job.job_id,reason_code=cmd.reason_code,payload={'job_id':str(job.job_id),'report_variant':cmd.report_variant,'job_target_key':key,'priority_class':pri.priority_class}))
        return self._record(cursor,cmd,request_hash,QueueRegenerationResult('QUEUED',job.job_id,target,key,pri.priority_class))
    def _record(self,cursor,cmd,h,res):
        payload={'status':res.status,'job_id':str(res.job_id) if res.job_id else None,'target_snapshot_id':str(res.target_snapshot_id) if res.target_snapshot_id else None,'job_target_key':res.job_target_key,'priority_class':res.priority_class}
        self.idempotency.record(cursor,ProcessedCommand(uuid4(),cmd.service_name,'QueueRegeneration',cmd.idempotency_key,h,res.status,cmd.correlation_id,result_payload=payload)); return res

def uuid_from(v):
    if not v: return None
    from uuid import UUID
    return UUID(str(v))
