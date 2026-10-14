# 2025 ordinary-income calculation prototype

Taxman can now calculate a bounded federal income-tax estimate from normalized W-2, 1099-INT and 1099-DIV information. This is an offline developer tool, with no accounts, upload service, web interface or filing. Rule interpretations remain research drafts; passing comparisons does not establish release approval.

## Run a synthetic return

From the repository root, using Python 3.12 or newer:

```sh
python -m pip install -r tools/model/requirements.txt
python tools/model/calculate_return.py \
  --input examples/ordinary-return-2025.json \
  --output /tmp/taxman-return-report.json
```

Choose a new output path each time. Reports are created with owner-only permissions and never overwrite existing files. The command logs the status, not financial amounts. Exit codes: `0` estimate, `2` blocked with an explanatory report, `1` invalid input/artifact or unavailable output path. Reports contain financial information; keep them out of Git and public issue attachments.

The supplied synthetic joint return has $55,000 wages, $1,500 taxable interest, $300 ordinary dividends and $3,000 federal withholding. Its $31,500 standard deduction leaves $25,300 taxable income. Publication 1040's published example gives $2,562 tax, producing a $438 estimated refund before penalties, interest and offsets.

## Supported scope

- Tax year 2025, full-year resident individuals, standard deduction.
- Single, married filing jointly, or married filing separately; filing status must already be established upstream.
- Independent adults ages 25–64, with no dependents. Blindness additions can use the existing standard-deduction worksheet when the other scope assessments are satisfied.
- W-2 boxes 1 and 2 for ordinary wages and federal income-tax withholding. Boxes 3 and 5 are also required for conservative payroll screening. Other relevant W-2 fields and Additional Medicare withholding must have been assessed.
- 1099-INT boxes 1 and 3 for federally taxable interest, including Treasury interest, and box 4 withholding.
- 1099-DIV box 1a ordinary dividends and box 4 withholding. Boxes 1b (qualified dividends, already included in 1a) and 2a (capital-gain distributions) must be confirmed zero.
- No other income, adjustments, deductions, credits, other taxes, AMT preferences or other payments. This includes Schedule 1-A deductions and estimated-tax payments.

Conservative total-income ceilings:

| Filing status | Maximum total income |
| --- | ---: |
| Single | $88,100 |
| Married filing jointly | $99,999 |
| Married filing separately | $68,500 |

Both unrounded income and the rounded AGI must satisfy the ceiling. Individual ceilings stay at or below the 2025 AMT exemptions; the joint ceiling is lower than its exemption and keeps this first package within the tax-table calculation. These are **implementation limits**, not legal income limits. Total Social Security wages and total Medicare wages each must not exceed $100,000; higher payroll wages require more screening.

A possible childless EITC blocks the estimate when both positive wage income and AGI are below $19,104 ($26,214 joint). This is conservative screening, not an eligibility determination; it may block returns that ultimately do not qualify. Dependency, senior, special deduction and other credit situations are not calculated just because a standard deduction can be calculated.

## Input contract and missing information

See `schemas/ordinary-return-input.schema.json`. Money is a nonnegative decimal string with exactly two decimal places; binary floating-point money, unknown box names, and duplicate document IDs are rejected. Document lists must be present, including explicit empty arrays. Omitted boxes are unresolved, not zero. Confirmed zero must be supplied explicitly after inspecting the source.

Each fact has a state and value. Only `confirmed` facts authorize a calculation; missing, invalid, estimated, provisional and not-applicable facts block it. Missing/invalid/not-applicable values must be null. Caller-supplied earned income is rejected: the adapter derives it from supported wages.

The normalized assessments are **upstream determinations**, not default values or a finished interview. For example, `no_credits: true` means eligibility was assessed and no credit applies; it does not mean the user simply chose to omit credits. `no_other_deductions` includes tips, overtime, eligible seniors, vehicle-loan interest, itemizing and QBI. `no_unhandled_fields` means each document was reviewed for relevant fields outside this module, including foreign taxes, tax-exempt interest, bond adjustments, special wage treatment and preferential dividends. `documents_complete` includes both spouses' documents for a joint return. Never copy the synthetic profile's confirmations into a real person's input without establishing them.

A guided interview and document-normalization layer must establish these facts before this can become a consumer preparation flow. The prototype does not independently establish status, residence, age, completeness, or every credit's eligibility. Explicit blockers explain unsupported situations and suppress final financial amounts.

## Calculation and explanation

The versioned JSON package authors the ordered financial flow: income → AGI → pinned standard-deduction worksheet → taxable income → IRS tax-table lookup → tax → withholding → payments → refund/balance. A small interpreter supports reusable operations instead of individual tax-specific branches for every return line. Domain screening is separate from arithmetic.

Each return line aggregates exact cents from its applicable boxes, then rounds once to whole dollars using the IRS half-up convention. Report lines are integer U.S. dollars. Federal withholding is rounded separately on lines 25a and 25b, then combined. Ordinary dividends include qualified dividends; they are never added together as separate income.

Taxable income below $100,000 uses the actual published tax table, not a continuous bracket formula. Reports include the precise selected interval and PDF page, source-byte pins, package/input hashes, runner-code hashes, deduction reasoning and return-line evidence. The result is a refund/balance **before penalties, interest and offsets**. It is not a complete prepared return, a filing eligibility decision or an IRS submission.

## Source import and verification

The evidence directory archives Publication 1040, the Form 1040 instructions, Form 1040 and the existing standard-deduction sources. Form 1040's PDF creation date is recorded as a publication-date proxy, explicitly distinct from a verified release date.

All 2,062 tax-table intervals were extracted from Publication 1040 PDF pages 2–13 and compared with the separately published duplicate in the Form 1040 instructions, PDF pages 68–79. The calculation uses the pinned JSON artifact and does not require a PDF reader. To reproduce the import:

```sh
python -m pip install -r tools/model/authoring-requirements.txt
python tools/model/import_tax_table.py --output /tmp/taxman-table-reproduction.json
```

Thirteen reference cases contain separately worked expectations, including the IRS published joint-return tax example, refunds/balances, zero taxable income, rounding across a table boundary and scope blockers. Contract tests additionally exercise every tax-table interval's endpoints and all mandatory-fact omissions. Run:

```sh
python tools/model/validate_model.py --baseline-ref HEAD
python -m unittest discover -s tools/model/tests -q
```

Existing worksheet packages and return artifacts are immutable. New years or corrections require new versions, newly grounded reference cases and explicit dependency pins; do not overwrite v1. The model validator includes return reference comparisons and checks historical preservation in CI.

## Next product milestone

Build a guided local web flow over this contract: enter document boxes, resolve missing information, establish scope facts, and show the income-to-refund explanation. Expand eligibility screening and preferential dividends before broadening the supported audience. Secure cross-device saving and preparation/filing remain later product milestones.
