from __future__ import annotations
class ReleaseApprovalService:
    INSERT="""INSERT INTO operations.release_approvals (release_id,manifest_fingerprint,decision,approved_by,reason_code) VALUES (%s,%s,%s,%s,%s)"""
    def __init__(self,*,lifecycle): self.lifecycle=lifecycle
    def approve(self,cursor,*,release,items,approved_by,reason_code='RELEASE_APPROVED',correlation_id=None):
        if not release.manifest_fingerprint: raise ValueError('release manifest must be frozen before approval')
        if not items or any(i.item_state!='STAGED' for i in items): raise ValueError('all release items must be STAGED before approval')
        cursor.execute(self.INSERT,(release.release_id,release.manifest_fingerprint,'APPROVED',approved_by,reason_code))
        for i in items:self.lifecycle.transition(cursor,item=i,to_state='APPROVED',actor=approved_by,reason_code=reason_code,correlation_id=correlation_id)
        return 'APPROVED'
