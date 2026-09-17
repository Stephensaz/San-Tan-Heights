from __future__ import annotations
from reportlab.lib.pagesizes import LETTER
from .common import RenderedArtifact, build_artifact, governed_text_lines, validate_request_payload
from .pdf import _pdf_bytes


class PrintRenderAdapter:
    version = '1.0.0'
    def render(self, *, request, canonical_payload: dict) -> RenderedArtifact:
        validate_request_payload(request, canonical_payload, 'PRINT')
        data=_pdf_bytes(governed_text_lines(canonical_payload),pagesize=LETTER,title=canonical_payload['property_identity']['address'],producer='STH PRINT Render Adapter 1.0.0')
        return build_artifact('PRINT','application/pdf',data)
