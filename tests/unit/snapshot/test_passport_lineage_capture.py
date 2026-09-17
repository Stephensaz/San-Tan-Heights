from dataclasses import replace
import pytest
from src.snapshot.findings.freezer import FindingFreezer
from src.snapshot.passports import PassportLineageCapture, PassportLineageError, PassportReference
from tests.unit.snapshot._fixtures import finding


def _ref(frozen, *, passport_id=None, passport_version=None, qa="PASS", evidence_hash=None, finding_id=None):
    return PassportReference(
        passport_id or frozen.passport_id,
        passport_version or frozen.passport_version,
        "c" * 64,
        qa,
        finding_id or frozen.finding_id,
        evidence_hash or frozen.evidence_reference_set_hash,
    )


def test_capture_exact_immutable_passport_reference():
    frozen = FindingFreezer().freeze((finding(),))[0]
    capture = PassportLineageCapture(lambda pid, ver: _ref(frozen))
    refs = capture.capture((frozen,))
    assert len(refs) == 1
    assert refs[0].passport_id == frozen.passport_id
    assert refs[0].passport_version == frozen.passport_version
    assert refs[0].passport_qa_status == "PASS"


def test_capture_rejects_wrong_passport_version():
    frozen = FindingFreezer().freeze((finding(),))[0]
    capture = PassportLineageCapture(lambda pid, ver: _ref(frozen, passport_version="v2"))
    with pytest.raises(PassportLineageError, match="identity/version mismatch"):
        capture.capture((frozen,))


def test_capture_rejects_wrong_finding_or_evidence_set():
    frozen = FindingFreezer().freeze((finding(),))[0]
    with pytest.raises(PassportLineageError, match="finding mismatch"):
        PassportLineageCapture(lambda pid, ver: _ref(frozen, finding_id="other")).capture((frozen,))
    with pytest.raises(PassportLineageError, match="evidence reference set mismatch"):
        PassportLineageCapture(lambda pid, ver: _ref(frozen, evidence_hash="d" * 64)).capture((frozen,))


def test_capture_requires_passport_qa_pass():
    frozen = FindingFreezer().freeze((finding(),))[0]
    with pytest.raises(PassportLineageError, match="Passport QA must be PASS"):
        PassportLineageCapture(lambda pid, ver: _ref(frozen, qa="REVIEW_REQUIRED")).capture((frozen,))
