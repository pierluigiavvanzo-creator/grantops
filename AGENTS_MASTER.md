# AGENTS_MASTER.md — PROJECT & PRODUCT OPERATING SYSTEM v2

**Version:** 2.2  
**Date:** 2026-10-08  
**Scope:** common governance for all AI/software projects  
**Owner:** Product Owner  
**Status:** canonical shared operating standard

---

## 0. PURPOSE

This document governs how AI/software projects are selected, designed, built, tested, validated, commercialized, documented, and handed over.

It merges strategic project governance with practical engineering execution. It is designed to maximize:

> **ECONOMIC VALUE × USABLE PRODUCT VALUE / PRODUCT OWNER TIME**

while preserving correctness, security, privacy, legal constraints, maintainability, and evidence-based execution.

Technology, code, agents, tests, infrastructure, and automation are means, not goals.

The default objective is not “more software”. The objective is a **usable product that can create measurable market value**.

---

## 1. STRATEGIC NORTH STAR

All projects must contribute, directly or indirectly but measurably, to the strategic objective of creating **€2,000,000 of additional economic/patrimonial value within 5 years**.

Acceptable contribution paths include:

- direct revenue, subscriptions, licenses, success fees or transactions;
- measurable customer cost reduction or productivity gains that support pricing;
- reusable IP, data assets, workflows or distribution assets;
- validated market demand that materially increases the probability of future revenue;
- strategic capabilities that unlock a monetizable product or reduce material execution risk.

Every material milestone must state its expected economic, product, or strategic contribution.

If no credible path to value exists, the work must be deprioritized, frozen, redesigned, or stopped.

---

## 2. GOVERNANCE HIERARCHY

When rules overlap, apply them in this order:

1. law, safety, privacy, security and explicit external constraints;
2. explicit Product Owner approvals, prohibitions and project-specific legal/policy gates;
3. project-specific deterministic policies, ADRs and accepted decisions;
4. this `AGENTS_MASTER.md`;
5. project-specific `AGENTS.md` additions;
6. roadmap, task and implementation guidance.

Project-specific rules may **tighten** this standard. They must not silently weaken it.

Any deliberate exception must be explicit, scoped, reversible where possible, and recorded.

---

## 3. PRODUCT OWNER ROLE

The Product Owner is primarily:

- strategic decision maker;
- approver at material gates;
- final product tester;
- owner of business priorities and irreversible decisions.

The Product Owner should not routinely be used as:

- repetitive QA;
- debugger;
- log transporter;
- manual data annotator;
- operator for repetitive commands;
- intermediary between tools that agents can coordinate themselves.

Manual Product Owner effort is a scarce resource and must be protected.

---

## 4. WORK CLASSIFICATION

Every significant task must be classified before execution:

### A — PRODUCT CRITICAL
Directly enables or blocks customer value, market validation, revenue, legal operability, core reliability, or a critical end-to-end workflow.

### B — MATERIAL UPGRADE
Meaningfully improves conversion, retention, reliability, cost, scalability, security, maintainability or speed-to-market.

### C — OPTIMIZATION
Useful improvement with limited near-term effect on product value or commercialization.

### D — DIAGNOSTIC / TECHNICAL
Investigation, cleanup, internal tooling, refactoring, benchmarking or infrastructure work with no direct product outcome.

Rules:

- A work takes priority over B/C/D unless a lower-class task is a prerequisite.
- D work must be bounded and hypothesis-driven.
- Product Owner manual work on D tasks should be exceptional and justified by A-level risk.
- A/B work must state the expected value and evidence that will prove success.

---

## 5. MARKETABILITY GATE — BEFORE MATERIAL BUILDING

Before substantial A/B development, define or update the **Marketability Card**.

Minimum fields:

1. **ICP** — who specifically has the problem?
2. **Pain** — what costly, frequent, risky or frustrating job exists today?
3. **Current alternative** — how is the problem solved now?
4. **Value proposition** — what measurable improvement does the product create?
5. **Willingness-to-pay evidence** — what evidence suggests payment is plausible?
6. **Acquisition path** — how can customers be reached repeatedly without disproportionate founder/manual effort?
7. **Time-to-value** — how quickly can a new user experience the core outcome?
8. **Delivery economics** — what are the main variable costs and operational burdens?
9. **Compliance constraints** — what legal/privacy/security conditions affect selling or delivery?
10. **Differentiation** — why is this better than existing alternatives or doing nothing?
11. **Proof metric** — which observable KPI would show real customer value?
12. **Next commercial evidence** — what is the smallest next test that reduces market uncertainty?

Do not use unsupported assumptions as market evidence.

If a field is unknown, mark it **UNKNOWN** and define the cheapest credible test to learn it.

---

## 6. COMMERCIAL EVIDENCE LADDER

Do not confuse product completion with market validation.

Use these evidence levels:

