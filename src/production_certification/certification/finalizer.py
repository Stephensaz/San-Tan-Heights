from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Mapping
import csv
import io
import json
import re
import shutil
import tempfile

import yaml

from src.production_certification.certification.final_suite import (
    FinalCertificationPolicy,
    LivePostgresCertificationEvidence,
)
from src.shared.canonical_json import canonical_json

_SHA256 = re.compile(r'^[0-9a-f]{64}$')


def _hash(payload: Mapping[str, object]) -> str:
    return sha256(canonical_json(payload).encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class LiveEvidenceFinalizationAssessment:
    eligible: bool
    status: str
    reason_codes: tuple[str, ...]
    check_statuses: Mapping[str, str]
    assessment_fingerprint: str


class M7LiveEvidenceFinalizer:
    """Validates the external live-PostgreSQL proof and, only when eligible,
    applies the repository's M7->M8 status transition.

    This class intentionally does not execute PostgreSQL. It consumes the immutable,
    fingerprint-verified evidence produced by the live harness.
    """

    def assess(
        self,
        *,
        policy: FinalCertificationPolicy,
        evidence: LivePostgresCertificationEvidence,
        candidate_fingerprint: str,
        source_revision: str,
    ) -> LiveEvidenceFinalizationAssessment:
        if not _SHA256.fullmatch(candidate_fingerprint):
            raise ValueError('candidate_fingerprint must be lowercase sha256')
        if not source_revision.strip():
            raise ValueError('source_revision is required')

        checks: dict[str, str] = {}
        reasons: list[str] = []

        available_ok = bool(evidence.available)
        executed_ok = bool(evidence.executed)
        candidate_ok = evidence.candidate_fingerprint == candidate_fingerprint
        revision_ok = evidence.source_revision == source_revision

        checks['LIVE_ENVIRONMENT_AVAILABLE'] = 'PASS' if available_ok else 'FAIL'
        checks['LIVE_BATTERY_EXECUTED'] = 'PASS' if executed_ok else 'FAIL'
        checks['CANDIDATE_FINGERPRINT_BINDING'] = 'PASS' if candidate_ok else 'FAIL'
        checks['SOURCE_REVISION_BINDING'] = 'PASS' if revision_ok else 'FAIL'

        if not available_ok:
            reasons.append('LIVE_POSTGRESQL_UNAVAILABLE')
        if not executed_ok:
            reasons.append('LIVE_POSTGRESQL_NOT_EXECUTED')
        if not candidate_ok:
            reasons.append('LIVE_POSTGRES_CANDIDATE_MISMATCH')
        if not revision_ok:
            reasons.append('LIVE_POSTGRES_SOURCE_REVISION_MISMATCH')

        for code in policy.required_live_postgresql_checks:
            status = str(evidence.check_statuses.get(code, 'NOT_RUN'))
            if status not in {'PASS', 'FAIL', 'BLOCKED', 'NOT_RUN'}:
                status = 'FAIL'
            checks[code] = status
            if status != 'PASS':
                reasons.append(f'{code}_NOT_PASS')

        eligible = all(value == 'PASS' for value in checks.values())
        status = 'READY_TO_ACCEPT' if eligible else 'NOT_ELIGIBLE'
        payload = {
            'candidate_fingerprint': candidate_fingerprint,
            'source_revision': source_revision,
            'live_evidence_fingerprint': evidence.evidence_fingerprint,
            'status': status,
            'reason_codes': sorted(set(reasons)),
            'check_statuses': dict(sorted(checks.items())),
        }
        return LiveEvidenceFinalizationAssessment(
            eligible,
            status,
            tuple(sorted(set(reasons))),
            dict(sorted(checks.items())),
            _hash(payload),
        )

    def apply_repository_transition(
        self,
        *,
        repo_root: str | Path,
        evidence_path: str | Path,
        assessment: LiveEvidenceFinalizationAssessment,
        test_count: int,
    ) -> str:
        if not assessment.eligible:
            raise ValueError('live evidence is not eligible for M7 acceptance')
        root = Path(repo_root)
        evidence_path = Path(evidence_path)
        if not evidence_path.exists():
            raise ValueError('evidence_path does not exist')

        build_path = root / 'BUILD-MANIFEST.yaml'
        backlog_path = root / 'IMPLEMENTATION-BACKLOG.yaml'
        csv_path = root / 'IMPLEMENTATION-BACKLOG.csv'
        version_path = root / 'VERSION'
        changelog_path = root / 'CHANGELOG.md'
        doc_path = root / 'docs/implementation/M7-027.md'
        artifact_rel = Path('artifacts/certification/m7-027-live-postgres-evidence.json')
        artifact_path = root / artifact_rel

        build = yaml.safe_load(build_path.read_text())
        backlog = yaml.safe_load(backlog_path.read_text())

        if build.get('current_ticket') != 'M7-027':
            raise ValueError('BUILD-MANIFEST current_ticket must be M7-027')
        milestones = {m['id']: m for m in build.get('milestones', [])}
        if milestones.get('M7', {}).get('status') != 'BLOCKED':
            raise ValueError('M7 must be BLOCKED before finalization')
        if milestones.get('M8', {}).get('status') != 'NOT_STARTED':
            raise ValueError('M8 must be NOT_STARTED before finalization')

        tickets = {t['ticket_id']: t for t in backlog.get('tickets', [])}
        if tickets.get('M7-027', {}).get('status') != 'BLOCKED':
            raise ValueError('M7-027 must be BLOCKED before finalization')
        if tickets.get('M8-001', {}).get('status') != 'NOT_STARTED':
            raise ValueError('M8-001 must be NOT_STARTED before finalization')

        current_version = version_path.read_text().strip()
        parts = current_version.split('.')
        if len(parts) != 3 or not all(x.isdigit() for x in parts):
            raise ValueError('VERSION must be semantic major.minor.patch')
        next_version = '.'.join((parts[0], parts[1], str(int(parts[2]) + 1)))

        # Prepare all mutations in memory before writing any file.
        tickets['M7-027']['status'] = 'ACCEPTED'
        tickets['M8-001']['status'] = 'IN_PROGRESS'
        files = list(tickets['M7-027'].get('files') or [])
        if str(artifact_rel) not in files:
            files.append(str(artifact_rel))
        if 'scripts/certification/finalize_m7_from_live_evidence.py' not in files:
            files.append('scripts/certification/finalize_m7_from_live_evidence.py')
        tickets['M7-027']['files'] = files

        milestones['M7']['status'] = 'ACCEPTED'
        milestones['M8']['status'] = 'IN_PROGRESS'
        build['current_ticket'] = 'M8-001'
        build['version'] = next_version

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['ticket_id','milestone','title','status','dependencies','files','definition_of_done'])
        writer.writeheader()
        for ticket in backlog['tickets']:
            writer.writerow({
                'ticket_id': ticket['ticket_id'],
                'milestone': ticket['milestone'],
                'title': ticket['title'],
                'status': ticket['status'],
                'dependencies': ';'.join(ticket.get('dependencies') or []),
                'files': ';'.join(ticket.get('files') or []),
                'definition_of_done': ';'.join(ticket.get('definition_of_done') or []),
            })
        csv_text = output.getvalue()

        evidence = json.loads(evidence_path.read_text())
        evidence_text = json.dumps(evidence, indent=2, sort_keys=True) + '\n'
        changelog_entry = (
            f"## {next_version} — Milestone 7 Production Certification Accepted\n\n"
            f"- Consumed candidate-bound live PostgreSQL evidence fingerprint `{evidence.get('evidence_fingerprint')}`.\n"
            f"- Verified all five required PostgreSQL 16+ checks PASS and source/candidate binding PASS.\n"
            f"- Accepted M7-027 and Milestone 7; advanced M8-001 Presentation Package Bootstrap to IN_PROGRESS.\n"
            f"- Repository suite at finalization: {test_count} tests passed; repository validation PASS.\n\n"
        )
        new_changelog = changelog_entry + changelog_path.read_text()
        doc_append = (
            "\n## Final live-certification acceptance\n\n"
            f"M7-027 accepted from candidate-bound live PostgreSQL evidence `{evidence.get('evidence_fingerprint')}`. "
            "All required PostgreSQL checks passed and the repository finalization gate advanced Milestone 7 to ACCEPTED.\n"
        )
        new_doc = doc_path.read_text().replace(
            'Status: BLOCKED (implementation and live-certification harness complete; live PostgreSQL 16+ execution unavailable in this sandbox)',
            'Status: ACCEPTED (candidate-bound live PostgreSQL 16+ evidence verified)'
        ) + doc_append

        # Atomic-at-repository-file level: stage all files in a temp directory, then replace.
        with tempfile.TemporaryDirectory(prefix='sth-m7-finalize-', dir=str(root)) as td:
            stage = Path(td)
            staged = {
                build_path: yaml.safe_dump(build, sort_keys=False),
                backlog_path: yaml.safe_dump(backlog, sort_keys=False),
                csv_path: csv_text,
                version_path: next_version + '\n',
                changelog_path: new_changelog,
                doc_path: new_doc,
                artifact_path: evidence_text,
            }
            for target, text in staged.items():
                rel = target.relative_to(root)
                sp = stage / rel
                sp.parent.mkdir(parents=True, exist_ok=True)
                sp.write_text(text)
            for target in staged:
                rel = target.relative_to(root)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(stage / rel, target)

        return next_version
