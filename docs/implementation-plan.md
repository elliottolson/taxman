# Implementation plan

## Proposed stack

Implementation language is an open decision. Current practical candidate: Go for the backend and tax engine, TypeScript for the web frontend, managed Postgres, private object storage, and a containerized deployment. Compare Go, Rust, Python, and TypeScript against the first calculation slice before committing to a runtime. The engine must not depend on the frontend framework or authentication provider.

Share API contracts through explicit schemas and generated client types; frontend and backend do not have to use the same language. Use exact decimal or integer/rational arithmetic for tax money, with documented rounding. Verify library behavior and current framework/provider documentation when implementing.

Initial production deployment candidate: Cloud Run, Postgres, Cloud Storage, Secret Manager, KMS, and GitHub Actions with federated authentication. Decide between Cloud SQL and an external Postgres provider based on actual costs, region, recovery, encryption, and network requirements. The hosting choice is provisional; no cloud resources are created by this plan.

Use a modular monolith with one independently testable engine, not microservices for each tax provision. Extraction can become a separate worker because its isolation and resource needs differ.

## Proposed future repository

```text
apps/web/                         guided intake and explanation UI
apps/api/                         accounts, scenarios, calculation endpoints
workers/document-intake/          scanning, parsing, confirmation drafts
packages/facts/                   typed schemas and normalization contracts
packages/tax-engine/              compiler, evaluator, exact math, trace
packages/tax-modules/             reviewed pure worksheet implementations
packages/tax-content/             explanations and interview definitions
rules/us/federal/2025/            manifest, decision tables, expressions
rules/us/federal/2026/            distinct planning/release packages
parameters/us/federal/<year>/     sourced annual constants and lookup tables
sources/                         claim ledger and public evidence registry
fixtures/                        synthetic and independently checked cases
infra/                           Terraform and environment manifests
```

Semantic IDs remain stable; form mappings and instructions vary by year. Database migrations and rule-package releases are distinct processes.

## Service contract

`POST /v1/calculations` accepts a scenario revision, explicit tax year and mode, and pinned package selection. It returns run ID, result completeness, package maturity, facts needing confirmation, coverage gaps, calculated values, and explanation references.

`GET /v1/calculations/:id/explanation` returns a private trace. `POST /v1/scenarios/:id/compare` compares explicit revisions with consistent methods and clearly identified changes. `POST /v1/documents` creates an authorized intake job; extraction cannot directly publish confirmed facts.

No arbitrary user-supplied expressions or executable modules through these endpoints. An agent CLI uses the same contracts and permissions, supports synthetic local calculations, and can draft package changes without production publishing rights.

Public calculation-source references contain no user data. Sensitive calculations require normal account authorization even when a source document itself is public.

## First prototype

1. Build exact numeric types and value/status contracts.
2. Implement the illustrative dividend package with dependency derivation and trace output.
3. Prove that missing data does not become zero and inconsistent qualified amounts are rejected.
4. Add one reviewed ordinary-tax method and one supported preferential-tax worksheet.
5. Add an applicability table with an exception and a coverage blocker.
6. Change a parameter version and demonstrate reproducible old/new comparisons.
7. Only then select UI and account infrastructure.

The goal is to test the architecture against real complexity, not spend months building an abstract rules platform. Include a worksheet, a decision, a source correction, and a rejected unsupported case in the prototype.

## Verification strategy

Tax calculation tests must establish independent correctness; merely echoing the implementation is insufficient.

- Reference cases: official published examples and independently reviewed worksheet calculations with documented expected intermediate steps.
- Boundaries: just below/at/above rates, lookup ranges, caps, phaseouts, rounding points, and eligibility dates.
- Relationships: qualified amounts remain subsets; payments change the balance without changing liability; equivalent document splits preserve aggregates where the method requires it.
- Metamorphic checks: document order does not affect totals; pinned versions reproduce; unsupported facts cannot yield a complete balance. Avoid assuming all tax outcomes are globally monotone.
- Interactions: status, deductions, preferential income, additional taxes, credits, and elections together.
- Failure cases: unknown/invalid values, overlapping decisions, dependency cycles, missing sources, missing parameters, disabled capabilities, incompatible modules.
- Independent comparisons: another calculator is a secondary discrepancy signal, not unquestioned truth. Resolve differences by sources, worksheets, assumptions, and rounding.

Architecture tests validate graph compilation and trace integrity. Security tests validate cross-account isolation, exports/downloads, privileged jobs, deletion, and log redaction.

## Release workflow

GitHub checks validate schemas, source references, parameter completeness, dependency compilation, types, numerical cases, and regressions. Build immutable packages and container images; deploy a reviewed release with rollback identifiers. Do not fetch “latest” tax rules during a user's calculation.

Production traces are sensitive. Monitor error categories, duration, rule/package IDs, and coarse coverage outcomes without collecting financial values. Retain historical versions needed for explanations and reproduce deleted private data only where policy lawfully permits it.

Cost controls: maximum service instances, pooled database connections, bounded document jobs, per-account upload limits, and private-object lifecycle rules. A budget alert is not a hard spending cap.
