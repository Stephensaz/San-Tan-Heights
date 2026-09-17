from .models import IntegrityFinding
class OrphanDetector:
    def detect(self, artifacts):
        out=[]
        for a in artifacts:
            if a.get('state')!='READY': continue
            if a.get('referenced'): continue
            kind=a['kind']
            rule='ORPHAN_READY_REPORT' if kind=='REPORT' else 'ORPHAN_READY_RENDER'
            out.append(IntegrityFinding(rule,kind.lower(),a['id'],'FAIL','READY artifact has no governed reference'))
        return tuple(out)
