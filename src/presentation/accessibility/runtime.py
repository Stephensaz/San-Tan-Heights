from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import yaml

from src.presentation.diagram.accessibility import AccessibleDiagramView
from src.presentation.pdf import AgentPdfDocument, PublicPdfDocument, SellerPdfDocument
from src.presentation.printing import PrintTemplatePlan
from src.shared.canonical_json import canonical_json

_EXPECTED_ID = "STH-PRESENTATION-ACCESSIBILITY-v1.0"
_EXPECTED_VERSION = "1.0.0"
_EXPECTED_STATUS = "LOCKED"
_EXPECTED_RULES = {
    "require_nonblank_property_identity_text": True,
    "require_nonblank_section_titles": True,
    "require_nonblank_card_titles": True,
    "require_nonblank_finding_labels": True,
    "require_nonblank_finding_display_text": True,
    "preserve_semantic_order": True,
    "require_print_source_binding": True,
    "require_diagram_short_description": True,
    "require_diagram_long_description": True,
    "require_diagram_nonvisual_equivalent": True,
    "require_accessible_svg_metadata": True,
    "allow_accessibility_specific_property_facts": False,
    "allow_audience_reclassification": False,
    "allow_content_rewriting": False,
}


@dataclass(frozen=True)
class AccessibilityRuntimeRegistry:
    registry_id: str
    version: str
    status: str
    rules: Mapping[str, bool]
    fingerprint: str

    @classmethod
    def load(cls, path: str | Path) -> "AccessibilityRuntimeRegistry":
        raw = yaml.safe_load(Path(path).read_text())
        if not isinstance(raw, dict):
            raise ValueError("accessibility runtime registry must be an object")
        if raw.get("accessibility_runtime_id") != _EXPECTED_ID:
            raise ValueError("unexpected accessibility runtime id")
        if str(raw.get("version")) != _EXPECTED_VERSION:
            raise ValueError("unexpected accessibility runtime version")
        if raw.get("status") != _EXPECTED_STATUS:
            raise ValueError("accessibility runtime registry must be LOCKED")
        if raw.get("rules") != _EXPECTED_RULES:
            raise ValueError("accessibility runtime rules do not match locked contract")
        payload = {
            "accessibility_runtime_id": _EXPECTED_ID,
            "version": _EXPECTED_VERSION,
            "status": _EXPECTED_STATUS,
            "rules": _EXPECTED_RULES,
        }
        return cls(
            registry_id=_EXPECTED_ID,
            version=_EXPECTED_VERSION,
            status=_EXPECTED_STATUS,
            rules=MappingProxyType(dict(_EXPECTED_RULES)),
            fingerprint=sha256(canonical_json(payload).encode("utf-8")).hexdigest(),
        )


@dataclass(frozen=True)
class AccessibilityIssue:
    code: str
    location: str
    message: str

    def canonical_payload(self) -> dict[str, str]:
        return {"code": self.code, "location": self.location, "message": self.message}


