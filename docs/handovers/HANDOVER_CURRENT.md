# HANDOVER_CURRENT — GrantOps

**Updated:** 2026-10-09

## Current verified baseline

`GrantOps v0.6 — WIDE Action Centre — VERIFIED`

`app.py` SHA-256:

`d64f91afaaa1e6c0cfc0b8d8e027a715b91e449c9b50fb37f1ae2e8adc563dc8`

## Frozen product constraints

- WIDE is the mature buyer-facing v0.6 slice.
- RIANA identity/provenance work remains closed unless regression evidence appears.
- DEMO-HE-001 behavior must remain unchanged.
- DB/schema migration remains frozen unless a concrete buyer-facing requirement justifies it.
- Never infer overdue status from a past structural date alone.
- Never invent owners, evidence requirements or contractual facts.
- Next actions are GrantOps recommendations, not contractual text.

## Repository boundary

Public GitHub source must exclude databases, uploaded Grant Agreements, audit/evidence exports, secrets and local backups.

## Current commercial priority

Continue narrow buyer validation and seek the first bounded pilot / transaction-level signal before expanding platform infrastructure.