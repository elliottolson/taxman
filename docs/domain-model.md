# Modeling the tax domain before returns

## Goal of this phase

Establish how tax concepts are authored, linked, reviewed, versioned, and eventually executed before implementing a narrow return. A broad concept inventory keeps the architecture aware of future deductions, credits, elections, shared limits, carryovers, additional taxes, and filing obligations.

Model breadth and verified coverage are separate. An inventoried concept is not an executable rule. A valid draft rule is not an approved interpretation. A correct local calculation does not establish that a complete return can be filed.

## Core vocabulary

| Object | What it represents |
|---|---|
| Concept | A named tax topic and its research/coverage status |
| Fact | Typed information with subject, period, state, and provenance |
| Parameter | Annual or dated sourced amount, rate, range, or lookup table |
| Rule | A versioned classification, calculation, eligibility, exception, limit, or reporting step |
| Decision | Explicit conditions, result type, and hit/unknown policies |
| Election | Eligible choices, taxpayer confirmation, and downstream effects |
| Constraint | A validation predicate with severity and affected capability |
| Module | Typed contract for a complex worksheet or bounded algorithm |
| Relationship | Legal/domain connection, independent of execution order |
| Form mapping | Year-specific reporting destination for a semantic result |
| Capability | A supported situation with calculation and filing readiness |
| Carryover | A prior-year amount with owner, character, origin, and future treatment |
| Evidence | Source revision, locator, interpretation, and review state |

The draft schema concretely models the first ten objects and capabilities. Carryover value records and full evidence/claim schemas are named next extensions; they are not claimed as implemented merely because the concepts appear in the catalog.

## Multiple kinds of links

An execution dependency means a value or decision must be available first. Derive it from expression references and module bindings, checking declared dependencies for missing or extra references.

A domain relationship expresses a different meaning: exception-of, supersedes, mutually-exclusive-with, shares-limit-with, allocates-to, carries-to, reports-as, or reconciles-with. These links can be cyclic without creating an execution cycle. Never flatten them into one ordered graph or infer a legal override from a priority number.

The compiler will eventually build an executable plan from the verified package. The broader knowledge map supports research and change impact analysis. The prototype validator checks the structural distinction now.

## Subject, time, and value semantics

Scope is explicit: document, taxpayer, household, return, or transaction. An aggregate declares a return/household context and which collection it uses. Cross-subject allocation cannot be inferred from a shared tax year.

Money and rates use exact values, not binary floats. Scalar and collection shapes are different types. Annual parameters can be indexed by filing status and must not acquire a default value when unpopulated.

Input value states remain confirmed, provisional, estimated, missing, not-applicable, or invalid. Rule applicability is true, false, unknown, or invalid. The prototype defines missing-input behavior; a future evaluator must implement propagation. A schema alone does not do so.

Tax year, legal effective interval, source publication/correction, software version, and fact revision are distinct. The prototype supports candidate years and a package version; detailed effective-date intervals and cross-year carryover values remain explicitly cataloged extension work.

## Authoring model

Routine calculations use a small typed expression tree. Current operators are sum, add, subtract, min/max, comparisons, and Boolean operations. Parameter references and explicit decision rows handle selection. Avoid arbitrary executable strings or an unrestricted eval function.

Complex calculations name a typed module with explicit inputs, outputs, version, and cycle policy. An interface-only module can be modeled but cannot count as implemented coverage. The prototype has no module implementations or numeric outputs from them.

An exception names its base rule and eligibility conditions. The prototype declares this relationship and demonstrates conditional applicability. Selecting which exception replaces a base result still requires an explicit reviewed decision; an exception relationship alone does not perform replacement.

Elections list choices and eligibility predicates. Selection is a separate confirmed fact in the draft model. The future runtime must validate the choice, bind it to a return revision, and preserve future-year effects. Unselected choices remain unknown; minimizing current-year tax is not implicit authorization.

Decision tables declare unique or first-match semantics, typed conditions/results, unknown behavior, and an explicit fallback. Identical conditions are rejected for unique tables, but general overlap/exhaustiveness needs richer domain analysis and representative tests. Do not claim complete symbolic proof from this first validator.

Constraints validate facts or derived outputs without silently modifying them. A qualified amount larger than its parent amount is an error, not an invitation to clamp the value.

## Representative modeled cases

The prototype covers aggregation, subset classification, deduction choice, a dependent-related exception contract, complex worksheet interfaces, and a reporting obligation. It contains no populated tax brackets, deductions, or credit amounts.

This exercises materially different authoring patterns without building a taxpayer return or pretending every provision has been researched. The IRS [1099-DIV instructions](https://www.irs.gov/instructions/i1099div), [Publication 501](https://www.irs.gov/publications/p501), and [Schedule B instructions](https://www.irs.gov/instructions/i1040sb) are candidate evidence for these topics; interpretation review remains pending.

## Broad catalog

The catalog inventories federal individual-tax families including household/residency, income, adjustments, deductions, credits, additional taxes, payments, investments, business income, retirement, international situations, carryovers, elections, and filing lifecycle.

It is an authored research inventory, not a scraped exhaustive list of statutory provisions. Topics without modeled rules remain inventoried. The initial product priorities still emphasize W-2, 1099-INT, and 1099-DIV. Business/entity/state coverage can be cataloged without being promised for release.

Sources to organize the individual-return research include [Form 1040 instructions](https://www.irs.gov/instructions/i1040gi), [Publication 501](https://www.irs.gov/publications/p501), and the existing [source registry](../examples/source-registry.json). Exact source sections belong on individual rules as they are researched.

## Next modeling work, before a return

1. Review the object boundaries and vocabulary against representative IRS worksheets.
2. Add explicit allocation, shared-limit, carryover, and effective-date contracts.
3. Add decision-overlap analysis for finite domains and explicit method routing.
4. Refine module contracts using genuinely interacting worksheet cases.
5. Expand each catalog concept into draft claims, parameters, rules, and evidence.
6. Review one coherent rule family and its independent references before an evaluator accepts it.

The completion criterion for this modeling phase is a stable, validated authoring system with representative complex patterns and explicit gaps. Researching every individual federal provision remains ongoing; no architecture removes that work.
