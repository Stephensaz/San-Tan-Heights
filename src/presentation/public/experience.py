from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from src.shared.canonical_json import canonical_json


@dataclass(frozen=True)
class PublicFindingView:
    finding_id: str
    finding_type: str
    label: str
    display_text: str
    status_label: str | None
    confidence_label: str | None
    limitation: str | None


@dataclass(frozen=True)
class PublicCardView:
    card_id: str
    card_type: str
    title: str
    body: str | None
    status_label: str | None
    findings: tuple[PublicFindingView, ...]


@dataclass(frozen=True)
class PublicSectionView:
    section_id: str
    title: str
    summary: str | None
    cards: tuple[PublicCardView, ...]


@dataclass(frozen=True)
class PublicReportView:
    property_id: str
    address: str
    community: str
    phase: str | None
    builder: str | None
    floor_plan: str | None
    verified_through: str
    market_data_through: str | None
    builder_data_through: str | None
    summary: tuple[str, ...]
    sections: tuple[PublicSectionView, ...]
    disclaimers: tuple[str, ...]

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "property_id": self.property_id,
            "address": self.address,
            "community": self.community,
            "phase": self.phase,
            "builder": self.builder,
            "floor_plan": self.floor_plan,
            "verified_through": self.verified_through,
            "market_data_through": self.market_data_through,
            "builder_data_through": self.builder_data_through,
            "summary": list(self.summary),
            "sections": [
                {
                    "section_id": section.section_id,
                    "title": section.title,
                    "summary": section.summary,
                    "cards": [
                        {
                            "card_id": card.card_id,
                            "card_type": card.card_type,
                            "title": card.title,
                            "body": card.body,
                            "status_label": card.status_label,
                            "findings": [finding.__dict__ for finding in card.findings],
                        }
                        for card in section.cards
                    ],
                }
                for section in self.sections
            ],
            "disclaimers": list(self.disclaimers),
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class PublicReportExperience:
    """Projection of an already-governed PUBLIC canonical report into public UI data."""

    def build(self, payload: dict[str, Any]) -> PublicReportView:
        metadata = payload.get("metadata") or {}
        if metadata.get("report_variant") != "PUBLIC":
            raise ValueError("PublicReportExperience requires a PUBLIC report payload")

        identity = payload.get("property_identity") or {}
        required_text = {
            "property_id": identity.get("property_id"),
            "address": identity.get("address"),
            "community": identity.get("community"),
            "verified_through": metadata.get("verified_through"),
        }
        missing = sorted(key for key, value in required_text.items() if not isinstance(value, str) or not value.strip())
        if missing:
            raise ValueError(f"missing required Public report fields: {missing}")

        findings_by_id: dict[str, dict[str, Any]] = {}
        for finding in payload.get("findings") or []:
            fid = str(finding.get("finding_id") or "")
            if not fid or fid in findings_by_id:
                raise ValueError("Public report finding IDs must be nonempty and unique")
            findings_by_id[fid] = finding

        cards_by_id: dict[str, dict[str, Any]] = {}
        for card in payload.get("cards") or []:
            cid = str(card.get("card_id") or "")
            if not cid or cid in cards_by_id:
                raise ValueError("Public report card IDs must be nonempty and unique")
            cards_by_id[cid] = card

        section_views: list[PublicSectionView] = []
        seen_sections: set[str] = set()
        last_order = 0
        for section in payload.get("sections") or []:
            sid = str(section.get("section_id") or "")
            order = int(section.get("order") or 0)
            if not sid or sid in seen_sections:
                raise ValueError("Public report section IDs must be nonempty and unique")
            if order <= last_order:
                raise ValueError("Public report sections must preserve canonical ascending order")
            seen_sections.add(sid)
            last_order = order

            card_views: list[PublicCardView] = []
            for card_id in section.get("card_ids") or []:
                if card_id not in cards_by_id:
                    raise ValueError(f"Public report section references unknown card: {card_id}")
                card = cards_by_id[card_id]
                if card.get("section_id") != sid:
                    raise ValueError(f"Public report card belongs to a different section: {card_id}")

                finding_views: list[PublicFindingView] = []
                for finding_id in card.get("finding_ids") or []:
                    if finding_id not in findings_by_id:
                        raise ValueError(f"Public report card references unknown finding: {finding_id}")
                    finding = findings_by_id[finding_id]
                    if finding.get("section_id") != sid:
                        raise ValueError(f"Public report finding belongs to a different section: {finding_id}")
                    finding_views.append(
                        PublicFindingView(
                            finding_id=str(finding["finding_id"]),
                            finding_type=str(finding["finding_type"]),
                            label=str(finding["label"]),
                            display_text=str(finding["display_text"]),
                            status_label=finding.get("status_label"),
                            confidence_label=finding.get("confidence_label"),
                            limitation=finding.get("limitation"),
                        )
                    )

                card_views.append(
                    PublicCardView(
                        card_id=str(card["card_id"]),
                        card_type=str(card["card_type"]),
                        title=str(card["title"]),
                        body=card.get("body"),
                        status_label=card.get("status_label"),
                        findings=tuple(finding_views),
                    )
                )

            section_views.append(
                PublicSectionView(
                    section_id=sid,
                    title=str(section.get("title") or sid),
                    summary=section.get("summary"),
                    cards=tuple(card_views),
                )
            )

        return PublicReportView(
            property_id=str(identity["property_id"]),
            address=str(identity["address"]),
            community=str(identity["community"]),
            phase=identity.get("phase"),
            builder=identity.get("builder"),
            floor_plan=identity.get("floor_plan"),
            verified_through=str(metadata["verified_through"]),
            market_data_through=metadata.get("market_data_through"),
            builder_data_through=metadata.get("builder_data_through"),
            summary=tuple(str(item) for item in (payload.get("summary") or [])),
            sections=tuple(section_views),
            disclaimers=tuple(str(item) for item in (payload.get("disclaimers") or [])),
        )