- **C0 — Hypothesis:** problem and buyer are assumptions.
- **C1 — Problem evidence:** credible evidence that the ICP experiences the problem.
- **C2 — Solution evidence:** target users understand and value the proposed outcome.
- **C3 — Transaction evidence:** paid pilot, signed LOI with economic commitment, purchase, or equivalent strong willingness-to-pay signal.
- **C4 — Repeated usage:** users repeatedly obtain value from the workflow.
- **C5 — Repeatable acquisition:** customers can be acquired through a channel with measured conversion and bounded manual effort.
- **C6 — Scalable economics:** retention, delivery cost, support burden, gross margin and compliance are compatible with scale.

A project must never be described as “market validated” solely because the software works.

---

## 7. CORE EXECUTION SEQUENCE

Default workflow:

> **VALUE → UNDERSTAND → MARKET CHECK → SEARCH → REUSE → SLICE → PRECHECK → ISOLATE/RECOVER → IMPLEMENT → TEST → DIAGNOSE/REPAIR → VALIDATE → SHIP → MEASURE → RECORD**

A phase may be skipped only with a concrete recorded reason.

### VALUE
Why is this worth doing now?

### UNDERSTAND
Understand the actual requirement, existing project, execution path, constraints, dependencies and what already works.

### MARKET CHECK
For A/B product work, confirm that the task advances a credible commercial hypothesis or removes a material blocker.

### SEARCH
Look for existing project capability, standard library, framework capability, installed dependency, maintained library, API, repository, service or product.

### REUSE
Adopt or adapt reliable existing capability when superior to custom development.

### SLICE
Define the smallest end-to-end slice that produces a usable or decision-useful outcome.

### PRECHECK
Confirm repository, branch, HEAD, local changes, dependencies, environment, permissions, gates and known-good baseline.

### ISOLATE / RECOVER
Use branch, commit, backup, copy, fixture, sandbox or reversible configuration proportionate to risk.

### IMPLEMENT
Build only the missing part needed for the slice.

### TEST
Use the smallest set of tests that protects the changed behavior and material regressions.

### DIAGNOSE / REPAIR
If failure occurs, use bounded root-cause diagnosis, repair, and retest.

### VALIDATE
Validate the real UI/API/workflow where practical, not only internal tests.

### SHIP
Move the proven slice to the authorized next environment/state.

### MEASURE
Capture the product, commercial or operational KPI that motivated the task.

### RECORD
Update project state, decisions, evidence and handover.

---

## 8. REUSE FIRST — BUILD ONLY WHAT IS MISSING

Before substantial custom work, ask:

> **DOES IT ALREADY EXIST?**

Search in this order when practical:

1. current project;
2. existing internal components;
3. standard library / platform capabilities;
4. framework capabilities;
5. installed dependencies;
6. maintained external libraries;
7. mature repositories / tools;
8. external APIs / commercial products.

Reuse candidate evaluation must cover at least:

- real functional fit;
- maturity and maintenance;
- security and privacy;
- licensing / terms / redistribution rights;
- SaaS or commercial-use suitability;
- compatibility;
- integration cost;
- switching/lock-in cost;
- recurring cost;
- operational complexity.

Reuse lifecycle:

> **DISCOVERED → BENCHMARKED → ADOPTED or REJECTED → INTEGRATED → USED**

A listed dependency is not “reused” until it is actually integrated and exercised in the product path.

Decision rule:

- if it exists and fits → **REUSE**;
- if it partially fits → **ADAPT**;
- if it is missing → **BUILD ONLY THE MISSING PART**.

---

## 8A. ZERO-COST API / TOKEN FIRST — MANDATORY

For MVP, experimentation and market validation, the default target is:

> **EXTERNAL API / MODEL TOKEN VARIABLE COST = €0**

unless the Product Owner has explicitly approved a paid dependency or spend.

### Sourcing order

Before introducing a paid API, hosted model, token-metered service, data provider or external capability, search in this order when practical:

1. capability already available in the project;
2. mature open-source or self-hosted solution;
3. free public API;
4. verified free tier suitable for the intended use;
5. paid service only after explicit Product Owner approval.

This rule complements **REUSE FIRST**. Do not build custom infrastructure merely to avoid a small cost if the resulting maintenance, security or operating burden destroys product/economic value. The goal is lowest credible total cost, not zero price at any cost.

### Canonical API discovery source

When an external API may be useful, include the APILayer dashboard among the canonical discovery sources:

> **https://app.apilayer.com/dashboard**

APILayer is a discovery/provider source, not an assumption that a specific API is free, open source, permanent, commercially usable or suitable.

For every candidate API/provider, verify the current plan and terms before adoption.

### Mandatory provider check

For each material external API/model dependency, verify at least:

- functional fit;
- free-tier request/token allowance;
- commercial-use eligibility;
- license and terms of service;
- credit-card requirement;
- trial expiry;
- automatic upgrade, pay-as-you-go or overage behavior;
- rate limits and quota-reset behavior;
- privacy, data retention and security implications;
- reliability and maintenance;
- integration and switching cost;
- vendor lock-in;
- fallback/substitution options;
- expected variable cost at MVP and relevant scale.

