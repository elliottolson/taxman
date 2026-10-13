# Research backlog and decisions

## Decisions already grounded in the conversation

- Taxman is free; monetization is not part of this phase.
- Initial income documents are W-2, 1099-INT, and 1099-DIV, not freelance 1099-NEC.
- Server-side secure storage and cross-device accounts are wanted.
- Explanations should show grounded sources.
- Future breadth matters. A graph is optional; easy, reliable rule authoring matters more.
- This work establishes a plan, not a promise of full-tax-code support or an acquisition outcome.

## Proposed defaults to validate through implementation

- Completed 2025 baseline first; separately labeled 2026 planning afterward.
- Hybrid rule system with derived dependency graph.
- Backend language to be decided; compare Go, Rust, Python, and TypeScript. Exact arithmetic, managed Postgres, and private document storage remain proposed defaults.
- Manual entry before document extraction; one account owner per household initially.
- No collection of SSNs for estimation.
- Import pipeline produces drafts for review, not executable rules accepted from prose.

## Tax research before the first released package

1. Precisely define household eligibility and what additional facts must be collected.
2. Inventory every W-2/1099 field and classify it as supported, informational, conditional, or blocking.
3. Establish qualified-dividend eligibility questions and supported capital-gain distributions.
4. Specify ordinary-tax table/computation selection and rounding in each mode.
5. Implement or conservatively screen each potentially applicable additional tax and credit; include childless credits.
6. Research year-specific deductions for ordinary wage households and standard-deduction filers.
7. Define savings-bond, foreign-income, basis, premium, discount, and corrected-document handling.
8. Identify when Schedule B or other reporting obligations affect future preparation scope.
9. Decide which elections and carryovers need prior-year facts; do not infer absent carryovers.
10. Obtain independent tax-domain review before publicly asserting numerical reliability.

## Architecture experiments

- Can a contributor add a parameter-backed deduction and its exception without kernel changes?
- Can the compiler explain why an output is blocked with the smallest relevant missing fact set?
- Can we reproduce a result after sources, formulas, and user documents change?
- Can a complex worksheet produce useful step traces without exposing implementation jargon?
- Can decision-table overlaps and incomplete method routing be detected before runtime?
- Can an imported source change produce a precise affected-capability report?

## Security and operations choices

Choose auth/recovery, region, encryption boundary, original-document retention, extraction vendor, backup retention, deletion behavior, and incident response before storing real documents. Measure deployment costs and expected load before committing to a provider.

## Broader expansion

“Entire tax code” spans individuals, businesses, entities, international provisions, reporting, and procedural law. Use a capability catalog and jurisdiction/entity boundaries. Aim first for progressively broader individual federal support. Extensibility is an architectural property; full coverage is a long-term research and maintenance program.
