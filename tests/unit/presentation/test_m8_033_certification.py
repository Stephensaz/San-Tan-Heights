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


def test_m8_033_clean_repaired_candidate_passes_every_gate():
    bundle = runner().run(verify_source_commit=False)
    assert bundle.verdict == "PASS / GO"
    assert bundle.waivers == ()
    assert bundle.open_defects == ()
    by_layer = {item.key: item for item in bundle.layers}
    assert tuple(by_layer) == tuple("ABCDEFGHIJ")
    assert all(item.passed for item in bundle.layers)
    assert len(bundle.stage_gates) == 12
    assert all(item.passed for item in bundle.stage_gates)
    assert len(bundle.acceptance_criteria) == 12
    assert all(item.passed for item in bundle.acceptance_criteria)
    assert any("visual_baseline_fingerprint=" in detail for detail in by_layer["I"].details)


def test_m8_033_evidence_is_deterministic_for_same_repository_state():
    first = runner().run(verify_source_commit=False)
    second = runner().run(verify_source_commit=False)
    assert first.evidence_hash == second.evidence_hash
    assert first.canonical_payload() == second.canonical_payload()
