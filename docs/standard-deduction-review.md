# Standard deduction source and implementation review

Development review completed October 13, 2026. Elliott Olson is not assigned a tax audit or asked to approve the calculations. This review checks source consistency and implementation behavior; it does not represent approval by a separate independent reviewer. Development can continue without a user tax-review task.

## Result

The supported ordinary standard-deduction calculation agrees with the cited IRS tables, published examples, and a second implementation of the Form 1040 dependent worksheet. One coverage defect was found and corrected: the original package could not identify a request for a qualified-disaster-loss increase. The active v2 package now requires a confirmed scope fact, returns unsupported when the adjustment is requested, and blocks when the fact is unresolved. The scope guard precedes numeric exclusion results, so an unimplemented adjustment cannot be silently discarded by an earlier zero result.

The v1 package and all prior claims/fixtures are retained unchanged. The [worksheet registry](../model/worksheet-registry.json) selects [v2](../model/standard-deduction-package-v2.json) and pins both archives. Current reports use `designated_reviewer: not_assigned`; historical draft metadata does not assign a current review task to the user.

## Evidence checked

Fresh downloads from the official URLs matched the archived PDF byte hashes. The review inspected the following source locations:

| Source | One-based PDF page | What was checked |
|---|---:|---|
| [Publication 501 (2025)](https://www.irs.gov/pub/irs-prior/p501--2025.pdf) | 24–26 | Worked examples, base/addition tables, dependent worksheet |
| [Form 1040 instructions (2025)](https://www.irs.gov/pub/irs-prior/i1040gi--2025.pdf) | 33, 35 | Spouse-box conditions and the separately structured dependent worksheet/chart |
| Form 1040 instructions | 34 | Line 12e exception for elected qualified-disaster-loss increases |
| Form 1040 instructions | 23 | Nonnegative whole-dollar reporting and summing before rounding |

Archived sources are [Publication 501](../evidence/irs/2025/p501.pdf) and [Form 1040 instructions](../evidence/irs/2025/i1040gi.pdf). Exact metadata and content hashes remain in [the claim ledger](../model/claim-ledger.json).

## Findings and disposition

| Finding | Disposition |
|---|---|
| Missing qualified-disaster-loss adjustment fact | Fixed in v2 with explicit requested/unknown scope handling; the adjustment itself remains unimplemented |
| MFS spouse no-return wording differed between narrative and table footnote | Form 1040 instructions explicitly repeat the no-return criterion in both their narrative and chart; the implementation follows that operational guidance |
| User designated as tax reviewer by report/template | Removed from current reports and instructions; no approval inferred or recorded |
| Enhanced senior deduction could be confused with age/blindness additions | Reviewed: the implementation computes only standard-deduction additions and explicitly excludes the separate enhanced deduction |
| Missing/estimated facts could be mistaken for false/zero | Checked: required unresolved facts block; facts from irrelevant branches need not be present |
| Parameter years or rounding could silently change results | Checked: missing years fail, numeric inputs are exact, rounding policies are explicit, and component amounts are summed before line rounding |

The MFS check establishes agreement with the IRS filing instructions, not a completed analysis of every statutory/regulatory exception. Existing controlling-authority questions and independent-acceptance states remain open; this review does not relabel them approved.

## Verification performed

- All 46 original reference cases still pass against the archived v1 package.
- The active v2 package passes 48 cases, including new requested/unresolved disaster-adjustment cases; 14 cases check intermediate values.
- A separate test transcribes the Form 1040 chart and its earned-income threshold branch instead of reading parameters or expressions from the authored program. It compares 10,240 combinations of status, claimability, qualified boxes, MFS spouse criteria, and income boundaries with the evaluator. All comparisons agree.
- The complete suite passes 250 tests. Archive preservation, source pins, exact arithmetic, fixture expectations, and report replay are checked.

The second-source comparison is a same-author differential audit, not third-party approval. It improves confidence in implementation consistency without establishing full tax coverage or professional review. The test source is [test_worksheet_audit.py](../tools/model/tests/test_worksheet_audit.py).

## Bounded inputs and remaining development

The worksheet needs previously established filing status, dependent/age/blindness qualification, earned-income aggregation, and applicable scope facts. It computes a candidate rather than choosing deductions or finalizing a return. Residency/treaty exceptions, dependent QSS, qualified disaster adjustments, earned-income classification, and the enhanced senior deduction remain separate work.

No user review task is pending. Later production readiness still needs complete executable coverage and authenticated interpretation/reference acceptance; those requirements do not stop the next development milestone. No independent approval has been fabricated in the ledger.
