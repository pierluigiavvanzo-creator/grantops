# DECISIONS.md — GrantOps

D-001 2026-10-01: prioritize visible product vertical slices over standalone infrastructure gates.

D-002 2026-10-01: Streamlit 1.64.0 is acceptable for the MVP UI and is not assumed to be the final frontend.

D-003 2026-10-01: SQLite is for local single-user validation; production DB migration remains deferred until justified.

D-004 2026-10-01: HUMAN_VERIFIED records require source/provenance evidence; uncertain extracted content must not silently become verified obligations.

D-005 2026-10-06: v0.6 is WIDE-only; RIANA and DEMO-HE-001 remain unchanged. Past structural dates do not automatically mean overdue when completion state is unknown.

D-006 2026-10-09: publish the verified v0.6 source baseline to GitHub without runtime DB, Grant Agreements, audit exports, private evidence, secrets, backups or historical patch bundles.

D-007 2026-10-09: preserve repository governance on `main`; code publication is isolated in a reviewable release branch/PR before merge.