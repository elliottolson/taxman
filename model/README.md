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
| [Interaction guide](../docs/time-limits-carryovers.md) | Selection, conservation, archive preservation, and boundaries |

All tax interpretations in the prototype are drafts. Annual parameter values are intentionally unpopulated. There is no evaluator, taxpayer return, or production rule package in this phase.

## Verification

```sh
python3 -m venv .venv
.venv/bin/pip install -r tools/model/requirements.txt
.venv/bin/python tools/model/validate_model.py
.venv/bin/python -m unittest discover -s tools/model/tests -v
```

Python is model-validation tooling only. The model is JSON, and the production backend language remains undecided. No Python application or tax calculation engine is introduced.

Checks cover JSON Schema, IDs, references, declared dependencies, expression types, decision structure, relationships, dependency cycles, temporal selection, archive preservation, allocation conservation, and carryover reconciliation. Negative tests demonstrate rejection of malformed models. They do not establish legal correctness, decision-table exhaustiveness for every domain, tax accuracy, or full coverage.

The old [dividend example](../examples/dividend-rules.json) remains a separate illustrative 0.1 contract. The general model is 0.3 and the interaction contract is 0.1; do not assume these schemas are interchangeable. CI checks historical archives against HEAD^; local checks may add --baseline-ref HEAD^ explicitly.
