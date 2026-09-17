from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
from uuid import uuid4
from src.operations.monitoring.pointer_integrity import PublicationPointerIntegritySweep
from src.operations.monitoring.orphans import OrphanDetector
from src.operations.monitoring.stuck_jobs import StuckJobDetector
from src.operations.monitoring.release_integrity import ReleaseIntegritySweep

def test_pointer_sweep_detects_missing_and_cross_report_render():
    x=PublicationPointerIntegritySweep().evaluate([{'pointer_id':'p1','channel':'WEB','report_id':'r1','report_exists':True,'render_exists':True,'render_report_id':'r2'}])
    assert [f.rule_id for f in x]==['POINTER_RENDER_REPORT_MATCH']

def test_orphan_detector_only_flags_ready_unreferenced():
    x=OrphanDetector().detect([{'kind':'REPORT','id':'r1','state':'READY','referenced':False},{'kind':'RENDER','id':'x','state':'BUILDING','referenced':False}])
    assert len(x)==1 and x[0].rule_id=='ORPHAN_READY_REPORT'

def test_stuck_job_detector_uses_queue_age_and_expired_lease():
    now=datetime(2026,9,16,tzinfo=timezone.utc)
    jobs=[{'job_id':'a','job_state':'QUEUED','queued_at':now-timedelta(hours=3),'lease_expires_at':None},{'job_id':'b','job_state':'RUNNING','queued_at':now,'lease_expires_at':now-timedelta(minutes=10)}]
    x=StuckJobDetector().detect(jobs,now=now)
    assert {f.entity_id for f in x}=={'a','b'}

def test_release_integrity_checks_count_and_manifest_fingerprints():
    rid=uuid4(); release=SimpleNamespace(release_id=rid,total_item_count=2,manifest_fingerprint='a'*64,membership_fingerprint='b'*64)
    manifest=SimpleNamespace(manifest_fingerprint='c'*64,membership_fingerprint='b'*64)
    x=ReleaseIntegritySweep().evaluate(release=release,manifest=manifest,items=[object()])
    assert {f.rule_id for f in x}=={'RELEASE_ITEM_COUNT_MATCH','RELEASE_MANIFEST_MATCH'}