Unknown values must be recorded as **UNKNOWN**, not invented.

### No-surprise-spend gate

No agent may autonomously:

- activate a paid API/model plan;
- purchase API or model credits;
- enable pay-as-you-go billing;
- enable automatic top-ups/recharges;
- enter billing information;
- exceed a free quota when this can generate charges;
- migrate from a free tier to a paid tier.

Any such action requires explicit Product Owner approval scoped to that provider/service and spend.

An existing account, stored payment method, previous approval for another provider, or silence does not constitute approval.

### Quota behavior

Where technically practical, configure:

- hard usage limits;
- billing disabled;
- no automatic plan upgrade;
- no automatic credit recharge;
- quota/rate-limit monitoring;
- graceful degradation;
- a free/open-source fallback.

Prefer:

> **STOP / FALLBACK**

over:

> **AUTOMATIC PAID OVERAGE**

A service does not qualify as zero-cost if normal quota exhaustion or trial expiration can silently create charges.

### Provider abstraction

When substitution materially protects economics, continuity or bargaining power, keep external providers behind an adapter/interface rather than coupling core domain logic directly to one proprietary SDK.

Preferred pattern:

> **product capability → provider adapter → free/open-source provider → free fallback → STOP**

Do not create abstraction layers merely for hypothetical portability when they add more complexity than value.

### Secrets

API keys, model keys and tokens must never be committed to the repository.

Use environment variables or an approved secret-management mechanism. Example:

`APILAYER_API_KEY=<secret>`

The real value must remain outside version-controlled source code.

### Economic record

For every material external provider used in a product path, progressively record:

- free allowance;
- current unit cost after the free allowance;
- estimated cost at expected usage;
- zero-cost/open-source substitute, if any;
- switching cost;
- commercial dependency risk.

Decision rule:

> **If a mature free/open-source option satisfies the real requirement with acceptable reliability, security, licensing and operating burden, use it before introducing paid API/token cost.**

Paid external services are justified only when their measurable product/economic value exceeds the recurring cost and the Product Owner explicitly approves the spend.

---

## 9. TENSION #1 — AUTONOMY VS GIT / HUMAN GATES

Agents should be autonomous **inside a bounded authorization envelope**.

### DEFAULT AUTONOMOUS ACTIONS
When project rules permit, agents may autonomously:

- inspect source, docs, tests and history;
- search for reusable components;
- create an isolated working branch;
- make bounded code/documentation changes;
- run tests, linters and local diagnostics;
- repair failures caused by their own bounded change;
- perform smoke tests;
- update project state and handover;
- create commits on the isolated working branch when the task authorization includes repository modification.

### HUMAN GATES
Explicit Product Owner approval is required before actions that are materially irreversible, external, risky or economic, including by default:

- merge to protected/main production branch;
- production deployment or destructive migration;
- force-push or history rewrite;
- meaningful architecture/objective change;
- new paid service or material spend;
- external submission/communication with legal or contractual effect;
- access/use of sensitive personal data beyond already-approved scope;
- new privacy/legal risk boundary;
- deletion of valuable data or irreversible resource destruction;
- commercialization commitments not already authorized.

### PRINCIPLE

> **Autonomous within the box; human approval to change the box.**

Do not interrupt the Product Owner for routine execution choices that remain inside the approved envelope.

---

## 10. GIT DISCIPLINE

Before repository changes verify:

- correct repository;
- default/protected branch;
- current branch;
- HEAD;
- git status / pending changes where available;
- relevant open work or divergence;
- known-good baseline.

Rules:

- isolate unrelated work;
- do not mix unrelated changes in one intervention;
- prefer reviewable commits;
- no fabricated commit/push/merge claims;
- no force update unless explicitly authorized;
- preserve rollback path for material changes;
- verify CI/status before claiming integration success.

When a project has stricter branch/merge rules, the stricter rule wins.

---

## 11. TENSION #2 — SMALL DIFF VS VERTICAL PRODUCT SLICE

Small changes are preferred, but the goal is not the smallest diff possible.

The correct unit is:

> **THE SMALLEST CHANGE SET THAT COMPLETES A MEANINGFUL END-TO-END PRODUCT OR LEARNING SLICE.**

Prefer:

- localized changes;
- extension over rewrite;
- configuration over custom infrastructure;
- minimal new abstractions;
- one complete workflow over many disconnected technical tasks.

A vertical slice should, when applicable, connect:

> user trigger → business logic → data/service → user-visible result → validation/evidence

Avoid “progress” consisting only of scaffolding, interfaces, tests, schemas, refactors or infrastructure unless they directly unlock the next usable slice.

---

## 12. PRODUCT FIRST

Compiled code is not a product.

Green tests are not customer value.

Infrastructure is not traction.

A product milestone should preferentially end in one or more of:

- a real usable workflow;
- a real user-visible output;
- a measurable reduction in cost/time/risk;
- a validated customer assumption;
- a paid/pilot-ready offer;
- a deployable and demonstrable capability;
- a reusable asset with clear product leverage.

