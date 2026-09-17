from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID, uuid4

@dataclass(frozen=True)
class CacheInvalidation:
    property_id: UUID
    report_variant: str
    channel: str | None
    reason_code: str

class CacheInvalidationEvents:
    EVENT_TYPE='PUBLICATION_CACHE_INVALIDATED'
    SOURCE_SYSTEM='PUBLICATION_SERVICE'
    @staticmethod
    def cache_keys(*,property_id,report_variant,channel=None):
        base=f'property:{property_id}:report:{report_variant}'
        keys=[base]
        if channel: keys.append(f'{base}:channel:{channel}')
        return tuple(keys)
    def __init__(self,event_writer=None): self.event_writer=event_writer
    def emit(self,cursor,*,property_id,report_variant,channel,reason_code,actor='PUBLICATION_SERVICE',correlation_id=None):
        payload={'property_id':str(property_id),'report_variant':report_variant,'channel':channel,
                 'cache_keys':list(self.cache_keys(property_id=property_id,report_variant=report_variant,channel=channel))}
        if self.event_writer is not None:
            from src.kernel.events import EventDraft
            self.event_writer.write(cursor,EventDraft(event_type=self.EVENT_TYPE,source_system=self.SOURCE_SYSTEM,
                actor_type='SYSTEM',actor_id=actor,correlation_id=correlation_id or uuid4(),property_id=property_id,
                reason_code=None,payload={**payload,'invalidation_reason':reason_code}))
        return payload
