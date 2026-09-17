from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml
@dataclass(frozen=True)
class RetryDecision:
    action: str; rule_id: str; registry_version: str; delay_seconds: int|None
class RetryPolicy:
    def __init__(self,raw): self.raw=raw; self.version=str(raw['version']); self.rules={r['failure_code']:r for r in raw['rules']}; self.default=raw['default_action']; self.base=int(raw['base_delay_seconds']); self.maximum=int(raw['max_delay_seconds'])
    @classmethod
    def from_repository(cls,root: Path):
        raw=yaml.safe_load((root/'registries/regeneration/retry-policy.yaml').read_text())
        if raw.get('registry_id')!='STH-REGENERATION-RETRY-v1.0': raise ValueError('unexpected retry registry')
        if raw.get('default_action') not in {'BLOCK','FAIL'}: raise ValueError('retry policy must fail closed')
        seen=set()
        for r in raw.get('rules',[]):
            if r['failure_code'] in seen: raise ValueError('duplicate retry failure code')
            seen.add(r['failure_code'])
            if r['action'] not in {'RETRY','BLOCK','FAIL'}: raise ValueError('invalid retry action')
        return cls(raw)
    def classify(self,failure_code: str,attempt_count: int,max_attempts: int) -> RetryDecision:
        rule=self.rules.get(failure_code); action=rule['action'] if rule else self.default; rid=rule['rule_id'] if rule else 'RETRY_DEFAULT_FAIL_CLOSED'
        if action=='RETRY' and attempt_count>=max_attempts: return RetryDecision('FAIL','RETRY_ATTEMPTS_EXHAUSTED',self.version,None)
        delay=min(self.maximum,self.base*(2**max(0,attempt_count-1))) if action=='RETRY' else None
        return RetryDecision(action,rid,self.version,delay)
