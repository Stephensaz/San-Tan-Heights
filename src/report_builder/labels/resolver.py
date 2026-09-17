from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml

VARIANT_KEYS = {"AGENT":"agent", "SELLER":"seller", "PUBLIC":"public"}

class FriendlyLabelError(ValueError):
    pass

@dataclass(frozen=True)
class FriendlyLabelRegistry:
    registry_id: str
    version: str
    labels: dict[str, dict[str,str]]

    @classmethod
    def from_repository(cls, root: Path) -> 'FriendlyLabelRegistry':
        path = Path(root)/'registries/friendly-labels/friendly-labels-v1.0.yaml'
        raw = yaml.safe_load(path.read_text())
        if raw.get('registry_id') != 'STH-FRIENDLY-LABELS-v1.0':
            raise FriendlyLabelError('unexpected friendly label registry id')
        labels = raw.get('labels') or {}
        if not labels:
            raise FriendlyLabelError('friendly label registry cannot be empty')
        for term, entry in labels.items():
            if not isinstance(entry, dict):
                raise FriendlyLabelError(f'invalid label entry: {term}')
            missing = set(VARIANT_KEYS.values()) - set(entry)
            if missing:
                raise FriendlyLabelError(f'missing audience labels for {term}: {sorted(missing)}')
            if any(not str(entry[k]).strip() for k in VARIANT_KEYS.values()):
                raise FriendlyLabelError(f'empty audience label for {term}')
        return cls(str(raw['registry_id']), str(raw['version']), labels)

    def resolve(self, term_id: str, variant: str) -> str:
        try:
            key = VARIANT_KEYS[variant]
        except KeyError as exc:
            raise FriendlyLabelError(f'unsupported report variant: {variant}') from exc
        try:
            return str(self.labels[term_id][key])
        except KeyError as exc:
            raise FriendlyLabelError(f'missing friendly label for {term_id}') from exc