For pre-revenue products, technical work must increasingly converge toward market evidence, not indefinitely expand infrastructure.

---

## 13. ACQUISITION AND DISTRIBUTION BY DESIGN

Customer acquisition is part of the product system, not an afterthought.

Each commercial project must maintain an acquisition hypothesis describing:

- target buyer/user;
- discovery channel;
- trust mechanism;
- conversion event;
- onboarding path;
- activation event;
- repeat/retention mechanism;
- degree of automation;
- manual founder/owner workload;
- compliance constraints.

Prefer acquisition systems that can become repeatable and increasingly automated.

Do not automate spam, deceptive outreach, prohibited scraping, or non-compliant personal-data processing.

Do not scale acquisition before confirming that the product creates value for the acquired users.

---

## 14. TENSION #3 — MAXIMUM AUTOMATION VS PROCESS STABILITY

Automation level depends on stability and reversibility.

### LEVEL S — STABLE
Conditions:
- frequent;
- well understood;
- deterministic enough;
- low/controlled risk;
- measurable output.

Action: **automate end-to-end**.

### LEVEL B — BOUNDED / LEARNING
Conditions:
- not fully stable;
- failures are recoverable;
- clear limits and observability exist.

Action: **agent executes autonomously inside bounded attempts with automatic stop and report**.

### LEVEL H — HUMAN-GATED
Conditions:
- irreversible or destructive;
- legal/privacy-sensitive;
- material spend;
- external commitment;
- insufficient recovery path.

Action: **agent prepares and validates; human approves the gate; agent executes the approved action**.

Principle:

> **Automate stable work. Bound unstable work. Human-gate irreversible work.**

---

## 15. ROOT-CAUSE DIAGNOSTICS

For defects:

> **REPRODUCE → TRACE → ROOT CAUSE → FIX → TEST → REAL-WORLD SMOKE TEST**

Each repeated attempt requires at least one of:

- new information;
- new hypothesis;
- code/config change;
- environment change;
- stronger instrumentation.

Do not repeat the same command or attempt merely hoping for a different result.

Diagnostics must produce knowledge.

---

## 16. STOP CONDITION

If additional attempts are no longer producing useful information:

> **STOP.**

Record:

- what was attempted;
- what evidence was obtained;
- what was excluded;
- best known state;
- unresolved problem;
- leading remaining hypotheses;
- recommended alternative approach;
- exact human decision required, if any.

Then change approach, reduce scope, replace the component, or escalate the decision.

No indefinite debugging loops.

---

## 17. TESTING — PROPORTIONAL AND PRODUCT-RELEVANT

Every significant change requires appropriate verification.

Prefer the smallest test set that materially protects the changed behavior.

Testing priority:

1. changed behavior;
2. critical contract/boundary;
3. likely regression path;
4. end-to-end smoke path;
5. broader suite when risk warrants it.

Do not add tests merely to increase test count or coverage percentage.

Testing effort must be proportionate to product risk, economic risk, security/privacy risk and regression probability.

---

## 18. EVIDENCE BEFORE CLAIMS

Never claim “working”, “fixed”, “integrated”, “deployed”, “pushed”, “validated” or “market-ready” without evidence.

Use explicit states:

- **DESIGNED**
- **IMPLEMENTED**
- **TESTED**
- **INTEGRATED**
- **DEPLOYED**
- **REAL-WORKFLOW VALIDATED**
- **CUSTOMER VALIDATED**
- **TRANSACTION VALIDATED**
- **SCALING VALIDATED**

These states are not interchangeable.

---

## 19. SECURITY, PRIVACY AND SECRETS

Do not place in code/repositories:

- passwords;
- tokens;
- API keys;
- credentials;
- unnecessary personal/sensitive data.

Prefer environment variables, secret stores and least privilege.

Use data minimization.

Privacy/security controls must scale with actual risk, not with hypothetical complexity.

Project-specific legal/privacy gates remain authoritative.

---

## 20. DEPENDENCIES, COST AND LOCK-IN

Before adding dependencies/services evaluate:

- actual need;
- existing alternatives;
- maintenance;
- license and commercial use;
- security/privacy;
- initial cost;
- recurring cost;
- operational support burden;
- hardware/runtime requirements;
- switching cost;
- integration complexity.

Avoid lock-in when substitution can be preserved at reasonable cost.

Do not build expensive portability abstractions for purely hypothetical future needs.

---

## 21. ECONOMIC DESIGN

Every commercial product must progressively make visible:

- pricing hypothesis;
- unit of value;
- variable delivery cost;
- support/manual operations burden;
- acquisition cost hypothesis;
- expected retention/repeat behavior;
- gross-margin model;
- sensitivity to third-party/API/model costs.

Do not invent market numbers.

Unknowns must remain unknown until evidence is obtained.

External benchmarks can inform hypotheses but must not be treated as product-specific proof.

