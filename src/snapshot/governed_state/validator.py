from __future__ import annotations
import re
from uuid import UUID
from .models import GovernedDependency, GovernedFinding, GovernedPropertyState

HEX64 = re.compile(r'^[0-9a-f]{64}$')
PRODUCTION = {'PRODUCTION_READY','INTERNAL_ONLY','BLOCKED','DEPRECATED','SUPERSEDED'}
PUBLICATION = {'AGENT','SELLER','PUBLIC','AGENT_SELLER','ALL','NONE'}
QA = {'PENDING','PASS','FAIL','REVIEW_REQUIRED'}
IDENTITY = {'RESOLVED','BLOCKED','INVALID'}
VARIANTS = {'AGENT','SELLER','PUBLIC'}
WORDING_KEYS = {'agent','seller','public'}

class GovernedStateValidationError(ValueError):
    pass

def _nonempty(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GovernedStateValidationError(f'{field} is required')
    return value

def _fp(value: object, field: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise GovernedStateValidationError(f'{field} must be lowercase sha256')
    return value

class GovernedStateValidator:
    def validate(self, raw: dict) -> GovernedPropertyState:
        try:
            property_id = UUID(str(raw['property_id']))
        except Exception as exc:
            raise GovernedStateValidationError('property_id must be UUID') from exc
        identity = raw.get('property_identity_status')
        if identity not in IDENTITY: raise GovernedStateValidationError('unknown property_identity_status')
        qa = raw.get('qa_status')
        if qa not in QA: raise GovernedStateValidationError('unknown qa_status')
        findings=[]
        for item in raw.get('findings', []):
            prod=item.get('production_status'); scope=item.get('publication_scope'); fqa=item.get('qa_status')
            if prod not in PRODUCTION: raise GovernedStateValidationError('unknown production_status')
            if scope not in PUBLICATION: raise GovernedStateValidationError('unknown publication_scope')
            if fqa not in QA: raise GovernedStateValidationError('unknown finding qa_status')
            wording=item.get('approved_wording'); versions=item.get('wording_versions')
            if not isinstance(wording,dict) or set(wording) != WORDING_KEYS: raise GovernedStateValidationError('approved_wording must contain agent/seller/public')
            if not isinstance(versions,dict) or set(versions) != WORDING_KEYS: raise GovernedStateValidationError('wording_versions must contain agent/seller/public')
            findings.append(GovernedFinding(
                _nonempty(item.get('finding_id'),'finding_id'), _nonempty(item.get('finding_type'),'finding_type'),
                _nonempty(item.get('passport_id'),'passport_id'), _nonempty(item.get('passport_version'),'passport_version'),
                item.get('canonical_value'), _nonempty(item.get('confidence_code'),'confidence_code'), fqa, prod, scope,
                dict(wording), dict(versions), _fp(item.get('semantic_fingerprint'),'semantic_fingerprint'),
                _fp(item.get('evidence_reference_set_hash'),'evidence_reference_set_hash')))
        deps=[]
        for item in raw.get('dependencies', []):
            scope=tuple(item.get('variant_scope') or ())
            if any(v not in VARIANTS for v in scope) or len(scope) != len(set(scope)):
                raise GovernedStateValidationError('invalid variant_scope')
            if not isinstance(item.get('required'), bool): raise GovernedStateValidationError('dependency required must be boolean')
            deps.append(GovernedDependency(
                _nonempty(item.get('dependency_type'),'dependency_type'), _nonempty(item.get('dependency_id'),'dependency_id'),
                _fp(item.get('semantic_fingerprint'),'dependency semantic_fingerprint'), _fp(item.get('record_fingerprint'),'record_fingerprint'),
                _nonempty(item.get('dependency_version'),'dependency_version'), item['required'], scope))
        return GovernedPropertyState(
            property_id, _nonempty(raw.get('governed_state_version'),'governed_state_version'),
            _nonempty(raw.get('source_read_token'),'source_read_token'),
            _nonempty(raw.get('intelligence_schema_version'),'intelligence_schema_version'),
            _nonempty(raw.get('governance_schema_version'),'governance_schema_version'),
            _nonempty(raw.get('model_version'),'model_version'), identity, qa, tuple(findings), tuple(deps))
