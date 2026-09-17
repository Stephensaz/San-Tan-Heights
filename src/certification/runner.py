from dataclasses import dataclass
from hashlib import sha256
from uuid import uuid4
from src.shared.canonical_json import canonical_json
@dataclass(frozen=True)
class CertificationVerdict:
    certification_run_id:object; candidate_version:str; candidate_fingerprint:str; verdict:str; scenario_results:tuple; metric_results:tuple
class CertificationRunner:
    def __init__(self,scenario_registry,metric_engine): self.scenarios=scenario_registry; self.metrics=metric_engine
    def candidate_fingerprint(self, *, candidate_version, contract_versions, registry_versions, artifact_hashes):
        return sha256(canonical_json({'candidate_version':candidate_version,'contract_versions':contract_versions,'registry_versions':registry_versions,'artifact_hashes':artifact_hashes}, set_like_paths=('/artifact_hashes',)).encode()).hexdigest()
    def run(self, *, candidate_version, candidate_fingerprint, scenario_executor, observed_metrics):
        results=[]
        for sid in self.scenarios.ids:
            try:
                detail=scenario_executor(sid)
                status='PASS' if detail.get('pass') is True else 'FAIL'
            except Exception as exc:
                detail={'error':type(exc).__name__}; status='ERROR'
            evidence=sha256(canonical_json({'scenario_id':sid,'status':status,'detail':detail}).encode()).hexdigest()
            results.append((sid,status,evidence,detail))
        metric_results=self.metrics.evaluate(observed_metrics)
        all_scenarios=all(r[1]=='PASS' for r in results)
        hard_zero=all(r.status=='PASS' for r in metric_results)
        return CertificationVerdict(uuid4(),candidate_version,candidate_fingerprint,'GO' if all_scenarios and hard_zero else 'NO_GO',tuple(results),metric_results)