@dataclass(frozen=True)
class AccessibilityAudit:
    target_type: str
    target_fingerprint: str
    registry_fingerprint: str
    issues: tuple[AccessibilityIssue, ...]

    @property
    def passed(self) -> bool:
        return not self.issues

    def canonical_payload(self) -> dict[str, object]:
        return {
            "target_type": self.target_type,
            "target_fingerprint": self.target_fingerprint,
            "registry_fingerprint": self.registry_fingerprint,
            "issues": [issue.canonical_payload() for issue in self.issues],
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


PdfDocument = AgentPdfDocument | SellerPdfDocument | PublicPdfDocument


class PresentationAccessibilityRuntime:
    """Fail-closed accessibility audit over already-governed presentation artifacts.

    The runtime validates existing semantic text, order, source binding, and diagram
    equivalents. It never generates property facts, rewrites presentation content,
    or changes audience eligibility.
    """

    def __init__(self, registry: AccessibilityRuntimeRegistry) -> None:
        self.registry = registry

    def audit_pdf(self, document: PdfDocument) -> AccessibilityAudit:
        if not isinstance(document, (AgentPdfDocument, SellerPdfDocument, PublicPdfDocument)):
            raise ValueError("accessibility runtime requires a certified PDF document")
        issues: list[AccessibilityIssue] = []
        self._require_text(document.address, "property.address", "PROPERTY_IDENTITY_TEXT", issues)
        self._require_text(document.community, "property.community", "PROPERTY_IDENTITY_TEXT", issues)
        self._require_text(document.verified_through, "freshness.verified_through", "PROPERTY_IDENTITY_TEXT", issues)

        section_ids = tuple(section.section_id for section in document.sections)
        if section_ids != document.template.semantic_order:
            issues.append(
                AccessibilityIssue(
                    "SEMANTIC_ORDER_MISMATCH",
                    "sections",
                    "section order differs from the certified PDF semantic order",
                )
            )

        for s_index, section in enumerate(document.sections):
            self._require_text(section.title, f"sections[{s_index}].title", "SECTION_TITLE", issues)
            for c_index, card in enumerate(section.cards):
                self._require_text(card.title, f"sections[{s_index}].cards[{c_index}].title", "CARD_TITLE", issues)
                for f_index, finding in enumerate(card.findings):
                    base = f"sections[{s_index}].cards[{c_index}].findings[{f_index}]"
                    self._require_text(finding.label, f"{base}.label", "FINDING_LABEL", issues)
                    self._require_text(
                        finding.display_text,
                        f"{base}.display_text",
                        "FINDING_DISPLAY_TEXT",
                        issues,
                    )

        return self._audit("PDF", document.fingerprint, issues)

    def audit_print(self, document: PdfDocument, plan: PrintTemplatePlan) -> AccessibilityAudit:
        pdf_audit = self.audit_pdf(document)
        issues = list(pdf_audit.issues)
        if plan.source_document_fingerprint != document.fingerprint:
            issues.append(
                AccessibilityIssue(
                    "PRINT_SOURCE_MISMATCH",
                    "print.source_document_fingerprint",
                    "print plan is not bound to the certified PDF document",
                )
            )
        if plan.semantic_order != document.template.semantic_order:
            issues.append(
                AccessibilityIssue(
                    "PRINT_ORDER_MISMATCH",
                    "print.semantic_order",
                    "print semantic order differs from the certified PDF order",
                )
            )
        return self._audit("PRINT", plan.fingerprint, issues)

    def audit_diagram(self, diagram: AccessibleDiagramView) -> AccessibilityAudit:
        if not isinstance(diagram, AccessibleDiagramView):
            raise ValueError("accessibility runtime requires an AccessibleDiagramView")
        issues: list[AccessibilityIssue] = []
        self._require_text(diagram.short_description, "diagram.short_description", "DIAGRAM_SHORT_DESCRIPTION", issues)
        self._require_text(diagram.long_description, "diagram.long_description", "DIAGRAM_LONG_DESCRIPTION", issues)
        if not diagram.nonvisual_equivalent or any(not item.strip() for item in diagram.nonvisual_equivalent):
            issues.append(
                AccessibilityIssue(
                    "DIAGRAM_NONVISUAL_EQUIVALENT",
                    "diagram.nonvisual_equivalent",
                    "diagram requires a complete nonvisual equivalent",
                )
            )
        svg = diagram.accessible_svg
        if "aria-labelledby=" not in svg or "<title " not in svg or "<desc " not in svg:
            issues.append(
                AccessibilityIssue(
                    "DIAGRAM_SVG_METADATA",
                    "diagram.accessible_svg",
                    "accessible SVG requires aria-labelledby, title, and description metadata",
                )
            )
        return self._audit("DIAGRAM", diagram.fingerprint, issues)

    def require_pass(self, audit: AccessibilityAudit) -> None:
        if not audit.passed:
            codes = ", ".join(issue.code for issue in audit.issues)
            raise ValueError(f"accessibility audit failed: {codes}")

    def _audit(self, target_type: str, target_fingerprint: str, issues: list[AccessibilityIssue]) -> AccessibilityAudit:
        ordered = tuple(sorted(issues, key=lambda issue: (issue.location, issue.code, issue.message)))
        return AccessibilityAudit(
            target_type=target_type,
            target_fingerprint=target_fingerprint,
            registry_fingerprint=self.registry.fingerprint,
            issues=ordered,
        )

    @staticmethod
    def _require_text(value: str, location: str, code: str, issues: list[AccessibilityIssue]) -> None:
        if not isinstance(value, str) or not value.strip():
            issues.append(AccessibilityIssue(code, location, "required accessible text is blank"))
