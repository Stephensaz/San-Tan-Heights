# Architecture Decisions

1. Reports are immutable semantic artifacts after READY.
2. Render versions are separate from semantic report versions.
3. Current publication uses explicit pointers rather than MAX(version).
4. Invalidated historical content is never selected automatically as fallback.
5. Variant-specific semantic fingerprints isolate Agent, Seller, and Public regeneration.
6. Initial implementation uses a modular monolith plus background workers with PostgreSQL as authority.
7. Transactional outbox provides at-least-once delivery; consumers must be idempotent.
8. Routine recovery uses explicit commands, not direct production SQL.
9. Public delivery reads sanitized audience-safe DTOs/views only.
10. Presentation may clarify governed intelligence but may not derive or reinterpret it.
