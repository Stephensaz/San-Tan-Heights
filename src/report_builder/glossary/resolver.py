from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import yaml
from src.report_builder.findings.selector import FindingSelection

VARIANT_KEYS={"AGENT":"agent","SELLER":"seller","PUBLIC":"public"}

class GlossaryError(ValueError):
    pass

@dataclass(frozen=True)
class GlossaryEntry:
    term_id: str
    label: str
    definition: str
    glossary_version: str

class GlossaryResolver:
    def __init__(self, registry_id: str, version: str, universal: tuple[str,...], terms: dict):
        self.registry_id=registry_id; self.version=version; self.universal=universal; self.terms=terms

    @classmethod
    def from_repository(cls, root: Path) -> 'GlossaryResolver':
        path=Path(root)/'registries/glossary/glossary-v1.0.yaml'
        raw=yaml.safe_load(path.read_text())
        if raw.get('registry_id')!='STH-CONSUMER-GLOSSARY-v1.0':
            raise GlossaryError('unexpected glossary registry id')
        terms=raw.get('terms') or {}; universal=tuple(raw.get('universal_terms') or [])
        if not terms: raise GlossaryError('glossary cannot be empty')
        for tid in universal:
            if tid not in terms: raise GlossaryError(f'unknown universal glossary term: {tid}')
        for tid, entry in terms.items():
            related=entry.get('related_finding_types') or []
            if len(set(related)) != len(related): raise GlossaryError(f'duplicate related finding type for {tid}')
            for key in VARIANT_KEYS.values():
                view=entry.get(key)
                if not isinstance(view,dict) or not str(view.get('label','')).strip() or not str(view.get('definition','')).strip():
                    raise GlossaryError(f'incomplete {key} glossary entry for {tid}')
        return cls(str(raw['registry_id']),str(raw['version']),universal,terms)

    def resolve(self, selections: Iterable[FindingSelection], variant: str) -> tuple[GlossaryEntry,...]:
        try: audience=VARIANT_KEYS[variant]
        except KeyError as exc: raise GlossaryError(f'unsupported report variant: {variant}') from exc
        used_types={s.finding.finding_type for s in selections}
        term_ids=set(self.universal)
        for tid, entry in self.terms.items():
            if used_types & set(entry.get('related_finding_types') or []): term_ids.add(tid)
        entries=[]
        for tid in sorted(term_ids):
            view=self.terms[tid][audience]
            entries.append(GlossaryEntry(tid,str(view['label']),str(view['definition']),self.version))
        return tuple(entries)
