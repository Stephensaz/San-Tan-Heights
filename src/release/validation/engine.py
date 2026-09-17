from __future__ import annotations
from dataclasses import dataclass
import json

@dataclass(frozen=True)
class ValidationResult:
    release_item_id:object
    status:str
    reason_code:str|None=None

class ReleaseValidationEngine:
    VERSION='STH-RELEASE-VALIDATOR-v1.0'
    INSERT="""INSERT INTO operations.release_validation_results (release_id,release_item_id,validation_status,reason_code,validator_version,evidence) VALUES (%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT (release_item_id,validator_version) DO NOTHING"""
    def validate_item(self,item):
        if item.target_report_id is None: return ValidationResult(item.release_item_id,'FAIL','TARGET_REPORT_MISSING')
        if not item.target_semantic_fingerprint: return ValidationResult(item.release_item_id,'FAIL','TARGET_SEMANTIC_FINGERPRINT_MISSING')
        if item.channel is not None:
            if item.target_render_id is None:return ValidationResult(item.release_item_id,'FAIL','TARGET_RENDER_MISSING')
            if not item.target_presentation_fingerprint:return ValidationResult(item.release_item_id,'FAIL','TARGET_PRESENTATION_FINGERPRINT_MISSING')
        return ValidationResult(item.release_item_id,'PASS')
    def persist(self,cursor,*,release_id,result,evidence=None):
        cursor.execute(self.INSERT,(release_id,result.release_item_id,result.status,result.reason_code,self.VERSION,json.dumps(evidence or {},sort_keys=True,separators=(',',':'))))
