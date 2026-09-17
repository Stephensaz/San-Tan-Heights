from pathlib import Path
from uuid import UUID, uuid4
import pytest
from src.release.policy import ReleasePolicyRegistry
from src.release.membership import ReleaseCandidate, ReleaseScope, DeterministicMembershipResolver
ROOT=Path(__file__).resolve().parents[3]

def policy(): return ReleasePolicyRegistry.from_repository(ROOT).get('STANDARD_FLEET')

def test_membership_is_deterministic_and_fingerprint_ignores_input_order_and_targets():
    a,b=UUID(int=1),UUID(int=2)
    c1=ReleaseCandidate(b,'PUBLIC','WEB',target_report_id=uuid4(),target_semantic_fingerprint='a'*64)
    c2=ReleaseCandidate(a,'AGENT',None,target_snapshot_id=uuid4(),target_semantic_fingerprint='b'*64)
    r=DeterministicMembershipResolver()
    x=r.resolve(candidates=[c1,c2],policy=policy()); y=r.resolve(candidates=[c2,c1],policy=policy())
    assert [m.candidate.property_id for m in x.members]==[a,b]
    assert [m.membership_ordinal for m in x.members]==[1,2]
    assert x.membership_fingerprint==y.membership_fingerprint
    changed=ReleaseCandidate(b,'PUBLIC','WEB',target_report_id=uuid4(),target_semantic_fingerprint='c'*64)
    z=r.resolve(candidates=[changed,c2],policy=policy())
    assert z.membership_fingerprint==x.membership_fingerprint

def test_membership_scope_filters_exactly_and_conflicting_duplicate_fails_closed():
    p1,p2=uuid4(),uuid4(); r=DeterministicMembershipResolver()
    out=r.resolve(candidates=[ReleaseCandidate(p1,'PUBLIC','WEB'),ReleaseCandidate(p2,'SELLER','PRINT')],policy=policy(),scope=ReleaseScope(property_ids=frozenset({p1}),variants=frozenset({'PUBLIC'}),channels=frozenset({'WEB'})))
    assert len(out.members)==1 and out.members[0].candidate.property_id==p1
    with pytest.raises(ValueError,match='conflicting duplicate'):
        r.resolve(candidates=[ReleaseCandidate(p1,'PUBLIC','WEB',target_report_id=uuid4()),ReleaseCandidate(p1,'PUBLIC','WEB',target_report_id=uuid4())],policy=policy())
