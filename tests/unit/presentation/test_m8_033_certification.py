from pathlib import Path

from src.presentation.certification import M8033CertificationRunner

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "registries" / "presentation" / "m8-033-certification-v1.0.yaml"


def runner():
    return M8033CertificationRunner(ROOT, MANIFEST)


def test_m8_033_manifest_is_frozen_and_exact():
    r = runner()
    assert tuple(r.manifest["layers"]) == tuple("ABCDEFGHIJ")
    assert tuple(r.manifest["stage_gates"]) == tuple("ABCDEFGHIJKL")
    assert len(r.manifest["acceptance_criteria"]) == 12
    assert r.manifest["final_rules"]["allow_waivers"] is False
    assert r.manifest["final_rules"]["allow_conditional_go"] is False


def test_m8_033_executes_fail_closed_when_approved_visual_baseline_manifest_is_missing():
    bundle = runner().run(verify_source_commit=False)
    assert bundle.verdict == "FAIL / NO-GO"
    by_layer = {item.key: item for item in bundle.layers}
    assert by_layer["A"].passed is True
    assert by_layer["B"].passed is True
    assert by_layer["C"].passed is True
    assert by_layer["D"].passed is True
    assert by_layer["E"].passed is True
    assert by_layer["F"].passed is True
    assert by_layer["G"].passed is True
    assert by_layer["H"].passed is True
    assert by_layer["I"].passed is False
    assert by_layer["J"].passed is False
    assert any("approved controlled visual baseline manifest/provenance evidence is missing" in detail for detail in by_layer["I"].details)
    assert bundle.waivers == ()


def test_m8_033_evidence_is_deterministic_for_same_repository_state():
    first = runner().run(verify_source_commit=False)
    second = runner().run(verify_source_commit=False)
    assert first.evidence_hash == second.evidence_hash
    assert first.canonical_payload() == second.canonical_payload()
