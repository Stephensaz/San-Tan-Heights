from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from src.renderer.repository import RenderVersion

@dataclass(frozen=True)
class RenderValidationIssue:
    code: str
    detail: str

@dataclass(frozen=True)
class RenderValidationResult:
    valid: bool
    issues: tuple[RenderValidationIssue, ...]

class RenderValidationEngine:
    """Fail-closed validation of a completed render artifact.

    This engine validates presentation integrity only. It never changes report
    semantics and never publishes a render.
    """
    def __init__(self, contract_registry):
        self.contract_registry = contract_registry

    def validate(self, *, render: RenderVersion, artifact_bytes: bytes, report_content_state: str = 'READY', report_qa_status: str = 'PASS') -> RenderValidationResult:
        issues: list[RenderValidationIssue] = []
        try:
            contract = self.contract_registry.resolve(render.render_type)
        except Exception as exc:
            return RenderValidationResult(False, (RenderValidationIssue('RENDER_CONTRACT_UNKNOWN', str(exc)),))

        actual_hash = sha256(artifact_bytes).hexdigest()
        if render.render_contract_version != contract.render_contract_version:
            issues.append(RenderValidationIssue('RENDER_CONTRACT_VERSION_MISMATCH', 'render contract version does not match registry'))
        if render.mime_type not in contract.mime_types:
            issues.append(RenderValidationIssue('RENDER_MIME_TYPE_INVALID', 'artifact MIME type is not permitted by render contract'))
        if render.artifact_hash is None or render.artifact_hash != actual_hash:
            issues.append(RenderValidationIssue('RENDER_ARTIFACT_HASH_MISMATCH', 'stored artifact hash does not match artifact bytes'))
        if render.artifact_size_bytes is None or render.artifact_size_bytes != len(artifact_bytes):
            issues.append(RenderValidationIssue('RENDER_ARTIFACT_SIZE_MISMATCH', 'stored artifact size does not match artifact bytes'))
        if not render.storage_uri:
            issues.append(RenderValidationIssue('RENDER_STORAGE_URI_MISSING', 'completed render requires a storage URI'))
        if render.content_state != 'READY':
            issues.append(RenderValidationIssue('RENDER_NOT_READY', 'validated render must be READY'))
        if render.health_state != 'CLEAN':
            issues.append(RenderValidationIssue('RENDER_HEALTH_NOT_CLEAN', 'validated render must be CLEAN'))
        if render.qa_status != 'PASS':
            issues.append(RenderValidationIssue('RENDER_QA_NOT_PASS', 'validated render must have PASS QA'))
        if not render.publication_eligible:
            issues.append(RenderValidationIssue('RENDER_NOT_PUBLICATION_ELIGIBLE', 'validated render must be explicitly publication eligible'))
        if report_content_state != 'READY' or report_qa_status != 'PASS':
            issues.append(RenderValidationIssue('SOURCE_REPORT_NOT_ELIGIBLE', 'source report must remain READY with PASS QA'))
        return RenderValidationResult(not issues, tuple(issues))
