from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Iterable


class RenderAdapterError(ValueError):
    pass


@dataclass(frozen=True)
class RenderedArtifact:
    render_type: str
    mime_type: str
    artifact_bytes: bytes
    artifact_hash: str
    artifact_size_bytes: int


def build_artifact(render_type: str, mime_type: str, payload: bytes) -> RenderedArtifact:
    if not payload:
        raise RenderAdapterError('rendered artifact cannot be empty')
    return RenderedArtifact(render_type, mime_type, payload, sha256(payload).hexdigest(), len(payload))


def validate_request_payload(request: Any, canonical_payload: dict, expected_type: str) -> None:
    if request.render_type != expected_type:
        raise RenderAdapterError(f'{expected_type} adapter cannot render {request.render_type}')
    metadata = canonical_payload.get('metadata') or {}
    identity = canonical_payload.get('property_identity') or {}
    if str(metadata.get('property_id')) != str(request.property_id):
        raise RenderAdapterError('render request property does not match canonical payload')
    if str(identity.get('property_id')) != str(request.property_id):
        raise RenderAdapterError('property identity does not match render request')


def governed_text_lines(canonical_payload: dict) -> tuple[str, ...]:
    """Flatten only governed consumer-facing text already present in the canonical report.

    This helper deliberately performs no inference, rewriting, scoring, or fact creation.
    """
    identity = canonical_payload['property_identity']
    out: list[str] = [str(identity['address']), str(identity['community'])]
    for item in canonical_payload.get('summary', ()): out.append(str(item))

    findings = {f['finding_id']: f for f in canonical_payload.get('findings', ())}
    cards = {c['card_id']: c for c in canonical_payload.get('cards', ())}
    for section in sorted(canonical_payload.get('sections', ()), key=lambda s: s['order']):
        out.append(str(section['title']))
        if section.get('summary'): out.append(str(section['summary']))
        for cid in section.get('card_ids', ()):
            card = cards.get(cid)
            if not card: continue
            out.append(str(card['title']))
            if card.get('body'): out.append(str(card['body']))
            if card.get('status_label'): out.append(str(card['status_label']))
            for fid in card.get('finding_ids', ()):
                finding = findings.get(fid)
                if not finding: continue
                out.append(str(finding['label']))
                out.append(str(finding['display_text']))
                if finding.get('status_label'): out.append(str(finding['status_label']))
                if finding.get('confidence_label'): out.append(str(finding['confidence_label']))
                if finding.get('limitation'): out.append(str(finding['limitation']))

    for g in canonical_payload.get('glossary', ()):
        out.extend((str(g['label']), str(g['definition'])))
    for d in canonical_payload.get('disclaimers', ()): out.append(str(d))
    return tuple(x for x in out if x)
