from copy import deepcopy

import pytest

from src.activation.full_corpus_qa import (
    audit_full_corpus_qa,
    load_full_corpus_inputs,
    run_repository_full_corpus_qa,
)


def repo_inputs():
    return load_full_corpus_inputs(".")


def test_repository_full_corpus_qa_passes():
    audit = run_repository_full_corpus_qa(".")
    assert audit.corpus_members == 4956
    assert audit.report_variants == 14868
    assert audit.production_findings == 37846
    assert audit.publication_decisions == 151384
    assert audit.partial_property_ids == ("STH-516018120",)
    assert audit.unclassified_exceptions == 0
    assert audit.tier_leakage_violations == 0
    assert audit.unauthorized_publications == 0
    assert audit.lineage_gaps == 0
    assert audit.coverage_gaps == 0
    assert audit.waivers == 0


def test_qa_fingerprint_is_deterministic():
    a = run_repository_full_corpus_qa(".")
    b = run_repository_full_corpus_qa(".")
    assert a.qa_fingerprint == b.qa_fingerprint


def test_membership_drift_fails():
    registries, exception_evidence = repo_inputs()
    mutated = deepcopy(registries)
    mutated["binding"]["population"]["row_count"] = 4955
    with pytest.raises(ValueError, match="full-corpus coverage drift"):
        audit_full_corpus_qa(mutated, exception_evidence)


def test_partial_property_lineage_mismatch_fails():
    registries, exception_evidence = repo_inputs()
    mutated = deepcopy(registries)
    mutated["current"]["property_population"]["unavailable_property_ids"] = ["STH-OTHER"]
    with pytest.raises(ValueError, match="partial/unavailable property lineage mismatch"):
        audit_full_corpus_qa(mutated, exception_evidence)


def test_historical_accounting_mismatch_fails():
    registries, exception_evidence = repo_inputs()
    mutated = deepcopy(registries)
    mutated["history"]["population"]["unresolved_listing_records_non_promoted"] = 154
    with pytest.raises(ValueError, match="listing-record accounting"):
        audit_full_corpus_qa(mutated, exception_evidence)


def test_tier_leakage_fails():
    registries, exception_evidence = repo_inputs()
    mutated = deepcopy(registries)
    mutated["reports"]["tier_isolation"]["monotonicity_violations"] = 1
    with pytest.raises(ValueError, match="tier leakage"):
        audit_full_corpus_qa(mutated, exception_evidence)


def test_stale_current_display_fails():
    registries, exception_evidence = repo_inputs()
    mutated = deepcopy(registries)
    mutated["reports"]["displayed_findings"]["stale_current_competition_displayed"] = 1
    with pytest.raises(ValueError, match="stale current competition displayed"):
        audit_full_corpus_qa(mutated, exception_evidence)


def test_publication_before_m9_010_fails():
    registries, exception_evidence = repo_inputs()
    mutated = deepcopy(registries)
    mutated["reports"]["publication_state"]["public_delivery_activated"] = True
    with pytest.raises(ValueError, match="publication activated before M9-010"):
        audit_full_corpus_qa(mutated, exception_evidence)


def test_waiver_fails():
    registries, exception_evidence = repo_inputs()
    evidence = deepcopy(exception_evidence)
    evidence["waivers"] = 1
    with pytest.raises(ValueError, match="waivers are prohibited"):
        audit_full_corpus_qa(registries, evidence)
