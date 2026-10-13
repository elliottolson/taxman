# Product and roadmap

## The product

Taxman is intended to be a free consumer U.S. federal tax preparation and filing product: a competitor to paid products such as TurboTax. The initial audience is people with wages and straightforward bank or investment income. A calculator is an early milestone toward preparing, reviewing, and submitting supported complete returns.

The home experience should be approachable: choose a year, describe the household, add income, review the calculations and completed return, sign, submit, and see the filing outcome. Scenario exploration remains useful before finalizing a return. Explain tax concepts where needed. Keep rule IDs and technical execution details out of the normal flow; offer a detailed evidence view for people who want it.

Saved scenarios are private by default. A user can resume on another device, duplicate a scenario, compare changes, and download their data. No financial information in public share links.

## Define support by situations, not form names

Reading a document and calculating every consequence of that document are different capabilities. A form can contain an ordinary supported amount alongside an unsupported election, credit, adjustment, or special distribution.

Proposed first release: Single and Married Filing Jointly, full-year U.S. resident individual households, no dependents, neither filer claimable as a dependent, ordinary wages, uncomplicated interest and dividends, standard deduction, and confirmed payments. This is a proposed envelope, not a verified eligibility rule.

These boundaries do not justify ignoring other facts. Intake must ask about other income, adjustments, credits, special deductions, foreign situations, marketplace insurance, age, blindness, and additional taxes. A negative answer must be explicit. Childless taxpayers can still have relevant credits; no dependents is not a complete credit screen.

The system returns separate dimensions:

- Result completeness: complete within declared assumptions, partial, blocked, or invalid.
- Calculation mode: annual planning or return-method estimate.
- Rule-package maturity: experimental, reviewed, or released.
- Input quality: confirmed, provisional, estimated, or missing.

A complete estimate is not a promise that the IRS will issue a particular refund. State tax, penalties, offsets, and filing readiness are distinct scopes. Federal filing is an explicit end goal; state support is a later expansion.

## Initial capability matrix

| Area | Initial treatment | Extension path |
|---|---|---|
| W-2 | Confirmed taxable wages and federal withholding; preserve other boxes for screening | Benefits, adjustments, multiple-employer Social Security reconciliation, additional taxes |
| 1099-INT | Basic interest and withholding; distinguish Treasury and tax-exempt categories | Penalties, bond premiums, market discount, savings-bond exclusions, foreign tax |
| 1099-DIV | Ordinary dividends, verified qualified amounts, straightforward capital-gain distributions, withholding | Foreign tax, REIT/QBI, specialized gains, basis changes and liquidation |
| Household | Single and MFJ after eligibility screening | Dependents, HOH, MFS, surviving spouse, residency complications |
| Deductions | Standard deduction for the supported household | Adjustments, itemization, and year-specific additional deductions |
| Taxes | Correct ordinary/preferential method for supported facts | NIIT, AMT, Additional Medicare Tax, other schedules |
| Credits | Screen for relevance; gate unsupported applicable credits | Implement each credit as a tested capability |
| Payments | Confirmed withholding and estimated payments | Carryforward payments, refundable credits, excess withholding |
| Documents | Manual entry first; retain all relevant field values | Secure upload, extraction, corrected forms, consolidated statements |

A blocker must be specific, actionable, and distinguish a legal condition from a product limitation. Example: “Your document includes foreign tax paid. Taxman does not yet calculate its treatment.” Do not describe such a case as ineligible for a tax benefit.

## Tax research findings that change scope

