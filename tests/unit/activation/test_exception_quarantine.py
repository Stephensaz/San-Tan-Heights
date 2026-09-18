import pytest
import yaml

from src.activation.exception_quarantine import (
    audit_exception_ledger,
    evaluate_exception,
    validate_exception_accounting,
    validate_repair_replay,
)


def policy():
    return yaml.safe_load(open("registries/activation/m9-008-exception-quarantine-v1.0.yaml"))


def frontage(state="QUARANTINED", **extra):
    r = {
        "exception_id": "EX-516018120-FRONTAGE",
        "canonical_property_id": "STH-516018120",
        "scope_type": "FIELD",
        "scope_key": "frontage",
        "exception_class": "KNOWN_PARTIAL_FRONTAGE",
        "reason_code": "FRONTAGE_EVIDENCE_UNRESOLVED",
        "severity": "MATERIAL",
        "repair_state": state,
        "owning_layer": "M9-003",
        "source_fingerprint": "a" * 64,
    }
    r.update(extra)
    return r


def test_known_frontage_is_quarantined_and_not_publishable():
    d = evaluate_exception(frontage(), policy())
    assert d.is_defect is True
    assert d.quarantine_required is True
    assert d.publication_allowed is False
    assert d.substitution_allowed is False


def test_waiver_cannot_make_quarantined_exception_publishable():
    d = evaluate_exception(frontage(waiver_requested=True), policy())
    assert d.publication_allowed is False


def test_stale_context_is_condition_not_automatic_defect():
    r = {
        "exception_id": "EX-STALE-1",
        "canonical_property_id": "STH-1",
        "scope_type": "FINDING",
        "scope_key": "current.competition",
        "exception_class": "CURRENT_CONTEXT_STALE",
        "reason_code": "SOURCE_DATE_EXPIRED",
        "severity": "WARNING",
        "repair_state": "OPEN",
        "owning_layer": "M9-005",
    }
    d = evaluate_exception(r, policy())
    assert d.is_defect is False
    assert d.quarantine_required is False


def test_wrong_owner_fails():
    with pytest.raises(ValueError, match="owning layer"):
        evaluate_exception(frontage(owning_layer="M9-007"), policy())


def test_known_exception_must_remain_accounted_for():
    with pytest.raises(ValueError, match="known governed frontage"):
        audit_exception_ledger([], policy())
    a = audit_exception_ledger([frontage()], policy())
    assert a.known_partial_present is True
    assert a.quarantined == 1


def test_exception_cannot_silently_disappear():
    with pytest.raises(ValueError, match="silently disappeared"):
        validate_exception_accounting([frontage()], [])


def test_superseding_record_preserves_exception_accounting():
    repaired = frontage(
        state="REPLAY_VALIDATED",
        exception_id="EX-516018120-FRONTAGE-R2",
        supersedes_exception_id="EX-516018120-FRONTAGE",
        repair_evidence_fingerprint="b" * 64,
    )
    validate_exception_accounting([frontage()], [repaired])


def test_repair_replay_only_changes_allowed_dependency_chain():
    before = {"binding": "a", "passport": "b", "agent_report": "c", "other_property": "z"}
    after = {"binding": "A", "passport": "B", "agent_report": "C", "other_property": "z"}
    audit = validate_repair_replay(
        "EX-516018120-FRONTAGE",
        ["binding", "passport", "agent_report"],
        before,
        after,
    )
    assert audit.unauthorized_changes == ()
    assert audit.unchanged_dependency_keys == ("other_property",)


def test_repair_replay_rejects_unaffected_fingerprint_change():
    before = {"binding": "a", "passport": "b", "other_property": "z"}
    after = {"binding": "A", "passport": "B", "other_property": "Z"}
    with pytest.raises(ValueError, match="unaffected dependencies"):
        validate_repair_replay(
            "EX-516018120-FRONTAGE",
            ["binding", "passport"],
            before,
            after,
        )
