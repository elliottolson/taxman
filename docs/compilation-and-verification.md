# Package compilation, verification, and explanations

The [execution contract](../model/execution-contract.json), [schema](../schemas/execution-contract.schema.json), and [compiler/harness](../tools/model/compile_package.py) prove a small end-to-end pipeline using invented values and decisions. This is Python validation tooling, not a production backend choice or a released tax calculator.

## Compile a pinned plan

An authoring program embeds a typed model, concept catalog, synthetic evidence registry, rule-revision history, and year-specific parameter bindings. These reuse the current portable authoring contract. Every request names its program, tax year, historical `known_at` instant, and outputs. No selection silently uses the latest rule or a parameter from another year.

The compiler selects exactly one rule revision per model rule using tax-year and knowledge intervals, validates the assembled model, then walks the complete dependency closure of the requested outputs. It emits a deterministic topological node order, each selected definition and digest, revision pins, parameter binding pins, source records, input contracts, election prerequisites, and a package digest. The package embeds its definitions; it does not require current authoring files to explain which definitions were selected.

The program is validated as a unit, so missing or ambiguous versions in an unused model rule still fail selection. All possible decision-result and election-eligibility dependencies belong in the plan. Unsupported methods cannot hide behind a currently unused branch. Legal relationship edges remain separate from execution dependencies.

Compilation fails on invalid references/types/cycles, conflicting revisions, missing or stale year-specific parameter bindings, unsupported scopes/operators, indexed lookups, modules, and rounding methods. Missing taxpayer values are a runtime question: the compiler emits their contracts; it does not invent their values or require facts from a branch that is never selected.

Identical input artifacts produce identical plans and hashes. Node ordering is independent of author ordering. The full program digest intentionally preserves authored array order; reordering an input artifact changes its identity even when the resulting node order is equivalent. Hashes follow the existing sorted-key, compact UTF-8 JSON convention and exclude an artifact's own `sha256` field.

Three saved packages demonstrate an original 2025 rule revision, its later explanation correction, and separate 2026 annual parameters. Their values and dates are invented, not IRS history. Programs, requests, fixtures, and compiled packages are immutable under the existing previous-commit CI baseline check; add a new artifact/version rather than editing an archived one.

## Bounded execution harness

The harness supports return-scoped scalar Money/Boolean/Enum values, Money collections, unindexed annual parameters, exact-cent addition/subtraction/min/max/sum, compatible comparisons, Boolean expressions, applicability predicates, finite decisions, and confirmed election choice bindings. It evaluates selected result branches lazily and blocks unresolved applicable facts. Boolean operands and decision conditions remain conservatively evaluated; this is not an optimizer or a complete unknown-value logic solver.

Unconfirmed, provisional, estimated, invalid, missing, and not-applicable facts cannot silently become confirmed values. An unused branch's missing fact does not block another branch's result. An applicable branch's missing fact does. A rule whose applicability is false emits `not_applicable` rather than zero. Money arithmetic uses integer cents, including numeric equality, without binary floats or an implicit rounding step.

The election adapter checks the selected choice, confirmed eligibility, a confirmation reference, and matching return revision. Those references are synthetic assertions. Deadlines, revocation, owner authentication, signatures, and future-year effects must be established by the separate election-lifecycle process before supplying an authorized binding to a production evaluator. This harness does not authenticate an election merely because an ID is present.

Date-sensitive applicability, general subject/household bindings, indexed annual tables, Rate/Decimal/Integer/Date/String execution, worksheets, iteration, allocations, carryovers, and tax rounding are unsupported. Existing interaction and selection contracts model some of these domains; modeling them does not make them executable in this harness.

The compiler's `tax_research` guard requires review evidence and ultimately rejects a tax package because complete interpretation/coverage acceptance is not implemented. The new artifact schema and saved examples describe synthetic programs only. The existing researched-claim preflight retains its tax execution and coverage blockers; synthetic success does not clear them.

## Verification reports

Ten independently authored synthetic fixtures are used in 18 package/case comparisons: eight cases each for the two 2025 packages and two for 2026. Expected results are entered separately from harness execution. The validator runs the harness, compares actual output/status with those expectations, and emits separate fields for:

| Field | Meaning |
|---|---|
| Structural validation | The saved plan exactly reproduces the validated compiler output |
| Calculation comparison | Every selected fixture matches, including expected blocking behavior |
| Interpretation review | Synthetic specification only; no tax-law approval |
| Production eligibility | Always false in this milestone |

Reports pin the complete package digest, individual fixture digests, fixture-set digest, runner version, and runner source-file digest. They include actual and expected results and per-case traces. A failed comparison remains a valid failed report; it cannot be relabeled passed. Empty fixture sets cannot pass. Stale or cross-package fixtures, altered outputs, wrong runner pins, and resealed forged reports fail validation against a fresh deterministic execution.

The runner digest covers the compiler/harness source file, not the entire interpreter, dependency environment, or supply chain. It is an identity pin, not a signature or proof of independent review. Synthetic expectation provenance does not establish tax correctness. The 15 IRS-backed reference expectations remain a separate, unapproved research corpus and are not claimed as executed tax tests here.

Reports are generated outputs rather than permanently archived examples. Future tax verification needs independently reviewed oracles, immutable run/environment attestations, module versions, coverage checks, and a release policy that consumes those attestations. A real release compiler is still required.

## Explanation contract

Every executed node records its definition pin, result/status, actually used dependencies, explanation key, and evidence references. Applicability decisions, selected table rows, fact states, and election confirmation IDs appear where relevant. The trace binds its exact package, return revision, and input/confirmation digest. Inactive result branches remain in the compiled plan but do not masquerade as executed trace nodes.

Trace validation replays the pinned synthetic package and requires an exact match. Removing a missing-input node, inventing a selected branch, changing a value, or hiding a used dependency fails even after recalculating the trace digest. The package's pinned source records give context for evidence references. All current trace evidence is explicitly a synthetic specification; no IRS claim has acquired approval through this example.

Financial traces will contain sensitive values when a production evaluator exists. They belong in controlled result storage, never routine logs. Current CI logs only aggregate counts and hashes for these synthetic executions. Production trace retention, access control, authenticated inputs, claim references, subject identities, rounding explanations, and signature binding remain future work.

## Generate a report

After installing the existing model-validation dependencies:

```sh
.venv/bin/python tools/model/validate_model.py --baseline-ref HEAD^
.venv/bin/python tools/model/validate_execution.py \
  --package design.2025.corrected \
  --output /private/tmp/taxman-synthetic-report.json
```

The output command validates the corpus first, writes an explicit JSON file, and refuses to overwrite an existing file. Output contains only the repository's synthetic fixtures. Schema definitions for `report` and `trace` are available under the execution schema's `$defs` for future consumers.

## Next work

Choose the scope of the first real executable package, finish its controlling-authority/interpretation reviews, implement exact numeric and indexed parameter contracts, and complete the needed worksheet interfaces. Then execute the independently reviewed IRS-backed cases and extend the compiler's coverage gate. Do not scale rule imports or build filing UI around synthetic verification results.