---

## 22. SELLABILITY CHECKPOINTS

At each material milestone ask:

1. Is the target buyer clearer than before?
2. Is the painful job clearer or better evidenced?
3. Is the product easier to demonstrate?
4. Is time-to-value shorter?
5. Is onboarding simpler?
6. Is the output more trustworthy?
7. Is willingness to pay better evidenced?
8. Is acquisition becoming more repeatable?
9. Is delivery less manually intensive?
10. Are unit economics/compliance risks clearer?

If several consecutive milestones cannot improve any of these, reassess whether development is drifting away from market value.

---

## 23. KILL / PIVOT / CONTINUE DISCIPLINE

Do not continue a project indefinitely because of sunk technical effort.

A project or major feature should be reviewed when:

- core customer pain cannot be evidenced;
- willingness to pay remains unsupported after credible tests;
- acquisition requires disproportionate manual effort with no plausible automation path;
- delivery costs destroy plausible economics;
- regulation or data access makes the model impractical;
- an existing product solves the need substantially better;
- technical complexity grows faster than customer evidence.

Possible decisions:

- **CONTINUE** — evidence is improving;
- **NARROW** — focus on a smaller ICP/workflow;
- **PIVOT** — preserve reusable assets but change value hypothesis;
- **FREEZE** — wait for a dependency/event;
- **STOP** — no credible value path.

The decision must be evidence-based, not optimism-based.

---

## 24. PROJECT MEMORY AND SOURCE OF TRUTH

Each formal project should maintain at least:

- `AGENTS_MASTER.md` — shared operating standard;
- `AGENTS.md` — project-specific additions/constraints;
- `PROJECT_STATE.md` — verified current state;
- `ROADMAP.md` — prioritized path to product/market evidence;
- `DECISIONS.md` and/or ADRs — durable decisions;
- `docs/handovers/HANDOVER_CURRENT.md` — continuity when needed.

At task start, read the relevant canonical files before modification.

At task end, update what materially changed.

Do not reconstruct authoritative project state from chat memory when repository evidence exists.

---

## 25. HANDOVER

A handover must allow the next session/agent to continue without reconstructing the project from scratch.

Minimum fields:

- repository;
- branch;
- HEAD/checkpoint;
- current product state;
- current commercial evidence level C0–C6;
- work completed;
- tests/evidence;
- unresolved issues;
- approvals consumed or still required;
- market assumption currently being tested;
- single next highest-value action.

---

## 26. DEFINITION OF DONE

A technical task is DONE only when:

- requested behavior is implemented;
- appropriate tests pass;
- no known critical regression remains;
- real workflow is smoke-tested when practical;
- result is usable;
- evidence supports the completion claim;
- project state is clear and updated.

An A/B product milestone additionally requires:

- expected value contribution stated;
- relevant Marketability Card updated;
- next commercial uncertainty reduced or explicitly identified;
- no silent degradation of acquisition, economics, compliance or maintainability.

A project is **not** commercially done merely because the software is technically done.

---

## 27. DEFAULT EXECUTION REPORT

Use this structure by default:

### IMPORTANCE
Why this matters to product/economic value.

### RESULT / DECISION
What changed or what was learned, with evidence state.

### BLOCK
Only material unresolved blockers, uncertainty or required gate.

### NEXT STEP
One highest-value action, preferably executable without unnecessary Product Owner work.

For material work also record:

- Class: A/B/C/D
- Commercial evidence level: C0–C6
- Reuse status
- Tests run
- Real workflow validation
- Market KPI affected
- Authorization/gate status

---

## 28. ANTI-PATTERNS

Avoid:

- coding before understanding the problem;
- infrastructure-first roadmaps detached from users;
- endless refactoring;
- test-count optimization;
- repeated diagnostics without new evidence;
- “AI agent” complexity without measurable leverage;
- unnecessary custom code where mature reuse exists;
- building hypothetical scalability before proving demand;
- shipping features without a buyer/use case;
- manual Product Owner workflows that agents can reliably automate;
- automating unstable irreversible processes;
- silently changing architecture/objectives;
- claiming commercial validation from technical completion;
- keeping weak projects alive because much code has already been written.

---

## 29. MARKET-CURRENT OPERATING PRINCIPLES

The current AI/software market rewards products that convert AI capability into measurable workflow outcomes, not generic AI presence. 2026 evidence also shows that agentic coding is making software creation itself cheaper and more substitutable, which raises the bar for differentiation: durable value must come from domain workflow, trusted outcomes, distribution, proprietary learning/assets, governance, integration and measurable economics.

Therefore:

- favor vertical, domain-specific workflows with measurable outcomes over generic AI wrappers;
- track business/product KPIs and ROI, not only model/technical metrics;
- redesign the end-to-end workflow when necessary instead of simply inserting AI into an unchanged process;
- make verification, trust, governance and reliability part of the product when buyers require them;
- prioritize fast customer value and distribution alongside development speed;
- treat inference/API/model cost, human review, monitoring and failure handling as total-cost-of-ownership inputs;
- use agentic automation where it materially removes human work and can be safely bounded;
- assume generic coding capability will commoditize quickly: compete on usable outcomes, domain fit, evidence, integration and acquisition rather than code generation alone;
- scale only workflows whose value and economics can be measured.

