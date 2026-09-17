from __future__ import annotations
from uuid import UUID
from .models import RenderDependency, RenderVersion


class RenderRepository:
    INSERT_RENDER = '''INSERT INTO reporting.render_versions
(render_id,report_id,render_type,render_version,render_contract_version,template_id,template_version,renderer_version,presentation_input_hash,artifact_hash,artifact_size_bytes,storage_uri,mime_type,content_state,health_state,qa_status,qa_completed_at,publication_eligible,supersedes_render_id,superseded_by_render_id,created_by)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'''

    INSERT_DEPENDENCY = '''INSERT INTO reporting.render_dependencies
(render_dependency_id,render_id,dependency_type,dependency_id,semantic_fingerprint,dependency_version,slot_id)
VALUES (%s,%s,%s,%s,%s,%s,%s)'''

    FIND_BY_ID = '''SELECT render_id,report_id,render_type,render_version,render_contract_version,template_id,template_version,renderer_version,presentation_input_hash,artifact_hash,artifact_size_bytes,storage_uri,mime_type,content_state,health_state,qa_status,qa_completed_at,publication_eligible,supersedes_render_id,superseded_by_render_id,created_at,created_by
FROM reporting.render_versions WHERE render_id=%s'''

    FIND_EQUIVALENT = '''SELECT render_id FROM reporting.render_versions
WHERE report_id=%s AND render_type=%s AND presentation_input_hash=%s
AND content_state NOT IN ('FAILED','STALE','INVALIDATED','ARCHIVED')
ORDER BY render_version DESC LIMIT 1'''

    @staticmethod
    def _hash64(value: str, field: str) -> None:
        if len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError(f'{field} must be a lowercase SHA-256 hex digest')

    def insert_render(self, cursor, render: RenderVersion) -> None:
        if render.render_type not in {'WEB', 'PDF', 'PRINT', 'MOBILE_PREVIEW'}:
            raise ValueError('unsupported render type')
        if render.render_version < 1:
            raise ValueError('render_version must be positive')
        self._hash64(render.presentation_input_hash, 'presentation_input_hash')
        if render.artifact_hash is not None:
            self._hash64(render.artifact_hash, 'artifact_hash')
        if render.artifact_size_bytes is not None and render.artifact_size_bytes < 0:
            raise ValueError('artifact_size_bytes must be non-negative')
        cursor.execute(self.INSERT_RENDER, (
            render.render_id, render.report_id, render.render_type, render.render_version,
            render.render_contract_version, render.template_id, render.template_version,
            render.renderer_version, render.presentation_input_hash, render.artifact_hash,
            render.artifact_size_bytes, render.storage_uri, render.mime_type,
            render.content_state, render.health_state, render.qa_status,
            render.qa_completed_at, render.publication_eligible,
            render.supersedes_render_id, render.superseded_by_render_id, render.created_by,
        ))

    def insert_dependency(self, cursor, dependency: RenderDependency) -> None:
        self._hash64(dependency.semantic_fingerprint, 'semantic_fingerprint')
        cursor.execute(self.INSERT_DEPENDENCY, (
            dependency.render_dependency_id, dependency.render_id,
            dependency.dependency_type, dependency.dependency_id,
            dependency.semantic_fingerprint, dependency.dependency_version,
            dependency.slot_id,
        ))

    def find_equivalent(self, cursor, report_id: UUID, render_type: str, presentation_input_hash: str) -> UUID | None:
        if render_type not in {'WEB', 'PDF', 'PRINT', 'MOBILE_PREVIEW'}:
            raise ValueError('unsupported render type')
        self._hash64(presentation_input_hash, 'presentation_input_hash')
        cursor.execute(self.FIND_EQUIVALENT, (report_id, render_type, presentation_input_hash))
        row = cursor.fetchone()
        return UUID(str(row[0])) if row else None
