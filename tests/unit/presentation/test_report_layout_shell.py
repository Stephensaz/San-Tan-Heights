import pytest

from src.presentation.components import text
from src.presentation.layout import ReportLayoutShell, ReportSectionSlot


def test_report_shell_composes_canonical_order():
    evidence = ReportSectionSlot("evidence", text("evidence-text", "Evidence"))
    summary = ReportSectionSlot("summary", text("summary-text", "Summary"))
    shell = ReportLayoutShell.compose(property_id="p-1", report_id="r-1", sections=[evidence, summary])
    assert [s.section_key for s in shell.sections] == ["summary", "evidence"]
    assert len(shell.fingerprint) == 64


def test_report_shell_rejects_duplicate_sections():
    slot = ReportSectionSlot("summary", text("summary-text", "Summary"))
    with pytest.raises(ValueError):
        ReportLayoutShell(property_id="p-1", report_id="r-1", sections=(slot, slot))


def test_report_shell_rejects_manual_reordering():
    evidence = ReportSectionSlot("evidence", text("evidence-text", "Evidence"))
    summary = ReportSectionSlot("summary", text("summary-text", "Summary"))
    with pytest.raises(ValueError):
        ReportLayoutShell(property_id="p-1", report_id="r-1", sections=(evidence, summary))


def test_missing_sections_are_not_synthesized():
    shell = ReportLayoutShell.compose(
        property_id="p-1",
        report_id="r-1",
        sections=[ReportSectionSlot("freshness", text("freshness-text", "Current as of source snapshot."))],
    )
    assert [s.section_key for s in shell.sections] == ["freshness"]
