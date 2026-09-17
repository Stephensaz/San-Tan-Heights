from dataclasses import dataclass
from random import Random
@dataclass(frozen=True)
class ChaosFault:
    ordinal:int; fault_type:str; target:str
class ChaosHarness:
    FAULTS=('DB_RETRYABLE','WORKER_CRASH','STALE_SOURCE','POINTER_SWAP_FAILURE','ARTIFACT_HASH_MISMATCH')
    def __init__(self,seed=20260916): self.seed=seed
    def plan(self,count:int,targets):
        if count<0: raise ValueError('count must be nonnegative')
        targets=tuple(targets)
        if not targets and count: raise ValueError('targets required')
        r=Random(self.seed)
        return tuple(ChaosFault(i,r.choice(self.FAULTS),r.choice(targets)) for i in range(count))
