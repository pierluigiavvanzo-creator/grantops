# AGENTS.md — GrantOps project-specific rules

> Read `AGENTS_MASTER.md` first. This file adds GrantOps-specific constraints and may tighten, but must not silently weaken, the shared standard.

## Product mission

Build GrantOps into a commercially usable grant-operations workspace that turns grant agreements and related source material into traceable, reviewable operational obligations, milestones, reporting items and evidence with minimal Product Owner/manual effort.

## Current product principle

Product before infrastructure. Prioritize the end-to-end workflow:

`Grant Agreement / source → extraction/candidates → human verification → operational workspace → deadlines/evidence/reporting → auditable status`.

Do not claim SaaS/production readiness until authentication, tenant isolation, production data storage/backup, hardening, monitoring and billing requirements relevant to the chosen commercial model are actually implemented and verified.

## GrantOps-specific evidence rules

1. Distinguish `UNVERIFIED` from `HUMAN_VERIFIED` facts and obligations.
2. Preserve source, section/citation and integrity/provenance evidence where available.
3. Never convert uncertain extracted content into verified obligations without the defined human-review gate.
4. Prefer workflows that reduce spreadsheet/email fragmentation and manual grant-administration effort.
5. Each A/B milestone must identify the commercial uncertainty it reduces: buyer, pain, willingness to pay, time-to-value, onboarding, acquisition, retention, delivery economics or compliance.
6. Until paid/customer evidence exists, describe market claims as hypotheses rather than facts.
7. Do not expand infrastructure faster than the verified operator workflow and market evidence require.

## Immediate operating priority

The next releases should move from the current local/operator workspace toward a verifiable customer workflow, especially source/PDF → candidate obligations → human review → verified workspace, before broad platform expansion.