Qualified dividends are part of ordinary dividends, not extra income. Certain distributions require different treatment. Source: [1099-DIV instructions, boxes 1a, 1b, and 2](https://www.irs.gov/instructions/i1099div).

Treasury interest has its own box. Bond adjustments and other entries make a naive sum unsafe. Source: [1099-INT instructions](https://www.irs.gov/instructions/i1099int).

Ordinary return tax can use tables rather than a continuous bracket formula. Source: [2025 tax tables and computation worksheets](https://www.irs.gov/publications/p1040).

Investment income, wages, and household characteristics can introduce additional taxes or deduction rules. Screen against [Form 8960](https://www.irs.gov/instructions/i8960), [Form 6251](https://www.irs.gov/instructions/i6251), [Form 8959](https://www.irs.gov/instructions/i8959), and [Publication 501](https://www.irs.gov/publications/p501). Do not use one guessed income ceiling as a universal safety gate.

New provisions can apply even to standard-deduction households. Keep these in the year's research checklist: [IRS guidance on individual tax changes](https://www.irs.gov/newsroom/working-families-tax-cuts-individuals-and-workers).

## Roadmap with completion gates

### 0. Research and contracts

Choose one year's supported calculation and filing envelopes. Inventory document boxes, required forms/schedules, and additional intake questions. Pin authoritative sources. Define fact types, a canonical return model, amount policy, outcomes, rule contracts, evidence, and test expectations. Research authorized transmission options early; do not wait until a calculator is finished.

Gate: every candidate support claim maps to an implemented rule, a reviewed exclusion decision, or a named blocker. No unreviewed “everything else is zero” shortcut.

### 1. Calculation kernel

Implement exact arithmetic, parameter lookup, unknown propagation, decision tables, expression evaluation, dependency compilation, trace serialization, and pure worksheet adapters. No account or upload work yet.

Gate: illustrative fixtures, threshold tests, independent reference cases, cycle rejection, source checks, and deterministic reproduction pass. No claim of end-user tax accuracy at this stage.

### 2. One complete supported tax-year slice

Implement income normalization, deductions, ordinary-tax lookup/computation, qualified-dividend and straightforward capital-gain treatment, payments, and coverage screening. Add year-specific output mappings without coupling semantic rule IDs to form line numbers.

Gate: reviewed numerical references across status, zero-income, withholding, and rate boundaries; applicable unsupported situations block final balance; ordinary and preferential cases are reconciled to official methods.

### 3. Free estimator interface

Guided manual entry, accessible explanations, scenario comparison, and clearly marked annual projections. Introduce return-review navigation and draft form previews, keeping hypothetical scenarios separate from confirmed return data. Prompt only for missing facts that matter to the requested result, while completing scope screening before claiming completeness.

Gate: people unfamiliar with taxes understand tax liability versus payments and can explain the reason for a changed result. No account required for an unsaved calculation.

### 4. Secure cross-device saving

Authentication, ownership, server-side scenarios, immutable calculation snapshots, optimistic concurrency, export, deletion, recovery, and restore exercises. Saving is free.

Gate: isolation checks across all resources and endpoints; successful cross-device resume; sensitive values absent from logs; restore and deletion behavior demonstrated. Before public launch, both calculation and security gates must pass.

### 5. Document intake

Private upload, scanning, extraction, field provenance, confirmation, corrections, duplicate detection, and retention choice. Keep manual entry available. Unknown boxes and missing pages cannot disappear during parsing.

Gate: extracted numbers never become confirmed facts without review; corrected statements replace prior facts rather than double-counting; document access and deletion are verified.

### 6. Breadth and annual maintenance

Add situations in coherent groups: household variants; common adjustments and credits; additional taxes; investment exceptions; retirement; itemization; business income; state overlays. Prioritize observed need and dependencies rather than the number of rules imported.

Gate per capability: evidence, reviewed interpretation, independent fixtures, regression set, explanation, screening behavior, and year applicability. No rule is released by an AI import alone.

### 7. Complete preparation and launch federal filing

Complete the guided interview, supported forms/schedules, return-wide validation, taxpayer review, signature flow, authorized transmission, acknowledgment handling, rejection correction, and downloadable records. Estimation readiness is not filing readiness. A successful network request is not IRS acceptance.

Research and model this work from milestone 0; release live filing after the calculation, security, operational, and applicable IRS/provider requirements are met. Choose the first filing tax year and transmission route explicitly. See [Preparation and filing](filing-product.md) for the lifecycle and research plan.

## What could become valuable

An explainable tax engine that other products can embed, a reliable annual update process, and a source-linked corpus of tested interpretations. Acquisition is a possibility, not a requirement or a reason to overbuild. Measure supported household coverage, accuracy, rule-change review time, and user comprehension.
