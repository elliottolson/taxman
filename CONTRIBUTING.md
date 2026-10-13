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

Keep pull requests focused. Describe the problem, resulting behavior, sources, and validation. Update related documentation when changing the design. The initial CI checks whitespace in the committed change and JSON syntax in the planning artifacts; it does not verify tax accuracy or JSON Schema conformance.

The production implementation language remains undecided. Do not introduce a runtime scaffold solely to validate planning documents.

Licensing has not been selected yet. A public repository should not be interpreted as a promise of an open-source license.
