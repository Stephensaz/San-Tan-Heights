from pathlib import Path
from src.certification import ScenarioRegistry,HardZeroMetricRegistry,SyntheticFleetGenerator,GoldenFixtureFramework,HardZeroMetricEngine,CertificationRunner
ROOT=Path(__file__).resolve().parents[3]
def test_synthetic_fleet_is_reproducible():
    g=SyntheticFleetGenerator(); a=g.generate(100); b=g.generate(100); assert a==b; assert g.fingerprint(a)==g.fingerprint(b)
def test_golden_fixture_compares_canonical_payloads():
    f=GoldenFixtureFramework(); x=f.create('x',{'a':1},{'b':[2,1]}); assert f.verify(x,{'b':[2,1]})
def test_hard_zero_metric_engine_fails_nonzero():
    r=HardZeroMetricRegistry.from_repository(ROOT); e=HardZeroMetricEngine(r); rows=e.evaluate({'unauthorized_data_exposure':1}); assert next(x for x in rows if x.metric_id=='unauthorized_data_exposure').status=='FAIL'
def test_certification_runner_requires_all_scenarios_and_zero_metrics():
    sr=ScenarioRegistry.from_repository(ROOT); mr=HardZeroMetricRegistry.from_repository(ROOT); run=CertificationRunner(sr,HardZeroMetricEngine(mr))
    fp=run.candidate_fingerprint(candidate_version='x',contract_versions={'a':'1'},registry_versions={'b':'1'},artifact_hashes=['a'*64])
    v=run.run(candidate_version='x',candidate_fingerprint=fp,scenario_executor=lambda sid:{'pass':True},observed_metrics={})
    assert v.verdict=='GO'
    v2=run.run(candidate_version='x',candidate_fingerprint=fp,scenario_executor=lambda sid:{'pass':True},observed_metrics={'unauthorized_data_exposure':1})
    assert v2.verdict=='NO_GO'
