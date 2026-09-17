from __future__ import annotations
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from .common import RenderedArtifact, build_artifact, governed_text_lines, validate_request_payload


def _pdf_bytes(lines, *, pagesize, title: str, producer: str) -> bytes:
    buf = BytesIO()
    c = Canvas(buf, pagesize=pagesize, invariant=1, pageCompression=1)
    c.setTitle(title); c.setAuthor('San Tan Heights Intelligence'); c.setProducer(producer)
    width, height = pagesize
    left, right, top, bottom = 48, 48, 48, 48
    font, size, leading = 'Helvetica', 10, 14
    c.setFont(font, size); y = height - top
    maxw = width-left-right
    for raw in lines:
        words = str(raw).split() or ['']
        row = ''
        wrapped=[]
        for word in words:
            candidate = word if not row else row+' '+word
            if row and stringWidth(candidate,font,size) > maxw:
                wrapped.append(row); row=word
            else: row=candidate
        wrapped.append(row)
        for text in wrapped:
            if y < bottom:
                c.showPage(); c.setFont(font,size); y=height-top
            c.drawString(left,y,text); y -= leading
        y -= 3
    c.save()
    return buf.getvalue()


class PdfRenderAdapter:
    version = '1.0.0'
    def render(self, *, request, canonical_payload: dict) -> RenderedArtifact:
        validate_request_payload(request, canonical_payload, 'PDF')
        data=_pdf_bytes(governed_text_lines(canonical_payload),pagesize=A4,title=canonical_payload['property_identity']['address'],producer='STH PDF Render Adapter 1.0.0')
        return build_artifact('PDF','application/pdf',data)
