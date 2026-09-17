from dataclasses import dataclass
from hashlib import sha256
from src.shared.canonical_json import canonical_json
@dataclass(frozen=True)
class GoldenFixture:
    fixture_id:str; input_payload:dict; expected_payload:dict; fingerprint:str
class GoldenFixtureFramework:
    def create(self,fixture_id,input_payload,expected_payload):
        fp=sha256(canonical_json({'fixture_id':fixture_id,'input':input_payload,'expected':expected_payload}).encode()).hexdigest()
        return GoldenFixture(fixture_id,input_payload,expected_payload,fp)
    def verify(self,fixture,actual_payload):
        return canonical_json(actual_payload)==canonical_json(fixture.expected_payload)
