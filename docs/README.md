# Taxman development plan

Free U.S. federal tax preparation and filing, with securely saved information across devices and an explanation for every calculation. Estimates are an early implementation milestone.

Status: product and architecture planning. This directory contains no production calculator, verified tax-year package, deployed service, or filing integration. Rule examples are design artifacts, not tax advice or accepted calculation rules.

## Product commitments

- Free consumer preparation, explanations, and filing. Monetization is outside the current scope.
- Start with W-2, 1099-INT, 1099-DIV, filing status, standard deduction, withholding, and estimated payments.
- Secure accounts and saved scenarios across browsers and computers. Browser-only storage is not a requirement.
- Show the inputs, reasoning, and grounded sources behind each result.
- Expand supported situations deliberately; never silently ignore an unsupported fact.
- Deliver preparation and electronic filing as the end product. Separate their readiness gates from the early calculation milestone while designing the full return workflow now.

## Architecture recommendation

Use a hybrid tax rule system, not a giant sequence of conditionals and not a requirement to author everything as a graph.

1. Typed facts describe taxpayers, income, documents, and choices.
2. Versioned tables hold annual parameters and decision tables express eligibility.
3. Small declarative expressions handle routine calculations.
4. Reviewed pure modules implement complex worksheets and bounded iterative calculations.
5. A compiler derives dependencies, checks completeness and conflicts, and creates a calculation plan.
6. An evaluator emits values, applicability decisions, missing-information requests, coverage limits, and source-backed traces.

The dependency graph is a derived implementation detail. Authors work with tax concepts, tables, and worksheets. Legal text is evidence; it is not automatically executable code.

The valuable asset is a verified, versioned tax knowledge base with a reliable authoring workflow and explainable execution. Visualizing a graph alone is not a durable advantage.

## Read these next

| Document | Purpose |
|---|---|
| [Product and roadmap](product-roadmap.md) | Audience, boundaries, milestones, and release gates |
| [Rule system](rule-system.md) | Alternatives, authoring model, dependencies, exceptions, and elections |
| [Tax domain model](../model/README.md) | Portable contracts, broad concept catalog, examples, and validation |
| [Time, limits, and carryovers](time-limits-carryovers.md) | Historical selection, allocations, and cross-year reconciliation |
| [Selection and elections](selection-and-elections.md) | Exception routing, election confirmation and revocation, and finite table analysis |
| [Compilation and verification](compilation-and-verification.md) | Pinned execution plans, synthetic comparisons, and explanations |
| [Claims and reviews](claims-and-review.md) | Exact evidence, bounded interpretations, independent reference cases, and release preflight |
| [Sources and imports](sources-and-imports.md) | Grounded evidence, assisted imports, review, and tax-year releases |
| [Data and security](data-and-security.md) | Saved scenarios, accounts, documents, access, and deletion |
| [Implementation plan](implementation-plan.md) | Proposed stack, repository layout, APIs, and validation |
| [Preparation and filing](filing-product.md) | Complete return model, filing lifecycle, and transmission approach |
| [Research backlog](research-backlog.md) | Questions to settle before implementation |
| [Source registry](../examples/source-registry.json) | Official resources inspected during planning |
| [Illustrative rules](../examples/dividend-rules.json) | A small example of structured rule authoring |
| [Illustrative trace](../examples/dividend-trace.json) | How a result links back to facts and sources |
| [Rule schema](../schemas/rule-package.schema.json) | A draft contract for the illustrative rule package |

## First engineering milestone

Model the tax domain and rule authoring system before implementing a narrow return. Establish portable contracts, broad concept coverage, typed relationships, and representative exceptions/elections/worksheet interfaces. Validate these artifacts and preserve explicit research gaps. See [the model](../model/README.md). A calculation and draft return are subsequent milestones. Prove source traceability, exact arithmetic, unknown handling, and year isolation before growing the rule catalog.

Recommended starting sequence: 2025 as the completed-return reference year; add 2026 planning as a separately labeled package. Published annual parameters do not mean every return instruction for a future filing season is final.

Planning prepared October 13, 2026. See source registry for publication versions and verification limits.
