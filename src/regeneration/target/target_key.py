from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID
from src.shared.hash import sha256_canonical

@dataclass(frozen=True)
class JobTargetContext:
    property_id: UUID
    report_variant: str
    target_snapshot_id: UUID
    report_schema_version: str
    content_contract_version: str
    variant_policy_version: str

class JobTargetKeyEngine:
    def calculate(self, context: JobTargetContext) -> str:
        for field_name in ('report_variant','report_schema_version','content_contract_version','variant_policy_version'):
            if not str(getattr(context,field_name)).strip(): raise ValueError(f'{field_name} is required')
        return sha256_canonical({
            'property_id':str(context.property_id),
            'report_variant':context.report_variant,
            'target_snapshot_id':str(context.target_snapshot_id),
            'report_schema_version':context.report_schema_version,
            'content_contract_version':context.content_contract_version,
            'variant_policy_version':context.variant_policy_version,
        })
