from pathlib import Path
from src.certification import ScenarioRegistry,HardZeroMetricRegistry,HardZeroMetricEngine,CertificationRunner,SyntheticFleetGenerator
from src.certification.scenario_checks import CHECKS
ROOT=Path(__file__).resolve().parents[3]
def test_m6_033_hard_zero_metrics_are_unwaivable():
    engine=HardZeroMetricEngine(HardZeroMetricRegistry.from_repository(ROOT))
    assert all(x.status=='PASS' for x in engine.evaluate({}))
    assert any(x.status=='FAIL' for x in engine.evaluate({'publication_pointer_partial_swap':1}))
def test_m6_034_certification_runner_freezes_candidate_identity_and_runs_all_scenarios():
    sr=ScenarioRegistry.from_repository(ROOT); runner=CertificationRunner(sr,HardZeroMetricEngine(HardZeroMetricRegistry.from_repository(ROOT)))
    fleet=SyntheticFleetGenerator().generate(4956)
    fleet_hash=SyntheticFleetGenerator().fingerprint(fleet)
    fp=runner.candidate_fingerprint(candidate_version='0.1.x',contract_versions={'security':'1.0.0','certification':'1.0.0'},registry_versions={'scenarios':'1.0.0'},artifact_hashes=[fleet_hash])
    verdict=runner.run(candidate_version='0.1.x',candidate_fingerprint=fp,scenario_executor=lambda sid: CHECKS[sid](),observed_metrics={})
    assert verdict.verdict=='GO'; assert len(verdict.scenario_results)==len(sr.ids)
def test_m6_035_any_scenario_or_hard_zero_failure_is_no_go():
    sr=ScenarioRegistry.from_repository(ROOT); runner=CertificationRunner(sr,HardZeroMetricEngine(HardZeroMetricRegistry.from_repository(ROOT)))
    fp='a'*64
    bad=runner.run(candidate_version='x',candidate_fingerprint=fp,scenario_executor=lambda sid:{'pass': sid!='PUBLICATION_RACE'},observed_metrics={})
    assert bad.verdict=='NO_GO'
    bad2=runner.run(candidate_version='x',candidate_fingerprint=fp,scenario_executor=lambda sid:{'pass':True},observed_metrics={'negative_field_leakage':1})
    assert bad2.verdict=='NO_GO'