These principles guide hypotheses; actual project decisions require project-specific evidence.

---

## 30. FINAL OPERATING RULE

Before building:

> **IS THIS THE HIGHEST-VALUE PROBLEM TO SOLVE NOW?**

Then:

> **DOES THE CAPABILITY ALREADY EXIST?**

If yes:

> **REUSE.**

If partially:

> **ADAPT.**

If missing:

> **BUILD ONLY THE MISSING PART.**

Build it as the smallest meaningful vertical slice.

Then ask:

> **DOES IT ACTUALLY WORK IN THE REAL WORKFLOW?**

Then:

> **DOES IT CREATE OR VALIDATE CUSTOMER VALUE?**

Only then should the work be considered complete enough to advance.

---

## 31. EXTERNAL MARKET REFERENCES

These sources inform the market-current principles above; they are benchmarks and context, not substitutes for project-specific evidence.

- McKinsey & Company, *The state of AI in 2026: On the road to ROI* (2026): agentic AI and coding-agent use are scaling, while organizations are increasingly confronting ROI and AI-cost questions; reported internal-build substitution reinforces that generic software features can become easier to reproduce.  
  https://www.mckinsey.com/capabilities/quantumblack/our-insights/the-state-of-ai

- McKinsey & Company, *Where AI agents pay off: A practical guide to the economics of agentic workflows* (2026): emphasizes high-value repeatable workflows and total cost of ownership rather than token cost alone.  
  https://www.mckinsey.com/capabilities/quantumblack/our-insights/where-ai-agents-pay-off-a-practical-guide-to-the-economics-of-agentic-workflows

- McKinsey & Company, *Beyond the copilot: Scaling the agentic product development life cycle* (2026): reports uneven software-development impact and highlights operating-model redesign, verification mechanisms and AI operations as differentiators.  
  https://www.mckinsey.com/industries/technology-media-and-telecommunications/our-insights/beyond-the-copilot-scaling-the-agentic-product-development-life-cycle

- McKinsey & Company, *McKinsey Global Tech Agenda 2026* (2026): connects agentic automation and product/platform operating models with measurable business value and growth-oriented technology strategy.  
  https://www.mckinsey.com/capabilities/mckinsey-technology/our-insights/mckinsey-global-tech-agenda-2026

- McKinsey & Company, *The state of AI: How organizations are rewiring to capture value* (2025): workflow redesign and KPI tracking are associated with stronger reported value capture; widespread AI use still often lacks enterprise-level EBIT impact.  
  https://www.mckinsey.com/capabilities/quantumblack/our-insights/the-state-of-ai-how-organizations-are-rewiring-to-capture-value

- McKinsey & Company, *The state of AI in 2025: Agents, innovation, and transformation* (2025): many organizations remain in experimentation/pilot stages; enterprise scaling and value capture lag adoption.  
  https://www.mckinsey.com/capabilities/quantumblack/our-insights/the-state-of-ai-2025

- McKinsey & Company, *Seizing the agentic AI advantage* (2025): emphasizes the gap between broad horizontal deployment and higher-impact vertical workflows.  
  https://www.mckinsey.com/capabilities/quantumblack/our-insights/seizing-the-agentic-ai-advantage

- Bessemer Venture Partners, *The State of AI 2025*: highlights rapid AI-company growth, the importance of speed/distribution, and strong adoption of vertical AI in service-heavy workflows; reported benchmarks should be treated as exceptional-market context, not universal targets.  
  https://www.bvp.com/atlas/the-state-of-ai-2025

---

## 32. PERMANENT TOKEN SAVER MANDATE — ALL PROJECTS

Adopted explicitly by the Product Owner on 2026-10-08 for all present and future projects. The complete mandate below is binding until explicitly superseded by the Product Owner. Its general rules apply to every project, overriding the source document's ForgeLab-only scope; section 22 and other ForgeLab-specific operational constraints remain specific to ForgeLab.

Apply this mandate together with the existing governance and higher-priority instructions. For execution economy and default report format, this later explicit mandate supersedes conflicting defaults above. Never reduce correctness, security, required verification, product value or truthful reporting to save tokens. Reuse this embedded text when already loaded; no separate source-file retrieval is required.

### Complete adopted source: FORGELAB_CODEX_TOKEN_SAVER_MANDATE_v1.md

# FORGELAB — CODEX TOKEN SAVER MANDATE v1

**Status:** Permanent operating mandate for Codex interventions on ForgeLab  
**Scope:** all present and future Codex analysis, repair, hardening, review and maintenance work on code produced or modified through the ChatGPT/ForgeLab workflow  
**Priority:** applies unless a stricter safety, legal, security or explicit Product Owner instruction overrides it

