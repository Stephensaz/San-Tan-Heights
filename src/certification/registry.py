from pathlib import Path
import yaml
class CertificationRegistryError(ValueError): pass
class ScenarioRegistry:
    def __init__(self, raw): self.raw=raw; self.scenarios=raw['scenarios']
    @classmethod
    def from_repository(cls,root:Path):
        raw=yaml.safe_load((Path(root)/'registries/certification/scenarios-v1.0.yaml').read_text())
        if raw.get('status')!='LOCKED' or not raw.get('scenarios'): raise CertificationRegistryError('locked certification scenarios required')
        return cls(raw)
    def get(self,scenario_id):
        try:return self.scenarios[scenario_id]
        except KeyError as exc: raise CertificationRegistryError(f'unknown scenario: {scenario_id}') from exc
    @property
    def ids(self): return tuple(sorted(self.scenarios))
class HardZeroMetricRegistry:
    def __init__(self,raw): self.raw=raw; self.metrics=raw['metrics']
    @classmethod
    def from_repository(cls,root:Path):
        raw=yaml.safe_load((Path(root)/'registries/certification/hard-zero-metrics-v1.0.yaml').read_text())
        if raw.get('status')!='LOCKED' or not raw.get('metrics'): raise CertificationRegistryError('locked hard-zero metrics required')
        if any(int(v.get('maximum',-1))!=0 for v in raw['metrics'].values()): raise CertificationRegistryError('hard-zero maximums must equal zero')
        return cls(raw)
    @property
    def ids(self): return tuple(sorted(self.metrics))
