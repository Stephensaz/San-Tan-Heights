from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml
from src.report_builder.variant.registry import VARIANTS, VariantPolicyRegistry

FALLBACKS = frozenset({'OMIT_IF_EMPTY','SHOW_EMPTY_STATE','BLOCK_IF_REQUIRED'})

class ReportSectionRegistryError(ValueError):
    pass

@dataclass(frozen=True)
class ReportSection:
    section_id: str
    order: int
    allowed_variants: frozenset[str]
    required_by_variant: frozenset[str]
    finding_types: frozenset[str]
    fallback_behavior: str

class ReportSectionRegistry:
    def __init__(self, registry_id: str, version: str, sections: tuple[ReportSection,...]):
        self.registry_id = registry_id
        self.version = version
        self.sections = sections
        self._by_id = {s.section_id:s for s in sections}

    @classmethod
    def from_repository(cls, root: Path) -> 'ReportSectionRegistry':
        root = Path(root)
        path = root/'registries/report-sections/sections.yaml'
        raw = yaml.safe_load(path.read_text())
        if raw.get('registry_id') != 'STH-REPORT-SECTIONS-v1.0':
            raise ReportSectionRegistryError('unexpected report section registry id')
        sections=[]; ids=set(); orders=set()
        for item in raw.get('sections') or []:
            sid=str(item['section_id']); order=int(item['order'])
            if sid in ids: raise ReportSectionRegistryError(f'duplicate section_id: {sid}')
            if order in orders: raise ReportSectionRegistryError(f'duplicate section order: {order}')
            ids.add(sid); orders.add(order)
            allowed=frozenset(item.get('allowed_variants') or [])
            required=frozenset(item.get('required_by_variant') or [])
            if not allowed or not allowed <= set(VARIANTS): raise ReportSectionRegistryError(f'invalid allowed_variants for {sid}')
            if not required <= allowed: raise ReportSectionRegistryError(f'required variants must be allowed for {sid}')
            fallback=str(item.get('fallback_behavior'))
            if fallback not in FALLBACKS: raise ReportSectionRegistryError(f'unknown fallback behavior: {fallback}')
            if required and fallback != 'BLOCK_IF_REQUIRED': raise ReportSectionRegistryError(f'required section must use BLOCK_IF_REQUIRED: {sid}')
            sections.append(ReportSection(sid,order,allowed,required,frozenset(item.get('finding_types') or []),fallback))
        sections.sort(key=lambda s:s.order)
        if not sections: raise ReportSectionRegistryError('section registry cannot be empty')
        registry=cls(str(raw['registry_id']),str(raw['version']),tuple(sections))
        registry.validate_variant_policies(VariantPolicyRegistry.from_repository(root))
        return registry

    def validate_variant_policies(self, policies: VariantPolicyRegistry) -> None:
        known=set(self._by_id)
        for variant in VARIANTS:
            policy=policies.get(variant)
            requested=set(policy.required_sections) | set(policy.optional_sections)
            unknown=requested-known
            if unknown: raise ReportSectionRegistryError(f'variant {variant} references unknown sections: {sorted(unknown)}')
            for sid in policy.required_sections:
                section=self._by_id[sid]
                if variant not in section.allowed_variants or variant not in section.required_by_variant:
                    raise ReportSectionRegistryError(f'variant {variant} requirement inconsistent for section {sid}')
            for sid in policy.optional_sections:
                if variant not in self._by_id[sid].allowed_variants:
                    raise ReportSectionRegistryError(f'variant {variant} cannot use section {sid}')

    def get(self, section_id: str) -> ReportSection:
        try: return self._by_id[section_id]
        except KeyError as exc: raise ReportSectionRegistryError(f'unknown section: {section_id}') from exc

    def for_variant(self, variant: str) -> tuple[ReportSection,...]:
        if variant not in VARIANTS: raise ReportSectionRegistryError(f'unsupported report variant: {variant}')
        return tuple(s for s in self.sections if variant in s.allowed_variants)
