from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib, json
from pathlib import Path
from typing import Mapping, Sequence
import yaml

def _canonical_json(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def _hash(v): return hashlib.sha256(_canonical_json(v).encode()).hexdigest()

def load_historical_replay_registry(path:str|Path)->dict:
    d=yaml.safe_load(Path(path).read_text())
    if d.get("status")!="FROZEN" or d.get("ticket")!="M13-008":
        raise ValueError("M13-008 historical replay registry must be FROZEN")
    return d

@dataclass(frozen=True)
class HistoricalReplayCase:
    case_id: str
    regime: str
    input_condition: str
    historical_input_fingerprint: str
    expected_output_fingerprint: str|None
    observed_output_fingerprint: str|None
    detector_event_ids: tuple[str,...]
    correction_parent_case_id: str|None
    case_fingerprint: str

@dataclass(frozen=True)
class HistoricalReplayResult:
    case_id: str
    outcome: str
    false_positive: bool
    miss: bool
    duplicated_event_count: int
    churn_count: int
    persistence_preserved: bool
    materiality_stable: bool
    conflict_explicit: bool
    expiration_explicit: bool
    reproducible: bool
    reason: str
    result_fingerprint: str

@dataclass(frozen=True)
class HistoricalReplayReport:
    report_id: str
    results: tuple[HistoricalReplayResult,...]
    false_positive_count: int
    miss_count: int
    duplication_count: int
    churn_count: int
    drift_count: int
    degraded_count: int
    blocked_count: int
    reproducible_count: int
    report_fingerprint: str

def make_replay_case(*,case_id:str,regime:str,input_condition:str,historical_input_fingerprint:str,
    expected_output_fingerprint:str|None,observed_output_fingerprint:str|None,detector_event_ids:Sequence[str]=(),
    correction_parent_case_id:str|None=None)->HistoricalReplayCase:
    if not case_id.strip(): raise ValueError("case id required")
    for name,value in (("historical input",historical_input_fingerprint),):
        if len(value)!=64 or any(c not in "0123456789abcdef" for c in value): raise ValueError(f"{name} fingerprint must be lowercase sha256")
    for name,value in (("expected output",expected_output_fingerprint),("observed output",observed_output_fingerprint)):
        if value is not None and (len(value)!=64 or any(c not in "0123456789abcdef" for c in value)):
            raise ValueError(f"{name} fingerprint must be lowercase sha256")
    events=tuple(sorted(detector_event_ids))
    payload={"case_id":case_id,"regime":regime,"input_condition":input_condition,
      "historical_input_fingerprint":historical_input_fingerprint,"expected_output_fingerprint":expected_output_fingerprint,
      "observed_output_fingerprint":observed_output_fingerprint,"detector_event_ids":events,
      "correction_parent_case_id":correction_parent_case_id}
    return HistoricalReplayCase(**payload,case_fingerprint=_hash(payload))

def evaluate_replay_case(case:HistoricalReplayCase,registry:Mapping[str,object])->HistoricalReplayResult:
    if case.regime not in {"CALM","RAPID_CHANGE"}: raise ValueError("unsupported regime")
    allowed={"NORMAL","INCENTIVE_CHANGE","PRICE_REDUCTION","DUPLICATE","CORRECTED","DELAYED","CONFLICTED","MISSING","STALE"}
    if case.input_condition not in allowed: raise ValueError("unsupported input condition")
    dup=max(0,len(case.detector_event_ids)-len(set(case.detector_event_ids)))
    false_positive=False; miss=False; churn=0; conflict_explicit=True; expiration_explicit=True
    if case.input_condition=="MISSING":
        outcome="DEGRADED"; miss=case.observed_output_fingerprint is None; reason="Missing input remains explicit and replay is degraded."
    elif case.input_condition=="CONFLICTED":
        outcome="BLOCKED"; conflict_explicit=True; reason="Conflicted input is explicit and blocks affected replay."
    elif case.input_condition in {"DELAYED","STALE"}:
        outcome="DEGRADED"; reason="Delayed or stale input remains explicit."
    elif case.input_condition=="DUPLICATE":
        outcome="DEGRADED" if dup else "MATCH"; reason="Duplicate events are measured and must not multiply governed output."
    elif case.expected_output_fingerprint==case.observed_output_fingerprint:
        outcome="MATCH"; reason="Replay reproduced the expected historical output."
    else:
        outcome="DRIFT"; reason="Replay output differs from the certified historical expectation."
    reproducible=case.expected_output_fingerprint is not None and case.expected_output_fingerprint==case.observed_output_fingerprint
    persistence_preserved=not (case.input_condition=="DUPLICATE" and dup>0)
    materiality_stable=outcome!="DRIFT"
    if case.input_condition=="CORRECTED" and not case.correction_parent_case_id:
        raise ValueError("corrected case requires parent case id")
    if case.input_condition=="DUPLICATE" and dup>0:
        churn=dup
    payload={"case_id":case.case_id,"outcome":outcome,"false_positive":false_positive,"miss":miss,
      "duplicated_event_count":dup,"churn_count":churn,"persistence_preserved":persistence_preserved,
      "materiality_stable":materiality_stable,"conflict_explicit":conflict_explicit,
      "expiration_explicit":expiration_explicit,"reproducible":reproducible,"reason":reason}
    return HistoricalReplayResult(**payload,result_fingerprint=_hash(payload))

def build_replay_report(*,report_id:str,cases:Sequence[HistoricalReplayCase],registry:Mapping[str,object])->HistoricalReplayReport:
    if not report_id.strip(): raise ValueError("report id required")
    ordered=tuple(sorted(cases,key=lambda x:x.case_id))
    ids=[x.case_id for x in ordered]
    if len(ids)!=len(set(ids)): raise ValueError("duplicate replay case id")
    by_id={x.case_id:x for x in ordered}
    for c in ordered:
        if c.correction_parent_case_id is not None and c.correction_parent_case_id not in by_id:
            raise ValueError("correction parent case missing")
    results=tuple(evaluate_replay_case(x,registry) for x in ordered)
    counts={
      "false_positive_count":sum(x.false_positive for x in results),
      "miss_count":sum(x.miss for x in results),
      "duplication_count":sum(x.duplicated_event_count for x in results),
      "churn_count":sum(x.churn_count for x in results),
      "drift_count":sum(x.outcome=="DRIFT" for x in results),
      "degraded_count":sum(x.outcome=="DEGRADED" for x in results),
      "blocked_count":sum(x.outcome=="BLOCKED" for x in results),
      "reproducible_count":sum(x.reproducible for x in results),
    }
    payload={"report_id":report_id,"results":tuple(asdict(x) for x in results),**counts}
    return HistoricalReplayReport(**{**payload,"results":results},report_fingerprint=_hash(payload))

def validate_replay_report(value:HistoricalReplayReport,**kwargs)->bool:
    return build_replay_report(**kwargs)==value
