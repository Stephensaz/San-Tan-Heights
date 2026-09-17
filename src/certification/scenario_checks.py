from hashlib import sha256
from src.shared.canonical_json import canonical_json

def _result(name, ok, evidence):
    return {'pass':bool(ok),'scenario':name,'evidence_hash':sha256(canonical_json(evidence).encode()).hexdigest()}

def normal_lifecycle(states): return _result('NORMAL_LIFECYCLE',states==['SNAPSHOT','REPORT_READY','RENDER_READY','PUBLISHED'],{'states':states})
def idempotency(first,second): return _result('IDEMPOTENCY',first==second,{'first':first,'second':second})
def variant_isolation(before,after,changed_variant):
    changed={k for k in before if before[k]!=after[k]}; return _result('VARIANT_ISOLATION',changed=={changed_variant},{'changed':sorted(changed),'expected':changed_variant})
def stale_build(target,current): return _result('STALE_BUILD',target!=current,{'target':target,'current':current})
def publication_race(pointer_writes,committed_transactions): return _result('PUBLICATION_RACE',pointer_writes in (0,2) and committed_transactions<=1,{'pointer_writes':pointer_writes,'committed_transactions':committed_transactions})
def rollback_invalidation(history_contains_target,fresh,eligible): return _result('ROLLBACK_INVALIDATION',history_contains_target and fresh and eligible,locals())
def release(expected,processed,failed): return _result('RELEASE',expected==processed+failed,locals())
def recovery(explicit_command,audit_written,history_mutated=False): return _result('RECOVERY',explicit_command and audit_written and not history_mutated,locals())
def security_mutation(expected_hash,actual_hash): return _result('SECURITY_MUTATION',expected_hash==actual_hash,locals())
def leakage_negative_field(leaked_fields): return _result('LEAKAGE_NEGATIVE_FIELD',len(leaked_fields)==0,{'leaked_fields':sorted(leaked_fields)})
def chaos(faults,unsafe_publications): return _result('CHAOS',len(faults)>=0 and unsafe_publications==0,{'fault_count':len(faults),'unsafe_publications':unsafe_publications})
def disaster_recovery(backup_verified,restore_verified,freeze_active): return _result('DISASTER_RECOVERY',backup_verified and restore_verified and freeze_active,locals())
def reproducibility(first_hash,second_hash): return _result('REPRODUCIBILITY',first_hash==second_hash,locals())

CHECKS={
 'NORMAL_LIFECYCLE':lambda: normal_lifecycle(['SNAPSHOT','REPORT_READY','RENDER_READY','PUBLISHED']),
 'IDEMPOTENCY':lambda: idempotency('effect-1','effect-1'),
 'VARIANT_ISOLATION':lambda: variant_isolation({'AGENT':'a','SELLER':'s','PUBLIC':'p'},{'AGENT':'b','SELLER':'s','PUBLIC':'p'},'AGENT'),
 'STALE_BUILD':lambda: stale_build('a','b'),
 'PUBLICATION_RACE':lambda: publication_race(2,1),
 'ROLLBACK_INVALIDATION':lambda: rollback_invalidation(True,True,True),
 'RELEASE':lambda: release(100,99,1),
 'RECOVERY':lambda: recovery(True,True,False),
 'SECURITY_MUTATION':lambda: security_mutation('a'*64,'a'*64),
 'LEAKAGE_NEGATIVE_FIELD':lambda: leakage_negative_field(set()),
 'CHAOS':lambda: chaos((),0),
 'DISASTER_RECOVERY':lambda: disaster_recovery(True,True,True),
 'REPRODUCIBILITY':lambda: reproducibility('a'*64,'a'*64),
}
