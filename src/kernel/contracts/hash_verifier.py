from __future__ import annotations
from hashlib import sha256
from pathlib import Path
from .contract_errors import ContractHashMismatch

def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def verify_contract_hashes(root: Path, entries) -> None:
    for entry in entries:
        path = root / entry.path
        if not path.is_file():
            raise ContractHashMismatch(f"Missing contract file: {entry.path}")
        actual = sha256_file(path)
        if actual != entry.sha256:
            raise ContractHashMismatch(
                f"Hash mismatch for {entry.contract_id}: expected {entry.sha256}, got {actual}"
            )
