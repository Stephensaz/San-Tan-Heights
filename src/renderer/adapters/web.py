from __future__ import annotations
from html import escape
from .common import RenderAdapterError, RenderedArtifact, build_artifact, validate_request_payload


class WebRenderAdapter:
    version = '1.0.0'

    def render(self, *, request, canonical_payload: dict) -> RenderedArtifact:
        validate_request_payload(request, canonical_payload, 'WEB')
        p = canonical_payload
        identity = p['property_identity']
        findings = {f['finding_id']: f for f in p.get('findings', ())}
        cards = {c['card_id']: c for c in p.get('cards', ())}
        parts = [
            '<!doctype html><html lang="en"><head><meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width,initial-scale=1">',
            f'<meta name="sth-report-id" content="{escape(str(request.report_id))}">',
            f'<meta name="sth-presentation-input-hash" content="{request.presentation_input_hash}">',
            f'<title>{escape(identity["address"])}</title></head><body>',
            f'<main data-property-id="{escape(str(request.property_id))}" data-template="{escape(request.profile.template_id)}">',
            f'<header><h1>{escape(identity["address"])}</h1><p>{escape(identity["community"])}</p></header>',
        ]
        if p.get('summary'):
            parts.append('<section id="summary"><ul>')
            parts.extend(f'<li>{escape(str(x))}</li>' for x in p['summary'])
            parts.append('</ul></section>')
        for section in sorted(p.get('sections', ()), key=lambda s: s['order']):
            parts.append(f'<section id="{escape(section["section_id"])}"><h2>{escape(section["title"])}</h2>')
            if section.get('summary'): parts.append(f'<p>{escape(section["summary"])}</p>')
            for cid in section.get('card_ids', ()):
                card = cards.get(cid)
                if not card: continue
                parts.append(f'<article data-card-id="{escape(cid)}"><h3>{escape(card["title"])}</h3>')
                if card.get('body'): parts.append(f'<p>{escape(card["body"])}</p>')
                for fid in card.get('finding_ids', ()):
                    f = findings.get(fid)
                    if not f: continue
                    parts.append(f'<dl data-finding-id="{escape(fid)}"><dt>{escape(f["label"])}</dt><dd>{escape(f["display_text"])}</dd></dl>')
                    if f.get('limitation'): parts.append(f'<p class="limitation">{escape(f["limitation"])}</p>')
                parts.append('</article>')
            parts.append('</section>')
        if p.get('glossary'):
            parts.append('<section id="glossary"><h2>Glossary</h2><dl>')
            for g in p['glossary']:
                parts.append(f'<dt>{escape(g["label"])}</dt><dd>{escape(g["definition"])}</dd>')
            parts.append('</dl></section>')
        for d in p.get('disclaimers', ()):
            parts.append(f'<p class="disclaimer">{escape(str(d))}</p>')
        parts.append('</main></body></html>')
        return build_artifact('WEB', 'text/html', ''.join(parts).encode('utf-8'))
