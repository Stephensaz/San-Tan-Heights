from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping
import yaml


def _hash_bytes(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _canonical_hash(payload: object) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return _hash_bytes(raw)


@dataclass(frozen=True)
class AuditArtifactReceipt:
    ticket: str
    artifact_type: str
    path: str
    sha256: str


@dataclass(frozen=True)
class EvidenceAuditReceipt:
    ticket: str
    evidence_id: str
    path: str
    sha256: str
    status: str
    waivers: int
    open_defects: int
    capability_count: int
    control_count: int


@dataclass(frozen=True)
class OperationalCertificationPackage:
    package_id: str
    status: str
    evidence_receipts: tuple[EvidenceAuditReceipt,...]
    artifact_receipts: tuple[AuditArtifactReceipt,...]
    blocking_gaps: tuple[str,...]
    evidence_chain_root: str
    artifact_manifest_root: str
    operational_certification_root: str
    final_milestone_decision_issued: bool
    public_eligible: bool
    external_action_capability: str


def load_operational_certification_registry(path: str|Path) -> dict:
    raw=yaml.safe_load(Path(path).read_text())
    if raw.get("operational_certification_registry_id")!="STH-M12-008-OPERATIONAL-CERTIFICATION-v1.0":
        raise ValueError("unexpected M12-008 operational certification registry id")
    if str(raw.get("version"))!="1.0.0" or raw.get("status")!="FROZEN":
        raise ValueError("M12-008 registry must be FROZEN v1.0")
    expected=[f"M12-{i:03d}" for i in range(1,8)]
    if list(raw.get("accepted_evidence") or {})!=expected:
        raise ValueError("M12-008 requires exact ordered M12-001 through M12-007 evidence chain")
    if list(raw.get("artifact_manifest") or {})!=expected:
        raise ValueError("M12-008 requires exact ordered M12-001 through M12-007 artifact manifest")
    if raw["package"]["final_milestone_decision_issued"] is not False:
        raise ValueError("M12-008 cannot issue final milestone decision")
    return raw


def _read_json(path: Path) -> tuple[dict,bytes]:
    raw=path.read_bytes()
    return json.loads(raw.decode("utf-8")),raw


def _audit_controls(ticket: str, data: Mapping[str,object], registry: Mapping[str,object]) -> list[str]:
    gaps=[]
    capabilities=data.get("capabilities")
    if not isinstance(capabilities,dict) or not capabilities:
        gaps.append(f"{ticket}:CAPABILITIES_MISSING")
    else:
        for key,value in capabilities.items():
            if value is not True:
                gaps.append(f"{ticket}:CAPABILITY_NOT_TRUE:{key}")

    controls=data.get("controls")
    if not isinstance(controls,dict) or not controls:
        gaps.append(f"{ticket}:CONTROLS_MISSING")
        return gaps

    allowed_false=set(registry["control_rules"]["allowed_false_keys"])
    required_strings=dict(registry["control_rules"]["required_string_values"])
    for key,value in controls.items():
        if isinstance(value,bool):
            if key in allowed_false:
                if value is not False:
                    gaps.append(f"{ticket}:CONTROL_EXPECTED_FALSE:{key}")
            elif value is not True:
                gaps.append(f"{ticket}:CONTROL_NOT_TRUE:{key}")
        elif key in required_strings:
            if value!=required_strings[key]:
                gaps.append(f"{ticket}:CONTROL_VALUE_MISMATCH:{key}")
        else:
            gaps.append(f"{ticket}:UNDECLARED_NONBOOLEAN_CONTROL:{key}")
    return gaps


def certify_operational_audit(
    *,
    repository_root: str|Path,
    registry: Mapping[str,object],
) -> OperationalCertificationPackage:
    root=Path(repository_root)
    gaps=[]
    evidence_receipts=[]
    artifact_receipts=[]
    prior_ticket=None
    prior_path=None

    for ticket,rel_value in registry["accepted_evidence"].items():
        rel=str(rel_value)
        path=root/rel
        if not path.is_file():
            gaps.append(f"{ticket}:EVIDENCE_MISSING")
            prior_ticket=ticket
            prior_path=rel
            continue
        try:
            data,raw=_read_json(path)
        except Exception:
            gaps.append(f"{ticket}:EVIDENCE_INVALID_JSON")
            prior_ticket=ticket
            prior_path=rel
            continue

        if data.get("ticket")!=ticket:
            gaps.append(f"{ticket}:TICKET_MISMATCH")
        if data.get("status")!="ACCEPTED":
            gaps.append(f"{ticket}:NOT_ACCEPTED")
        waivers=int(data.get("waivers",-1))
        defects=int(data.get("open_defects",-1))
        if waivers!=0:
            gaps.append(f"{ticket}:WAIVERS_PRESENT")
        if defects!=0:
            gaps.append(f"{ticket}:OPEN_DEFECTS_PRESENT")

        if prior_ticket is not None:
            parent=data.get("parent")
            if not isinstance(parent,dict):
                gaps.append(f"{ticket}:PARENT_LINEAGE_MISSING")
            else:
                if parent.get("ticket")!=prior_ticket:
                    gaps.append(f"{ticket}:PARENT_TICKET_MISMATCH")
                if parent.get("evidence")!=prior_path:
                    gaps.append(f"{ticket}:PARENT_EVIDENCE_PATH_MISMATCH")

        gaps.extend(_audit_controls(ticket,data,registry))
        evidence_receipts.append(EvidenceAuditReceipt(
            ticket=ticket,
            evidence_id=str(data.get("evidence_id") or ""),
            path=rel,
            sha256=_hash_bytes(raw),
            status=str(data.get("status") or ""),
            waivers=waivers,
            open_defects=defects,
            capability_count=len(data.get("capabilities") or {}),
            control_count=len(data.get("controls") or {}),
        ))
        prior_ticket=ticket
        prior_path=rel

    if len(evidence_receipts)!=7:
        gaps.append("M12_EVIDENCE_CHAIN_INCOMPLETE")

    for ticket,manifest in registry["artifact_manifest"].items():
        for artifact_type in ("registry","implementation","tests"):
            rel=str(manifest[artifact_type])
            path=root/rel
            if not path.is_file():
                gaps.append(f"{ticket}:{artifact_type.upper()}_MISSING")
                continue
            artifact_receipts.append(AuditArtifactReceipt(
                ticket=ticket,
                artifact_type=artifact_type,
                path=rel,
                sha256=_hash_bytes(path.read_bytes()),
            ))

    expected_artifacts=7*3
    if len(artifact_receipts)!=expected_artifacts:
        gaps.append("M12_ARTIFACT_MANIFEST_INCOMPLETE")

    evidence_payload=[
        {
            "ticket":x.ticket,"evidence_id":x.evidence_id,"path":x.path,"sha256":x.sha256,
            "status":x.status,"waivers":x.waivers,"open_defects":x.open_defects,
            "capability_count":x.capability_count,"control_count":x.control_count,
        } for x in evidence_receipts
    ]
    artifact_payload=[
        {"ticket":x.ticket,"artifact_type":x.artifact_type,"path":x.path,"sha256":x.sha256}
        for x in sorted(artifact_receipts,key=lambda x:(x.ticket,x.artifact_type))
    ]
    evidence_root=_canonical_hash(evidence_payload)
    artifact_root=_canonical_hash(artifact_payload)
    blocking=tuple(sorted(set(gaps)))
    package_payload={
        "package_id":"STH-M12-008-OPERATIONAL-CERTIFICATION-PACKAGE-v1.0",
        "status":registry["package"]["status"] if not blocking else "BLOCKED",
        "evidence_chain_root":evidence_root,
        "artifact_manifest_root":artifact_root,
        "blocking_gaps":blocking,
        "final_milestone_decision_issued":False,
        "public_eligible":False,
        "external_action_capability":"NONE",
    }
    return OperationalCertificationPackage(
        package_id=package_payload["package_id"],
        status=package_payload["status"],
        evidence_receipts=tuple(evidence_receipts),
        artifact_receipts=tuple(sorted(artifact_receipts,key=lambda x:(x.ticket,x.artifact_type))),
        blocking_gaps=blocking,
        evidence_chain_root=evidence_root,
        artifact_manifest_root=artifact_root,
        operational_certification_root=_canonical_hash(package_payload),
        final_milestone_decision_issued=False,
        public_eligible=False,
        external_action_capability="NONE",
    )
