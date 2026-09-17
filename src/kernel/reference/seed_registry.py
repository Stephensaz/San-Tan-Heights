from __future__ import annotations
from pathlib import Path
import yaml

class ReferenceSeedError(RuntimeError):
    pass

def _load(path: Path):
    raw=yaml.safe_load(path.read_text()) or {}
    if not raw.get('registry_id') or not raw.get('version'):
        raise ReferenceSeedError(f'Invalid registry metadata: {path}')
    return raw

def expected_reference_values(root: Path) -> dict[str, tuple[str,...]]:
    states=_load(root/'registries/states/states.yaml')['dimensions']
    refs=_load(root/'registries/reference/reference-values.yaml')
    reasons=_load(root/'registries/reason-codes/reason-codes.yaml')['reason_codes']
    errors=_load(root/'registries/error-codes/error-codes.yaml')['error_codes']
    events=_load(root/'registries/events/events.yaml')['events']
    guards=_load(root/'registries/guards/guards.yaml')['guards']
    classes=_load(root/'registries/classifications/data-classifications.yaml')['classifications']
    out={
        'content_state': tuple(states['CONTENT']),
        'publication_state': tuple(states['PUBLICATION']),
        'health_state': tuple(states['HEALTH']),
        'job_state': tuple(states['JOB']),
        'release_state': tuple(states['RELEASE']),
        'qa_status': tuple(refs['qa_statuses']),
        'render_type': tuple(refs['render_types']),
        'report_variant': tuple(refs['report_variants']),
        'reason_code': tuple(reasons),
        'error_code': tuple(errors),
        'event_type': tuple(e['id'] for e in events),
        'guard_id': tuple(g['id'] for g in guards),
        'data_classification': tuple(classes),
    }
    for table, values in out.items():
        if len(values) != len(set(values)):
            raise ReferenceSeedError(f'Duplicate reference code for {table}')
    return out
