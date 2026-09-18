import pytest

from src.evolution.progressive_build_pipeline import (
    StageInput,
    execute_progressive_pipeline,
    load_pipeline_registry,
)

R = "registries/evolution/m10-004-progressive-build-pipeline-v1.0.yaml"


def registry():
    return load_pipeline_registry(R)


def good_inputs():
    ids = [x["id"] for x in registry()["stages"]]
    return {
        stage_id: StageInput(
            stage_id=stage_id,
            checks={"required_contracts_present": True, "stage_specific_validation": True},
            evidence={"manifest": f"SYNTH-{stage_id}-MANIFEST", "fingerprint": "b" * 64},
        )
        for stage_id in ids
    }


def run(inputs=None):
    return execute_progressive_pipeline(
        community_id="DESERT_RIDGE_TEST",
        onboarding_bootstrap_fingerprint="a" * 64,
        stage_inputs=inputs or good_inputs(),
        registry=registry(),
    )


def test_registry_has_exact_frozen_eight_stage_sequence():
    r = registry()
    assert [x["id"] for x in r["stages"]] == [
        "ONBOARDING_BOOTSTRAP",
        "IDENTITY_JURISDICTION",
        "SOURCE_ADAPTER_READINESS",
        "CORPUS_ADMISSION_READINESS",
        "EVIDENCE_PASSPORT_READINESS",
        "REPORT_MATERIALIZATION_READINESS",
        "PRESENTATION_INTEGRITY_READINESS",
        "CANDIDATE_FREEZE",
    ]


def test_complete_synthetic_pipeline_passes_and_is_deterministic():
    a = run()
    b = run()
    assert a.status == "PASS"
    assert a.stopped_at is None
    assert len(a.stages) == 8
    assert a.candidate_fingerprint == b.candidate_fingerprint
    assert [x.evidence_fingerprint for x in a.stages] == [x.evidence_fingerprint for x in b.stages]


@pytest.mark.parametrize(
    "failed_stage",
    [
        "ONBOARDING_BOOTSTRAP",
        "IDENTITY_JURISDICTION",
        "SOURCE_ADAPTER_READINESS",
        "CORPUS_ADMISSION_READINESS",
        "EVIDENCE_PASSPORT_READINESS",
        "REPORT_MATERIALIZATION_READINESS",
        "PRESENTATION_INTEGRITY_READINESS",
        "CANDIDATE_FREEZE",
    ],
)
def test_failure_at_any_stage_stops_pipeline_and_prevents_candidate_freeze(failed_stage):
    inputs = good_inputs()
    original = inputs[failed_stage]
    inputs[failed_stage] = StageInput(
        stage_id=failed_stage,
        checks={"required_contracts_present": True, "stage_specific_validation": False},
        evidence=original.evidence,
    )
    result = run(inputs)
    assert result.status == "FAIL"
    assert result.stopped_at == failed_stage
    assert result.candidate_fingerprint is None
    executed = [x.stage_id for x in result.stages]
    assert executed[-1] == failed_stage
    full = [x["id"] for x in registry()["stages"]]
    assert len(executed) == full.index(failed_stage) + 1


def test_missing_stage_input_fails_before_execution():
    inputs = good_inputs()
    del inputs["REPORT_MATERIALIZATION_READINESS"]
    with pytest.raises(ValueError, match="coverage mismatch"):
        run(inputs)


def test_extra_stage_input_fails_before_execution():
    inputs = good_inputs()
    inputs["UNCONTROLLED_STAGE"] = StageInput(
        stage_id="UNCONTROLLED_STAGE",
        checks={"x": True},
        evidence={"x": "y"},
    )
    with pytest.raises(ValueError, match="coverage mismatch"):
        run(inputs)


def test_stage_identity_mismatch_fails_closed():
    inputs = good_inputs()
    inputs["SOURCE_ADAPTER_READINESS"] = StageInput(
        stage_id="WRONG_STAGE",
        checks={"x": True},
        evidence={"x": "y"},
    )
    with pytest.raises(ValueError, match="stage identity mismatch"):
        run(inputs)


def test_checks_and_evidence_are_required():
    inputs = good_inputs()
    inputs["CORPUS_ADMISSION_READINESS"] = StageInput(
        stage_id="CORPUS_ADMISSION_READINESS",
        checks={},
        evidence={"x": "y"},
    )
    with pytest.raises(ValueError, match="checks required"):
        run(inputs)

    inputs = good_inputs()
    inputs["CORPUS_ADMISSION_READINESS"] = StageInput(
        stage_id="CORPUS_ADMISSION_READINESS",
        checks={"x": True},
        evidence={},
    )
    with pytest.raises(ValueError, match="evidence required"):
        run(inputs)


def test_san_tan_heights_cannot_be_used_as_new_community_target():
    with pytest.raises(ValueError, match="protected community identity"):
        execute_progressive_pipeline(
            community_id="SAN_TAN_HEIGHTS",
            onboarding_bootstrap_fingerprint="a" * 64,
            stage_inputs=good_inputs(),
            registry=registry(),
        )


def test_protected_default_leakage_fails_closed():
    inputs = good_inputs()
    inputs["REPORT_MATERIALIZATION_READINESS"] = StageInput(
        stage_id="REPORT_MATERIALIZATION_READINESS",
        checks={"x": True},
        evidence={"community": "San Tan Heights"},
    )
    with pytest.raises(ValueError, match="protected default leakage"):
        run(inputs)


def test_failed_boolean_must_be_literal_true():
    inputs = good_inputs()
    inputs["IDENTITY_JURISDICTION"] = StageInput(
        stage_id="IDENTITY_JURISDICTION",
        checks={"required_contracts_present": 1, "stage_specific_validation": True},
        evidence={"manifest": "SYNTH-ID", "fingerprint": "b" * 64},
    )
    result = run(inputs)
    assert result.status == "FAIL"
    assert result.stopped_at == "IDENTITY_JURISDICTION"
