from pathlib import Path
import shutil
import yaml
import pytest
from src.kernel.contracts import load_contract_manifest, validate_architecture_lock, verify_contract_hashes
from src.kernel.contracts.contract_errors import ContractHashMismatch, ManifestValidationError

ROOT=Path(__file__).resolve().parents[2]

def test_locked_manifest_loads_and_hashes_verify():
    manifest=load_contract_manifest(ROOT/"CONTRACT-MANIFEST.yaml")
    verify_contract_hashes(ROOT, manifest.contracts)
    assert manifest.status == "LOCKED"
    assert len(manifest.contracts) >= 8

def test_architecture_lock_is_valid():
    lock=validate_architecture_lock(ROOT/"ARCHITECTURE-LOCK.yaml")
    assert lock["status"] == "LOCKED"

def test_hash_mismatch_fails(tmp_path):
    shutil.copytree(ROOT, tmp_path/"repo", dirs_exist_ok=True)
    repo=tmp_path/"repo"
    manifest=load_contract_manifest(repo/"CONTRACT-MANIFEST.yaml")
    first=repo/manifest.contracts[0].path
    first.write_text(first.read_text()+"# tampered\n")
    with pytest.raises(ContractHashMismatch):
        verify_contract_hashes(repo, manifest.contracts)

def test_unknown_dependency_fails(tmp_path):
    raw=yaml.safe_load((ROOT/"CONTRACT-MANIFEST.yaml").read_text())
    raw["contracts"][0]["depends_on"]=["NOT_REAL"]
    p=tmp_path/"manifest.yaml"
    p.write_text(yaml.safe_dump(raw, sort_keys=False))
    with pytest.raises(ManifestValidationError):
        load_contract_manifest(p)
