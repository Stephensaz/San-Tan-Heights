from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from src.shared.hash import sha256_canonical


class PresentationInputHashError(ValueError):
    pass


@dataclass(frozen=True)
class PresentationDependency:
    dependency_type: str
    dependency_id: str
    semantic_fingerprint: str
    dependency_version: str
    slot_id: str | None = None


@dataclass(frozen=True)
class PresentationInputIdentity:
    presentation_input_hash: str
    semantic_projection: dict


class PresentationInputHashEngine:
    """Hash exact presentation inputs without changing semantic report identity."""

    VALID_TYPES = {'WEB', 'PDF', 'PRINT', 'MOBILE_PREVIEW'}

    @staticmethod
    def _hash64(value: str, field: str) -> None:
        if len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise PresentationInputHashError(f'{field} must be a lowercase SHA-256 hex digest')

    def calculate(
        self,
        *,
        report_id: str,
        render_type: str,
        canonical_report_payload_hash: str,
        report_input_hash: str,
        render_contract_version: str,
        template_id: str,
        template_version: str,
        renderer_version: str,
        dependencies: Iterable[PresentationDependency] = (),
    ) -> PresentationInputIdentity:
        if render_type not in self.VALID_TYPES:
            raise PresentationInputHashError(f'unsupported render type: {render_type}')
        self._hash64(canonical_report_payload_hash, 'canonical_report_payload_hash')
        self._hash64(report_input_hash, 'report_input_hash')
        dep_rows = []
        seen = set()
        for dep in dependencies:
            self._hash64(dep.semantic_fingerprint, 'dependency semantic_fingerprint')
            key = (dep.dependency_type, dep.dependency_id, dep.slot_id)
            if key in seen:
                raise PresentationInputHashError(f'duplicate presentation dependency: {key}')
            seen.add(key)
            dep_rows.append({
                'dependency_type': dep.dependency_type,
                'dependency_id': dep.dependency_id,
                'semantic_fingerprint': dep.semantic_fingerprint,
                'dependency_version': dep.dependency_version,
                'slot_id': dep.slot_id,
            })
        dep_rows.sort(key=lambda x: (x['dependency_type'], x['dependency_id'], x['slot_id'] or ''))
        projection = {
            'report_id': str(report_id),
            'render_type': render_type,
            'canonical_report_payload_hash': canonical_report_payload_hash,
            'report_input_hash': report_input_hash,
            'render_contract_version': render_contract_version,
            'template_id': template_id,
            'template_version': template_version,
            'renderer_version': renderer_version,
            'render_dependencies': dep_rows,
        }
        return PresentationInputIdentity(sha256_canonical(projection), projection)
