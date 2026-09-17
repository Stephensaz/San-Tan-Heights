from __future__ import annotations
from collections import Counter
from .models import FleetHealth, PropertyHealth

class FleetHealthModel:
    def aggregate(self, properties: list[PropertyHealth] | tuple[PropertyHealth,...]) -> FleetHealth:
        status_counts=Counter(p.status for p in properties)
        signal_counts=Counter()
        for p in properties:
            for s in p.signals:
                if s.status not in ('HEALTHY','UNKNOWN'):
                    signal_counts[s.code]+=max(1,s.count)
        if status_counts.get('CRITICAL'): status='CRITICAL'
        elif status_counts.get('DEGRADED'): status='DEGRADED'
        elif properties: status='HEALTHY'
        else: status='UNKNOWN'
        return FleetHealth(status,len(properties),dict(status_counts),dict(signal_counts))
