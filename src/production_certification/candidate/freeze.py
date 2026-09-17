from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID
import re
from src.shared.canonical_json import canonical_json

_SHA = re.compile(r'^[0-9a-f]{64}$')

@dataclass(frozen=True)
class CandidateFreeze:
    production_certification_id: UUID
    candidate_version: str
    candidate_fingerprint: str
    artifact_sha256: str
    source_revision: str
    artifact_uri: str
    freeze_fingerprint: str
    frozen_by: str

class CandidateFreezer:
    @staticmethod
    def _hash(payload) -> str:
        return sha256(canonical_json(payload).encode('utf-8')).hexdigest()

    def freeze(self, *, production_certification_id: UUID, run_candidate_version: str,
               run_candidate_fingerprint: str, candidate_version: str,
               candidate_fingerprint: str, artifact_sha256: str,
               source_revision: str, artifact_uri: str, frozen_by: str) -> CandidateFreeze:
        for name, value in [('candidate_fingerprint',candidate_fingerprint),('artifact_sha256',artifact_sha256)]:
            if not _SHA.fullmatch(value):
                raise ValueError(f'{name} must be lowercase SHA-256')
        if candidate_version != run_candidate_version or candidate_fingerprint != run_candidate_fingerprint:
            raise ValueError('candidate does not match production certification run')
        if not source_revision.strip() or not artifact_uri.strip() or not frozen_by.strip():
            raise ValueError('source_revision, artifact_uri, and frozen_by are required')
        payload = {
            'production_certification_id': str(production_certification_id),
            'candidate_version': candidate_version,
            'candidate_fingerprint': candidate_fingerprint,
            'artifact_sha256': artifact_sha256,
            'source_revision': source_revision,
            'artifact_uri': artifact_uri,
        }
        return CandidateFreeze(production_certification_id,candidate_version,candidate_fingerprint,
                               artifact_sha256,source_revision,artifact_uri,self._hash(payload),frozen_by)
