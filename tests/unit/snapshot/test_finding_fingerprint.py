from dataclasses import replace
import pytest
from src.snapshot.findings.freezer import FindingFreezer
from src.snapshot.fingerprints import FindingFingerprintEngine, FindingFingerprintMismatch
from src.snapshot.passports import PassportReference
from tests.unit.snapshot._fixtures import finding


def _parts():
    frozen = FindingFreezer().freeze((finding(),))[0]
    passport = PassportReference(frozen.passport_id, frozen.passport_version, "c"*64, "PASS", frozen.finding_id, frozen.evidence_reference_set_hash)
    return frozen, passport


def test_finding_fingerprint_is_deterministic_and_ignores_identifier():
    engine = FindingFingerprintEngine()
    frozen, passport = _parts()
    fp1 = engine.calculate(frozen, passport)
    fp2 = engine.calculate(replace(frozen, finding_id="renamed"), replace(passport, finding_id="renamed"))
    assert fp1 == fp2
    assert len(fp1) == 64


def test_finding_fingerprint_changes_for_semantic_content():
    engine = FindingFingerprintEngine()
    frozen, passport = _parts()
    base = engine.calculate(frozen, passport)
    assert engine.calculate(replace(frozen, canonical_value={"code":"RESIDENTIAL_LOT"}), passport) != base
    assert engine.calculate(replace(frozen, publication_scope="AGENT"), passport) != base
    assert engine.calculate(replace(frozen, public_wording="Revised public text"), passport) != base
    assert engine.calculate(frozen, replace(passport, passport_semantic_fingerprint="d"*64)) != base


def test_verify_upstream_accepts_exact_and_rejects_mismatch():
    engine = FindingFingerprintEngine()
    frozen, passport = _parts()
    expected = engine.calculate(frozen, passport)
    exact = replace(frozen, semantic_fingerprint=expected)
    assert engine.verify_upstream(exact, passport) == expected
    with pytest.raises(FindingFingerprintMismatch, match="UPSTREAM_FINDING_FINGERPRINT_MISMATCH"):
        engine.verify_upstream(frozen, passport)
