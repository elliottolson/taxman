# Contributing to Taxman

Taxman is in the planning stage. Useful contributions include clarifying product behavior, researching supported tax situations, improving source references, and developing independently verified synthetic examples.

Start with the [roadmap](docs/product-roadmap.md) and [development plan](docs/README.md). Discuss substantial architectural or scope changes in an issue before implementing them.

## Financial information

Use fictional information in issues, pull requests, examples, and tests. Do not submit tax documents, Social Security numbers, account numbers, credentials, or anyone's financial data. Replace sensitive details with a minimal synthetic case.

## Tax rules and references

For a proposed rule, identify the jurisdiction, tax year, applicable situation, precise official source and section, interpretation, affected calculations, and unsupported cases. Distinguish published guidance from drafts and assumptions.

Numerical examples need independently established expected results and calculation steps. An example produced solely by the implementation being tested is not an independent reference. Explain rounding and method selection where they matter.

The [source and import workflow](docs/sources-and-imports.md) describes how draft interpretations become reviewed rules. A source citation does not by itself establish that a calculation is correct.

## Changes and checks

Keep pull requests focused. Describe the problem, resulting behavior, sources, and validation. Update related documentation when changing the design. CI checks whitespace, JSON syntax, model JSON Schema conformance, references/types/dependencies, historical archive preservation, temporal/ownership constraints, allocation and carryover reconciliation, and contract rejection tests. It does not verify tax accuracy or every decision overlap. See [Model verification](model/README.md).

Published definition, package, and carryover snapshots must remain intact. Add a new revision instead of editing archived content; use --baseline-ref HEAD^ locally to check preservation.

The production implementation language remains undecided. Python under tools/model/ is validation tooling for portable JSON artifacts, not an application scaffold or tax evaluator.

## License

Taxman is licensed under the [Apache License 2.0](LICENSE). Contributions submitted for inclusion in the project are under the same license unless explicitly stated otherwise.
