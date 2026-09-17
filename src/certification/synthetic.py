from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID
from src.shared.canonical_json import canonical_json
@dataclass(frozen=True)
class SyntheticProperty:
    ordinal:int; property_id:UUID; variant_fingerprints:dict; dependency_fingerprint:str
class SyntheticFleetGenerator:
    def __init__(self, seed='STH-SYNTHETIC-v1'): self.seed=seed
    def _uuid(self,i):
        h=sha256(f'{self.seed}:property:{i}'.encode()).hexdigest()
        return UUID(h[:32])
    def generate(self,count:int):
        if count<=0: raise ValueError('count must be positive')
        rows=[]
        for i in range(count):
            pid=self._uuid(i)
            fps={v:sha256(f'{self.seed}:{i}:{v}'.encode()).hexdigest() for v in ('AGENT','SELLER','PUBLIC')}
            dep=sha256(f'{self.seed}:{i}:dependency'.encode()).hexdigest()
            rows.append(SyntheticProperty(i,pid,fps,dep))
        return tuple(rows)
    def fingerprint(self,fleet):
        return sha256(canonical_json([{'ordinal':x.ordinal,'property_id':str(x.property_id),'variant_fingerprints':x.variant_fingerprints,'dependency_fingerprint':x.dependency_fingerprint} for x in fleet]).encode()).hexdigest()
