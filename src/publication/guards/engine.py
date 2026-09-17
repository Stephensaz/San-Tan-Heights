from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PublicationGuardResult:
    allowed: bool
    reasons: tuple[str,...]

class PublicationGuardEngine:
    """Fail-closed eligibility checks. This engine never mutates publication state."""
    CHANNEL_RENDER={'WEB':'WEB','PDF_DOWNLOAD':'PDF','PRINT':'PRINT'}
    def evaluate(self,*,stage,report,render)->PublicationGuardResult:
        reasons=[]
        expected=self.CHANNEL_RENDER.get(stage.channel)
        if expected is None: reasons.append('PUBLICATION_CHANNEL_UNSUPPORTED')
        if stage.staging_state not in {'STAGED','VALIDATING','READY'}: reasons.append('PUBLICATION_STAGE_NOT_ACTIVE')
        if report.property_id != stage.property_id: reasons.append('REPORT_PROPERTY_MISMATCH')
        if report.report_variant != stage.report_variant: reasons.append('REPORT_VARIANT_MISMATCH')
        if report.report_id != stage.report_id: reasons.append('REPORT_ID_MISMATCH')
        if report.content_state != 'READY' or report.qa_status != 'PASS' or not report.publication_eligible or report.health_state != 'CLEAN': reasons.append('REPORT_NOT_PUBLICATION_ELIGIBLE')
        if render.render_id != stage.render_id or render.report_id != report.report_id: reasons.append('RENDER_LINEAGE_MISMATCH')
        if expected is not None and render.render_type != expected: reasons.append('RENDER_CHANNEL_MISMATCH')
        if render.content_state != 'READY' or render.qa_status != 'PASS' or not render.publication_eligible or render.health_state != 'CLEAN': reasons.append('RENDER_NOT_PUBLICATION_ELIGIBLE')
        if not render.storage_uri or not render.artifact_hash: reasons.append('RENDER_ARTIFACT_INCOMPLETE')
        return PublicationGuardResult(not reasons,tuple(reasons))
