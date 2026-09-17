from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID
import yaml
from src.shared.canonical_json import canonical_json
from src.kernel.contracts.manifest_loader import load_contract_manifest
from src.kernel.contracts.hash_verifier import verify_contract_hashes

_ALLOWED = {'CONTRACT_MANIFEST','BUILD_MANIFEST'}

@dataclass(frozen=True)
class ManifestPin:
    production_certification_id: UUID
    manifest_type: str
    manifest_version: str
    manifest_sha256: str
    manifest_payload: Mapping[str, Any]
    pin_fingerprint: str
    pinned_by: str

class ManifestPinner:
    @staticmethod
    def _bytes_hash(path: Path) -> str:
        return sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _pin_hash(payload) -> str:
        return sha256(canonical_json(payload).encode('utf-8')).hexdigest()

    def pin_file(self, *, production_certification_id: UUID, manifest_type: str,
                 path: str | Path, pinned_by: str, repository_root: str | Path | None = None) -> ManifestPin:
        if manifest_type not in _ALLOWED:
            raise ValueError('unknown manifest_type')
        p = Path(path)
        payload = yaml.safe_load(p.read_text())
        if not isinstance(payload, dict):
            raise ValueError('manifest must be a mapping')
        if manifest_type == 'CONTRACT_MANIFEST':
            version = str(payload.get('manifest_id','')).strip()
            if payload.get('status') != 'LOCKED':
                raise ValueError('contract manifest must be LOCKED')
            manifest = load_contract_manifest(p)
            if repository_root is None:
                raise ValueError('repository_root is required for CONTRACT_MANIFEST pinning')
            verify_contract_hashes(Path(repository_root), manifest.contracts)
        else:
            version = str(payload.get('version','')).strip()
            if payload.get('status') != 'ACTIVE':
                raise ValueError('build manifest must be ACTIVE')
        if not version or not pinned_by.strip():
            raise ValueError('manifest version and pinned_by are required')
        file_hash = self._bytes_hash(p)
        pin_payload = {'manifest_type': manifest_type, 'manifest_version': version,
                       'manifest_sha256': file_hash, 'manifest_payload': payload}
        return ManifestPin(production_certification_id,manifest_type,version,file_hash,payload,
                           self._pin_hash(pin_payload),pinned_by)
