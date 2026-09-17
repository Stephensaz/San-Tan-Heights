from uuid import uuid4
import pytest
from src.production_certification.candidate.freeze import CandidateFreezer

H='a'*64
A='b'*64

def test_candidate_freeze_matches_run_identity_and_is_deterministic():
    rid=uuid4(); f=CandidateFreezer()
    x=f.freeze(production_certification_id=rid,run_candidate_version='1.2.3',run_candidate_fingerprint=H,
        candidate_version='1.2.3',candidate_fingerprint=H,artifact_sha256=A,source_revision='git:abc',artifact_uri='oci://candidate@sha256:'+A,frozen_by='ops')
    y=f.freeze(production_certification_id=rid,run_candidate_version='1.2.3',run_candidate_fingerprint=H,
        candidate_version='1.2.3',candidate_fingerprint=H,artifact_sha256=A,source_revision='git:abc',artifact_uri='oci://candidate@sha256:'+A,frozen_by='ops')
    assert x.freeze_fingerprint == y.freeze_fingerprint


def test_candidate_freeze_rejects_drift_from_run():
    with pytest.raises(ValueError, match='does not match'):
        CandidateFreezer().freeze(production_certification_id=uuid4(),run_candidate_version='1',run_candidate_fingerprint=H,
            candidate_version='2',candidate_fingerprint=H,artifact_sha256=A,source_revision='r',artifact_uri='u',frozen_by='ops')
