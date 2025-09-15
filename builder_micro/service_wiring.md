# Service Wiring (summary)
- REST: FastAPI services per context, mounted under `services/micro/<ctx>/`.
- Events: Redis Streams via `RedisBus` with consumer groups (ack/replay), exactly-once via outbox + idempotency table.
- Security: JWT/OIDC (placeholder in app), TLS/Secrets via env. Observability: OTEL middleware already wired.
