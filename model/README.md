# Tax domain model

This phase models the rule system and its relationships before implementing a taxpayer return. It does not claim to encode or verify the entire tax code.

| Artifact | Purpose |
|---|---|
| [Domain catalog](domain-catalog.json) | Broad federal individual-tax concept inventory and explicit research gaps |
| [Model prototype](tax-model.json) | Typed facts, parameters, decisions, elections, modules, rules, constraints, and form mappings |
| [Model schema](../schemas/tax-model.schema.json) | Portable authoring contract using JSON Schema 2020-12 |
| [Catalog schema](../schemas/domain-catalog.schema.json) | Structure of the research inventory |
| [Modeling guide](../docs/domain-model.md) | Relationships, semantics, and next modeling steps |
| [Interaction contracts](interaction-model.json) | Synthetic temporal revisions, allocation cases, and carryover snapshots |
| [Interaction schema](../schemas/interaction-model.schema.json) | Time, ownership, allocation, and ledger contracts |
| [Execution contracts](execution-contract.json) | Synthetic authoring program, rule revisions, annual bindings, fixtures, and compiled plans |
| [Execution schema](../schemas/execution-contract.schema.json) | Portable plan, verification report, and explanation trace contracts |
| [Compilation guide](../docs/compilation-and-verification.md) | Deterministic compilation, bounded harness, verification, and limits |
| [Claim ledger](claim-ledger.json) | Archived IRS evidence, bounded draft claims, review events, and independent reference expectations |
| [Claim schema](../schemas/claim-ledger.schema.json) | Closed evidence, claim, review, fixture, and package preflight contracts |
| [Claim guide](../docs/claims-and-review.md) | Review transitions, history preservation, release blockers, and verification limits |
| [Selection contracts](selection-model.json) | Synthetic exception routing, election lifecycle, and authorized selection cases |
| [Selection schema](../schemas/selection-model.schema.json) | Closed routing, choice, event, and finite table contracts |
| [Selection guide](../docs/selection-and-elections.md) | Precedence, confirmation, conflicts, coverage, and limits |
| [Interaction guide](../docs/time-limits-carryovers.md) | Selection, conservation, archive preservation, and boundaries |

All tax interpretations in the prototype are drafts. Annual parameter values are intentionally unpopulated. A bounded synthetic harness now exercises compiled packages. There is no production tax evaluator, taxpayer return, or released rule package.

## Verification

```sh
python3 -m venv .venv
.venv/bin/pip install -r tools/model/requirements.txt
.venv/bin/python tools/model/validate_model.py
.venv/bin/python -m unittest discover -s tools/model/tests -v
```

Python is model-validation tooling only. The model is JSON, and the production backend language remains undecided. The Python compiler and bounded synthetic harness are test tooling; no production tax service is introduced.

Checks cover JSON Schema, IDs, references, declared dependencies, expression types, decision structure, relationships, dependency cycles, temporal selection, archive preservation, allocation conservation, carryover reconciliation, explicit exception routing, revision-bound election replay, Boolean/enum decision consistency, source-byte integrity, claim/fixture pins, independent review transitions, release preflight blockers, reproducible compiled plans, year-specific bindings, synthetic calculations, and report/trace integrity. Negative tests demonstrate rejection of malformed models. They do not establish legal correctness, decision-table exhaustiveness for every domain, tax accuracy, or full coverage.

The old [dividend example](../examples/dividend-rules.json) remains a separate illustrative 0.1 contract. The general model is 0.3 and the interaction, selection, claim, and execution contracts are 0.1; do not assume these schemas are interchangeable. CI checks historical archives against HEAD^; local checks may add --baseline-ref HEAD^ explicitly.