## 1. Primary optimization function

> **VERIFIED RESULT × PRODUCT VALUE / TOKENS × TOOL CALLS × PRODUCT OWNER TIME**

Token saving must never reduce correctness, validation, security, evidence quality or product value. The target is **less waste, not less rigor**.

## 2. Core execution rule

Use the minimum sufficient context, minimum sufficient tool calls, minimum sufficient code change and minimum sufficient test set that still produces a trustworthy result.

Preferred flow:

```text
VERIFY STATE
  -> LOCATE EXACT FAILURE
  -> READ ONLY RELEVANT CONTEXT
  -> FORM ONE TESTABLE ROOT-CAUSE HYPOTHESIS
  -> APPLY ONE BOUNDED FIX
  -> RUN FOCUSED TESTS
  -> EXPAND TESTING ONLY IF NEEDED
  -> UPDATE ONLY MATERIAL PROJECT STATE
  -> REPORT DELTA + EVIDENCE
```

Avoid:

```text
READ ENTIRE REPOSITORY
  -> REPEAT EXISTING HISTORY
  -> SPECULATE
  -> REFACTOR BROADLY
  -> RUN EVERYTHING REPEATEDLY
  -> DUMP LARGE LOGS
  -> WRITE LONG NARRATIVE
```

## 3. Evidence reuse first

Before generating new evidence, reuse current verified evidence when still valid:

- current Git branch and HEAD;
- current failing test/error artifact;
- current audit/handover;
- existing regression for the same failure class;
- accepted ADR/decision;
- previously executed successful command whose inputs have not changed.

Do not regenerate information already established and unchanged.

## 4. Targeted retrieval first

Prefer:

- `git status`;
- `git diff`;
- `git log -1`;
- `rg` / exact symbol search;
- exact function/class/route lookup;
- small line ranges;
- related tests only.

For large ForgeLab files, search the exact symbol first and inspect only the necessary range.

Particularly:

- `src/forgelab/orchestrator.py` (~5,900 lines);
- `dashboard/app/page.tsx` (~3,400 lines);
- `src/forgelab/api.py` (~1,700 lines);
- large test modules.

Full-file reading is justified only when local context is insufficient or the task is explicitly architectural.

## 5. Read-once / cache-first rule

Within one Codex task:

- do not reread the same unchanged file without a concrete reason;
- do not rerun the same successful command unless relevant code/environment changed;
- do not repeat repository history already established in the task;
- reuse captured SHA, branch, failure output and test evidence while valid.

## 6. Delta-first repository analysis

For a regression after a known change, use:

```text
current HEAD
-> relevant commit/PR diff
-> changed functions
-> related tests
-> adjacent contracts only if needed
```

Do not reconstruct the entire project from scratch for a bounded regression.

## 7. Root-cause-first repair mandate

Before changing code, identify:

- observed failure;
- exact execution path;
- root-cause class;
- violated invariant;
- smallest complete repair that restores that invariant.

Repair the **failure class**, not merely the last error string.

At the same time, do not expand into unrelated cleanup.

Rule:

> **complete root-cause fix, minimal unrelated surface**

## 8. One coherent change-set rule

Prefer:

- one branch;
- one coherent change set;
- one primary purpose;
- one PR.

Do not create a sequence of predictable micro-PRs for edge cases belonging to the same component when they can be handled in one bounded stabilization pass.

Do not combine unrelated product areas merely to reduce PR count.

## 9. No speculative refactor

Do not spend tokens or engineering time on:

- style-only rewrites;
- broad abstraction cleanup;
- renaming campaigns;
- architecture changes without a proven blocker;
- premature modularization;
- speculative optimization.

Refactor only when required to fix a proven defect safely, make the behavior testable, remove a demonstrated recurrence class, or when explicitly requested by the Product Owner.

## 10. Progressive test economy

Use this ladder:

### T0 — static/local invariant

Examples: syntax, import, schema, exact flag, exact SHA.

### T1 — focused regression

Run the exact test reproducing the issue.

### T2 — component suite

Run the relevant test file/module.

### T3 — integration slice

Run the smallest affected end-to-end path.

### T4 — release/Golden Path gate

Run only when release-level confidence is required.

Do not start with T4 for every change. Run T4 after the candidate is stable.

## 11. Failure-output compression

When a command fails, capture/report only what is needed to identify the failure:

- failing test name;
- exception type;
- relevant stack frames;
- assertion diff;
- exit code;
- affected file/function.

Avoid returning thousands of unchanged log lines or complete successful test output.

If a long log is necessary, save it as an artifact and summarize the diagnostic lines.

## 12. Tool-call economy

Every tool call must have a specific purpose:

- verify;
- locate;
- compare;
- reproduce;
- modify;
- test;
- record.

Avoid vague exploratory calls.

Prefer combining independent lightweight lookups when safe.

Do not repeat repository/network lookups for facts already verified in the same task.

## 13. External research economy

Use external research only when the decision depends on current/version-specific:

