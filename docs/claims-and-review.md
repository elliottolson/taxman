# Claims, reviews, and reference cases

The [claim ledger](../model/claim-ledger.json) and [schema](../schemas/claim-ledger.schema.json) connect exact evidence snapshots, bounded interpretations, affected model records, independent reference expectations, and review history. This is a research contract, not an approved tax package.

## Current corpus

The initial three draft interpretations linked to two year-specific IRS PDFs. The worksheet milestone adds three claims and the Form 1040 rounding source; see [its review packet](standard-deduction-review.md). Evidence is archived in [the evidence archive](../evidence/README.md). Each document records its publication revision/date, retrieval time, authority class, applicable candidate year, byte digest, and metadata digest. Every citation pins the metadata digest and a one-based PDF page plus a section/table/example locator. The complete PDFs preserve context rather than relying on a changing web page or extracted snippet. This initial archive adapter accepts IRS PDFs only; other authority providers and media need additional archive adapters. Page counts and locators are reviewed metadata, not verified by a PDF parser in CI.

The claims cover the 2025 base deduction table, the dependent worksheet's limited base, and one sufficient Schedule B trigger. They intentionally do not claim complete eligibility, dependent earned-income classification, every reporting trigger, or full worksheet support. Their consumer links identify the exact rule/parameter/module hash and the facet grounded by the claim. A consumer hash proves identity, not sufficient coverage of its whole algorithm.

IRS operational guidance is recorded as its own authority class. It is not relabeled as statute or regulation. Controlling-law checks and subsequent-correction research remain open questions. The old planning source registry remains an inventory; archiving a document in this ledger does not approve its interpretations or change that registry's review status.

## Immutable authoring records

Source, claim, and fixture digests use sorted-key, compact JSON, UTF-8, no ASCII escaping, and no non-finite numbers; the record's own `sha256` is excluded. PDF bytes have a separate SHA-256. These are integrity checks, not signatures or proof of publisher authenticity.

A claim has a logical ID, immutable revision ID, integer version, predecessor, author reference, recorded time, `[start, end_exclusive)` tax-year interval, bounded statement, scope, exclusions, open questions, consumers, and supporting/limiting/disagreeing evidence. Transaction-date applicability remains in the separate temporal model; a broad year interval alone cannot resolve date-sensitive law.

Do not edit an archived interpretation to address a review finding. Append its next revision and explicitly supersede the predecessor. Forks and disconnected/invalid revision links fail validation. Consumer changes make old pins stale rather than silently retargeting evidence. Historic consumer bodies remain in Git; this ledger is not a complete executable snapshot store.

CI compares against the previous commit. Sources, claims, fixtures, and review events cannot be removed or rewritten; the review log must retain its exact prefix. This checks the immediately available Git baseline, not arbitrary history rewrites by administrators. Draft package selections may change because no released package format exists yet. New source revisions should have new IDs and paths. Replacing bytes at an old path fails digest validation.

## Review workflow

States are derived from hash-bound events, rather than trusted mutable status labels:

| Event | Required conditions | Result |
|---|---|---|
| Submit | Drafted record; submitting actor is its author | In review |
| Approve | Submitted, undisputed content; enabled reviewer distinct from author | Reviewed |
| Dispute | Drafted, in-review, or reviewed record; independent enabled reviewer | Disputed |
| Supersede | Claim author; linked next revision already recorded | Superseded |

Claim approval also requires reviewed source snapshots, no open questions, and no unresolved disagreeing evidence. Fixture approval requires its claim and evidence sources to be reviewed, and the reviewer must also differ from the claim author. Disputed content requires a successor revision; it cannot be resubmitted or silently reapproved. Source disputes block dependent package preflight even if an earlier claim approval remains in history.

Events must be chronological globally and per subject, cannot precede their subject, and must pin its exact content digest. Equal timestamps retain array order. Package `known_at` provides an explicit historical review context. Review events after that instant do not alter the historical state used by that preflight; the full event log is still validated.

`research-draft` is an unapproved authoring-origin reference. No real reviewer is registered and no approvals are recorded. Tests use explicitly synthetic reviewer identities. Qualification text, actor IDs, and enabled flags are contract assertions; authenticating reviewers, enforcing permissions, and assessing their qualifications require a future service/process. Changing a reviewer registration cannot safely substitute for recorded dispute/supersession history; reviewer registrations must remain valid for historical events.

## Independent reference expectations

The corpus includes 15 cases:

- Two published IRS worked examples, recorded as external expected results.
- Manually authored floor/cap boundary cases and a table lookup.
- A dependent excluded from the base-table scope.
- A missing-input case labeled as product policy rather than an IRS tax conclusion.
- Reporting-threshold cases, including a non-trigger whose overall reporting outcome remains undetermined.

Inputs use exact decimal money strings and explicit fact states. No candidate expression, worksheet implementation, or tax evaluator generates these expected results. The cases pin the exact claim and source digests, year, method of establishing the expectation, and derivation note. Their independence from candidate execution is recorded provenance, not something a Boolean flag can prove; independent review is still required.

Structural tests protect the pins and expectations. They do not execute the tax calculations, validate every manually authored amount, or establish completeness of tax coverage. Keep the published examples and source derivations as separate reference inputs when the evaluator is built, then compare its actual results against them. Add intermediate worksheet traces and rounding/date boundaries as the relevant implementations are researched.

## Package preflight

Draft package selections produce machine-readable blockers. A request for `release_candidate` fails while any gate is unsatisfied. Checks include historical claim/source/fixture approval, year matching, at least one selected reference case per claim, consumer freshness/review state, unpopulated parameters, and unimplemented modules.

Two explicit blockers always remain in this milestone: execution verification and compiled dependency coverage are not implemented. Approval of prose cannot bypass those requirements. This is a necessary preflight, not a release compiler, a complete dependency/coverage proof, or an engine conformance report. The schema permits no released state and production remains disabled.

Next, define immutable executable package closure and verification reports, establish reviewed evidence for the selected scope, and compare an evaluator with these independently authored expectations. Expand claims to exceptions and election policies using the same revision/evidence/review pattern, rather than assuming the synthetic selection policies have acquired legal authority.

## Worksheet review subjects

Claim contract 0.2 adds optional structured worksheet expectations to fixture records; every `worksheet.*` review subject requires them. The worksheet milestone adds 46 complete reference subjects alongside the original 15 fixtures. These pin all adapter inputs, full outcome semantics, intermediate expectations, evidence, and any original narrow fixture. Old records and hashes remain unchanged. This additive migration does not approve any source, interpretation, or expectation.
