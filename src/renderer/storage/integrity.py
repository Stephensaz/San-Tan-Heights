from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from src.renderer.repository import RenderVersion

@dataclass(frozen=True)
class StorageIntegrityResult:
    valid: bool
    code: str

class StorageIntegrityEngine:
    """Verifies bytes retrieved from immutable artifact storage against DB evidence."""
    def verify(self, *, render: RenderVersion, stored_bytes: bytes) -> StorageIntegrityResult:
        if not render.storage_uri:
            return StorageIntegrityResult(False, 'RENDER_STORAGE_URI_MISSING')
        if render.artifact_hash is None or render.artifact_size_bytes is None:
            return StorageIntegrityResult(False, 'RENDER_ARTIFACT_EVIDENCE_MISSING')
        if len(stored_bytes) != render.artifact_size_bytes:
            return StorageIntegrityResult(False, 'STORAGE_SIZE_MISMATCH')
        if sha256(stored_bytes).hexdigest() != render.artifact_hash:
            return StorageIntegrityResult(False, 'STORAGE_HASH_MISMATCH')
        return StorageIntegrityResult(True, 'PASS')