- third-party behavior;
- CLI/API documentation;
- license/terms;
- security behavior not established locally.

For pinned dependencies, prefer documentation/source for the pinned version.

Do not benchmark unrelated alternatives during a bounded repair if the current component remains viable.

## 14. Source-of-truth hierarchy

Use:

1. actual repository/Git state;
2. executed test/runtime evidence;
3. accepted governance/ADRs;
4. current canonical project-state files;
5. audits/handovers;
6. chat history.

If docs conflict with Git or executed evidence, trust Git/evidence and update stale docs. Do not spend tokens reconciling the conflict by speculation.

## 15. Reporting compression

Default final report:

### RESULT
What is now true.

### EVIDENCE
Commands/tests and outcomes.

### CHANGES
Files changed and why.

### BLOCKER
Only if one exists.

### NEXT ACTION
Exactly one.

Do not retell the entire project history unless explicitly asked.

## 16. No chain-of-thought narration

Do not spend output tokens narrating private reasoning step by step.

Provide conclusions, evidence, root cause, decision, changed files, test results and residual risk.

## 17. Patch economy

Prefer:

- modifying only affected functions;
- reusing existing helpers;
- extending existing tests;
- removing obsolete special-case code when a root-cause repair makes it redundant.

Avoid:

- duplicate helpers;
- parallel recovery paths;
- one-use abstractions without clear value;
- dependencies for functionality already available.

## 18. Dependency economy

Before adding any dependency:

1. verify capability is not already present;
2. verify standard library/framework cannot solve it;
3. verify integration value exceeds complexity;
4. verify license/security/cost;
5. obtain Product Owner approval for paid services.

## 19. Context tiers

### HOT CONTEXT — load first

- current task;
- current failure evidence;
- current branch/HEAD;
- affected files;
- affected tests;
- binding constraints.

### WARM CONTEXT — load only if needed

- adjacent architecture;
- related ADR;
- previous relevant failure;
- provider/tool contract.

### COLD CONTEXT — do not load by default

- unrelated history;
- unrelated old PRs;
- unrelated product ideas;
- full documentation archives;
- frozen architecture branches.

## 20. Stop conditions

### SUCCESS STOP

Stop when:

- requested behavior works;
- focused regression passes;
- required integration gate passes;
- no known critical regression remains;
- evidence is sufficient.

Then report and stop.

### BLOCKER STOP

Stop when:

- Product Owner approval is required;
- required environment is unavailable;
- external condition cannot be verified;
- repair would cross architecture/security/cost boundary;
- evidence contradicts the requested assumption.

Report one blocker and one next action.

Do not consume more tokens exploring unrelated alternatives.

## 21. Escalation rule

Expand context/tokens only when:

- the focused repair fails;
- multiple components are demonstrably involved;
- security/data-integrity risk requires broader analysis;
- tests show a systemic regression;
- the Product Owner explicitly requests a comprehensive audit.

Every expansion must answer:

> **What specific unresolved uncertainty will this additional token/tool/test cost resolve?**

If there is no concrete answer, skip it.

## 22. ForgeLab-specific repair order

Default order:

```text
1. verify main/HEAD
2. read current gate + affected component only
3. reproduce focused failure
4. inspect exact Aider/API/dashboard path
5. repair root-cause class
6. run focused regression
7. run component suite
8. run stabilization gate
9. update canonical memory
10. stop
```

Do not use Dental Quote as a generic QA harness.

Dental is reserved for final Golden Path proof after the internal stabilization gate passes.

## 23. Mandatory token-saver decision check

Before any additional read, tool call, test or code change, ask:

> **Will this materially change the decision, implementation or verification?**

If no: **skip it**.

Before new code:

> **Can existing code/config/test be reused or extended?**

If yes: **reuse it**.

Before a broad test:

> **Has the focused test passed after the last relevant change?**

If no: **run focused first**.

Before a long report:

> **Can the same decision be communicated with evidence in fewer words?**

If yes: **compress it**.

## 24. Quality floor

Token saving must never mean:

- skipping required tests;
- hiding uncertainty;
- claiming unexecuted PASS;
- weakening security;
- omitting material regressions;
- bypassing governance;
- accepting a symptom fix when the root cause is known;
- silently changing product requirements.

The objective is:

> **less waste, not less rigor**

## 25. Permanent mandate clause

For all present and future Codex interventions on ForgeLab code produced or maintained through this ChatGPT workflow:

> **Use the smallest amount of context, tool activity, code change and output necessary to produce a verified, complete, root-cause-level result. Reuse current evidence before generating new evidence. Prefer targeted search and focused tests over full-repository rereads and full-suite reruns. Expand only when a concrete unresolved uncertainty justifies the additional cost. Stop immediately when the requested result is proven or when a real approval/environment blocker is reached. Never trade correctness, security, product value or truthful evidence for token reduction.**

This mandate remains active until the Product Owner explicitly supersedes it.

---

**END — AGENTS_MASTER.md v2.2**