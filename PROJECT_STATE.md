# PROJECT_STATE.md — GrantOps

**Updated:** 2026-10-09

## Current product baseline

`GrantOps v0.6 — WIDE Action Centre — VERIFIED`

Verified `app.py` SHA-256:

`d64f91afaaa1e6c0cfc0b8d8e027a715b91e449c9b50fb37f1ae2e8adc563dc8`

## Verified WIDE gates

- structural nodes: `22/22`
- resolved structural deadlines: `32/32`
- source/provenance chains: `54/54`
- DB mutations during validation: `0`
- RIANA changed: `NO`
- DEMO-HE-001 changed: `NO`
- rollback capability: `PRESERVED / TESTED`

## v0.6 product behavior

WIDE has a buyer-facing Action Centre with:

- needs-attention / upcoming / waiting-evidence summary;
- primary action + compact queue;
- item detail answering the seven approved operational questions;
- source/provenance visibility;
- explicit `STATO DA CONFERMARE` semantics when completion is unknown;
- no automatic overdue label solely because a structural date is in the past.

## Repository publication boundary

The public repository contains source code only. Runtime DB, uploaded Grant Agreements, audit exports, private evidence, secrets and local backups are excluded.

The exact verified WIDE data state therefore remains local and is not reconstructed from repository source alone.

## Current priority

Commercial validation and pilot evidence take priority over broad infrastructure expansion.