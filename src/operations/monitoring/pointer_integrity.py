from .models import IntegrityFinding
class PublicationPointerIntegritySweep:
    def evaluate(self, pointers):
        findings=[]
        for p in pointers:
            if not p.get('report_exists',False): findings.append(IntegrityFinding('POINTER_REPORT_EXISTS','publication_pointer',p['pointer_id'],'FAIL','current report target missing'))
            if p.get('channel') and not p.get('render_exists',False): findings.append(IntegrityFinding('POINTER_RENDER_EXISTS','publication_pointer',p['pointer_id'],'FAIL','current render target missing'))
            if p.get('channel') and p.get('render_exists') and p.get('render_report_id')!=p.get('report_id'): findings.append(IntegrityFinding('POINTER_RENDER_REPORT_MATCH','publication_pointer',p['pointer_id'],'FAIL','render belongs to another report'))
        return tuple(findings)
