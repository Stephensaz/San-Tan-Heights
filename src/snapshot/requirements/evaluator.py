from __future__ import annotations
from .models import RequirementEvaluation, RequirementResult, SnapshotRequirement
from src.snapshot.governed_state.models import GovernedPropertyState

class SnapshotRequirementEngine:
    def __init__(self, requirements: tuple[SnapshotRequirement, ...]):
        self.requirements=requirements

    def evaluate(self, state: GovernedPropertyState) -> RequirementEvaluation:
        # Contradictory upstream state is structurally invalid, not merely incomplete.
        if state.property_identity_status == "INVALID" or state.qa_status == "FAIL":
            return RequirementEvaluation(tuple(), "INVALID")
        results=[]
        for req in self.requirements:
            result=self._evaluate_one(req,state)
            results.append(result)
        if any(r.required_flag and r.status == "BLOCKED" for r in results):
            completeness="BLOCKED"
        elif any(r.status == "OPTIONAL_MISSING" for r in results):
            completeness="PARTIAL_VALID"
        else:
            completeness="COMPLETE"
        return RequirementEvaluation(tuple(results),completeness)

    def _evaluate_one(self, req: SnapshotRequirement, state: GovernedPropertyState) -> RequirementResult:
        sat=req.satisfied_by
        if "property_field" in sat:
            field=sat["property_field"]; value=getattr(state,field,None)
            ok=(value == sat.get("equals")) if "equals" in sat else bool(value) if sat.get("nonempty") else value is not None
            if ok: return RequirementResult(req.requirement_id,req.scope,req.required,"SATISFIED")
        elif "finding_type" in sat:
            f=next((x for x in state.findings if x.finding_type == sat["finding_type"] and x.production_status == "PRODUCTION_READY" and x.qa_status == "PASS"),None)
            if f: return RequirementResult(req.requirement_id,req.scope,req.required,"SATISFIED",finding_id=f.finding_id)
        elif "dependency_type" in sat:
            d=next((x for x in state.dependencies if x.dependency_type == sat["dependency_type"]),None)
            if d: return RequirementResult(req.requirement_id,req.scope,req.required,"SATISFIED",dependency_type=d.dependency_type,dependency_id=d.dependency_id)
        status="BLOCKED" if req.required else "OPTIONAL_MISSING"
        return RequirementResult(req.requirement_id,req.scope,req.required,status,reason_code=req.failure_reason_code)
