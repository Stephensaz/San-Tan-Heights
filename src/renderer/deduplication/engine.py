from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RenderDeduplicationDecision:
    action: str
    existing_render_id: UUID | None


class RenderDeduplicationEngine:
    """Reuse only the same report/render-type/presentation semantic identity."""
    def __init__(self, repository): self.repository=repository
    def decide(self, cursor, *, report_id: UUID, render_type: str, presentation_input_hash: str) -> RenderDeduplicationDecision:
        existing=self.repository.find_equivalent(cursor,report_id,render_type,presentation_input_hash)
        return RenderDeduplicationDecision('REUSE' if existing else 'CREATE', existing)
