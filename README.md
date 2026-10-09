# GrantOps

GrantOps is a local/operator MVP for source-traceable post-award operations on EU-funded projects.

## Current published baseline

**GrantOps v0.6 — WIDE Action Centre — VERIFIED**

Verified local runtime `app.py` SHA-256:

`d64f91afaaa1e6c0cfc0b8d8e027a715b91e449c9b50fb37f1ae2e8adc563dc8`

The verified WIDE slice demonstrated:

- 22/22 structural nodes preserved;
- 32/32 resolved structural deadlines preserved;
- 54/54 source/provenance chains preserved;
- WIDE Action Centre with primary action, compact queue, item detail, source/provenance and explicit uncertainty handling;
- zero DB mutations during the v0.6 validation;
- RIANA behavior unchanged;
- DEMO-HE-001 behavior unchanged;
- rollback path tested.

## What is published here

This repository contains the source/runtime code, tests and validation tooling needed for the v0.6 code baseline.

It intentionally **does not** include:

- the local SQLite runtime database;
- uploaded Grant Agreements or customer documents;
- audit exports / RIANA evidence artifacts;
- local backups and historical patch bundles;
- secrets or API keys.

Because the verified WIDE dataset and evidence artifacts are not committed, cloning this repository reproduces the source baseline but not the exact verified WIDE data state.

## Run locally on Windows

```powershell
.\INSTALL_GRANTOPS_MVP.ps1
.\TEST_GRANTOPS_MVP.ps1
.\RUN_GRANTOPS_MVP.ps1
```

Then open `http://127.0.0.1:8501`.

## Product principle

GrantOps is designed around:

`Grant Agreement → operational control → source/provenance → evidence → human decision`

The current product is a local/operator MVP and is **not** presented as production SaaS. Authentication, tenant isolation, production storage/backup, hardening, monitoring and billing remain future production gates if commercial evidence justifies them.

## Governance

Read `AGENTS_MASTER.md` and `AGENTS.md` before making material changes. Never commit secrets, customer Grant Agreements, runtime databases or private evidence artifacts to this public repository.