from pathlib import Path
import shutil
import yaml
import pytest
from src.kernel.registry import load_registry_bundle
from src.kernel.registry.registry_errors import RegistryValidationError

ROOT=Path(__file__).resolve().parents[2]

def test_registry_bundle_loads_and_cross_references():
    bundle=load_registry_bundle(ROOT)
    assert "CONTENT" in bundle.states
    assert bundle.transitions[0]["from_state"] == "BUILDING"

def test_unknown_guard_reference_fails(tmp_path):
    shutil.copytree(ROOT/"registries", tmp_path/"registries")
    path=tmp_path/"registries/transitions/transitions.yaml"
    raw=yaml.safe_load(path.read_text())
    raw["transitions"][0]["required_guards"].append("NOT_REAL")
    path.write_text(yaml.safe_dump(raw, sort_keys=False))
    with pytest.raises(RegistryValidationError):
        load_registry_bundle(tmp_path)

def test_unknown_state_reference_fails(tmp_path):
    shutil.copytree(ROOT/"registries", tmp_path/"registries")
    path=tmp_path/"registries/transitions/transitions.yaml"
    raw=yaml.safe_load(path.read_text())
    raw["transitions"][0]["to_state"]="NOT_A_STATE"
    path.write_text(yaml.safe_dump(raw, sort_keys=False))
    with pytest.raises(RegistryValidationError):
        load_registry_bundle(tmp_path)
