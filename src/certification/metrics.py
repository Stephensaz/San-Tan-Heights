from dataclasses import dataclass
@dataclass(frozen=True)
class MetricResult:
    metric_id:str; observed_value:int; maximum_allowed:int; status:str
class HardZeroMetricEngine:
    def __init__(self,registry): self.registry=registry
    def evaluate(self,observed):
        unknown=set(observed)-set(self.registry.metrics)
        if unknown: raise ValueError(f'unknown hard-zero metrics: {sorted(unknown)}')
        out=[]
        for mid in self.registry.ids:
            val=int(observed.get(mid,0)); maxv=int(self.registry.metrics[mid]['maximum'])
            out.append(MetricResult(mid,val,maxv,'PASS' if val<=maxv else 'FAIL'))
        return tuple(out)
