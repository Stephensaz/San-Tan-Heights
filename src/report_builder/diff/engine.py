from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from src.shared.hash import sha256_canonical

@dataclass(frozen=True)
class ReportSemanticDiff:
    changed: bool
    changed_paths: tuple[str, ...]
    categories: tuple[str, ...]
    diff_hash: str
    payload: dict[str, Any]

class ReportSemanticDiffEngine:
    """Deterministic semantic diff that ignores snapshot/verification lineage noise."""
    _META_IGNORED={'snapshot_id','verified_through','market_data_through','builder_data_through'}
    def projection(self,payload: dict[str,Any]) -> dict[str,Any]:
        p={k:v for k,v in payload.items() if k!='lineage'}
        meta=dict(p.get('metadata') or {})
        for k in self._META_IGNORED: meta.pop(k,None)
        p['metadata']=meta
        findings=[]
        for f in p.get('findings',[]):
            x=dict(f); x.pop('source_snapshot_id',None); findings.append(x)
        p['findings']=findings
        return p
    def compare(self,old_payload: dict[str,Any],new_payload: dict[str,Any]) -> ReportSemanticDiff:
        old=self.projection(old_payload); new=self.projection(new_payload); paths=[]
        self._walk(old,new,'',paths)
        paths=tuple(sorted(paths)); cats=tuple(sorted({self._category(x) for x in paths}))
        body={'changed_paths':list(paths),'categories':list(cats)}
        return ReportSemanticDiff(bool(paths),paths,cats,sha256_canonical(body),body)
    def _walk(self,a,b,path,out):
        if type(a) is not type(b): out.append(path or '/'); return
        if isinstance(a,dict):
            for k in sorted(set(a)|set(b)):
                p=f'{path}/{k}'
                if k not in a or k not in b: out.append(p)
                else: self._walk(a[k],b[k],p,out)
        elif isinstance(a,list):
            if a!=b: out.append(path or '/')
        elif a!=b: out.append(path or '/')
    @staticmethod
    def _category(path:str)->str:
        top=path.strip('/').split('/',1)[0] if path.strip('/') else 'root'
        return {'findings':'FINDING','cards':'CARD','sections':'SECTION','summary':'SUMMARY','glossary':'GLOSSARY','disclaimers':'DISCLAIMER','property_identity':'PROPERTY_IDENTITY','branding_reference':'BRANDING','metadata':'CONTRACT'}.get(top,'OTHER')
