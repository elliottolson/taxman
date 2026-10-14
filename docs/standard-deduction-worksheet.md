# Standard deduction research worksheet

This milestone implements an executable, data-authored 2025 standard-deduction candidate. It is an offline research implementation, not a released return calculator or filing service. Python remains tooling; the production backend language is undecided. A source and implementation audit is complete; no tax-review task is assigned to the user. Separate independent acceptance is not recorded.

## Architecture

[The active worksheet package](../model/standard-deduction-package-v2.json) contains typed input definitions, indexed annual tables, worksheet expressions, ordered scope/eligibility outcomes, exact claim/source pins, reference cases, and a saved compiled plan. [Its schema](../schemas/worksheet-package.schema.json) is closed. [The generic engine](../tools/model/worksheet_engine.py) executes the authored expressions rather than embedding a series of tax-specific conditions in Python.

The compiler checks types, references, cycles, claim applicability, source pins, and complete annual-table key domains. It emits deterministic step ordering and dependency closure, source snapshots, claim review states at an explicit historical instant, and selected annual rows. A request without a populated year fails; it does not borrow another year's parameters. The authored worksheet and its selected plan currently support 2025 only. The [registry](../model/worksheet-registry.json) pins both v1 and corrected v2; historical packages remain unchanged.

The older 0.1 synthetic compiler and its packages remain unchanged. This is an explicit research worksheet adapter, not a bypass of that compiler's production tax gates. The old prototype's dependent-module interface is still incomplete; this new worksheet is not declared compatible with its one-input binding contract. It also does not populate or approve the old model's annual parameters.

## Exact numbers and indexed tables

[The numeric library](../tools/model/exact_numbers.py) represents Money, Rate, Decimal, and Integer quantities as exact rational values with explicit units. External money uses fixed-cent decimal strings; rates/decimals use decimal strings; integers reject Boolean and float coercion. Arithmetic can retain fractional cents or nonterminating ratios without depending on a global decimal context. Incompatible money dimensions and division by zero fail.

Quantization explicitly names its scale and mode: exact, half-up, half-even, floor, ceiling, or truncate. An unrepresentable output cannot silently choose a rounding mode. The IRS whole-dollar helper accepts nonnegative monetary line components, sums their cents first, and rounds the total under the documented convention. Negative IRS line rounding and a consistent filing-wide rounding choice remain separate research work. Generic signed arithmetic/rounding conventions are library behavior, not assertions about every tax worksheet.

Annual tables declare typed finite axes and complete unique rows. Enum axes must cover their declared domain. Table values may use Money, Rate, Decimal, or Integer; selections are exact and year-specific. Tests separately demonstrate two-year isolation and missing-year rejection. The actual tax tables here contain only sourced 2025 values.

## Worksheet scope

The worksheet computes a candidate amount across all five filing-status domains, dependent limits, and age/blindness additions. The expressions expose dependent worksheet lines 1–7c, box counts, annual lookups, and the selected route. Nondependent routes do not require earned income. Additions are applied after the dependent base limit.

The inputs are resolved facts, not questionnaire answers. Filing status, dependent eligibility, age eligibility (including any death-date rule), qualified blindness, and the worksheet-specific earned-income aggregate must be determined upstream. The published business-loss example supplies its already established earned aggregate; this engine does not implement business income or loss classification. Joint dependent earned-income aggregation also remains an upstream responsibility.

Known MFS spouse-itemizing and accounting-period-change short-year exclusions emit explained zero amounts. Unknown facts block. Nonresident/dual-status exceptions, other entities, and a claimable-dependent qualifying-surviving-spouse situation not listed in the dependent table remain explicitly unsupported. Unsupported is not a determination that no deduction is legally available.

The MFS spouse-box route follows the income, filing, and dependent criteria corroborated in the Form 1040 instructions. This operational source check does not resolve every controlling-authority question. A qualifying-surviving-spouse route counts the taxpayer's own eligible boxes. The newer enhanced senior deduction is a separate computation and is not included. Requested qualified-disaster-loss increases are explicitly unsupported, and an unresolved adjustment request blocks the candidate. This worksheet calculates a standard-deduction candidate; it does not choose standard versus itemized deductions or finalize Form 1040 line 12e.

## Evidence and comparisons

The existing Publication 501 archive grounds the worksheet; the 2025 Form 1040 instructions are newly archived to ground the numeric reporting helper. Three new claims cover additions, exclusions, and whole-dollar line reporting. All prior source, claim, fixture, and compiled-package archives are preserved.

The active v2 package has 48 result comparisons; the 46 original cases remain in the v1 archive. Comparisons include including seven published examples, all five base-table rows, every published age/blindness table row, dependent boundary cases, missing information, and scoped exclusions. Ten expectations are reused from the earlier claim ledger with pinned original hashes. All 46 complete worksheet cases are also registered as persistent fixture review subjects, with new v2 subjects added separately while old subjects remain unchanged. Explicit adapters supply the supplemental facts that were absent from those narrower cases; the engine has no hidden defaults.

Fourteen cases additionally compare selected intermediate values. Published outcomes, manually derived boundaries, and product missing/scope behavior are labeled separately. Expected values are authored independently of evaluator execution. Calculation agreement does not establish complete coverage, legal interpretation approval, or independent reference review.

Reports pin the plan, case set, each case, and the numeric/engine/report source files. They include exact intermediate quantities, source references, and result/blocking reasons. Schema checks plus deterministic replay reject altered traces and resealed false reports. Runner digests identify those source files, not the whole execution environment or a signed attestation.

The prior claim preflight retains its execution/coverage blockers: this worksheet has not made the broad tax model releasable. The report explicitly records pending interpretation/reference review and false production eligibility.

## Run and review

```sh
.venv/bin/python tools/model/validate_model.py --baseline-ref HEAD^
.venv/bin/python tools/model/validate_worksheet.py \
  --output /private/tmp/taxman-standard-deduction-report.json
```

The command checks the full source/model corpus, writes a report to an explicit new file, and refuses to overwrite existing output. Financial values and traces belong in controlled result storage if a production service is later built; only synthetic case data is used here.

See [the completed development review](standard-deduction-review.md) for findings and the 10,240-combination second-source check. No tax audit is assigned to the user. Any future independent acceptance must be recorded separately against exact source/claim/fixture hashes.
