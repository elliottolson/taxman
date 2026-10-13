# Sources, rule imports, and tax-year releases

## The import promise

Make research and rule authoring much faster, while keeping acceptance deliberate. “Import the entire tax code” is not a safe one-click operation. Provisions depend on definitions, regulations, elections, effective dates, interpretation, and other computations. Automate collection, structuring, dependency suggestions, and change detection; review the meaning before executing it.

## Source hierarchy

Track statute, Treasury regulations, official published guidance, IRS forms/instructions/publications, corrections, and explanatory resources as different authority classes. Higher authority does not eliminate the need for operational worksheets. Material disagreement opens a research issue instead of automatically choosing one source.

Initial planning links are in [the registry](../examples/source-registry.json). Entries were inspected October 13, 2026. “Inspected” is not legal review or permission to ship a rule. Snapshot hashes are intentionally absent because source archives have not yet been downloaded and verified.

Important version finding: the current W-2 instructions page is for 2026, while the income-tax instructions used for the completed-year baseline are 2025. The registry separately identifies the [2025 W-2 instructions](https://www.irs.gov/pub/irs-prior/iw2w3--2025.pdf). Never silently mix tax years because a URL looks familiar.

## Source record

Capture stable ID, publisher, authority type, title, publication revision, reviewed tax-year applicability, canonical URL, accessed date, archive location, content digest, and source status. Exact evidence references include section heading, form/worksheet line, PDF page where verified, and a short excerpt or approved paraphrase.

Maintain a claim ledger: claim ID, supporting evidence, interpretation notes, rule consumers, review state, and tests. One broad IRS homepage link does not ground an exact threshold or exception. Short quotations need to remain faithful and appropriately attributed.

Use year-specific archived URLs when available. For continuing-use sources, pin the publication revision and archived content rather than pretending its date is the tax year. A live IRS URL can change; historical reproducibility requires an immutable evidence artifact or preserved version.

## Assisted pipeline

1. Register a candidate official source and preserve a verified snapshot.
2. Extract text, table structure, headings, and version/effective-date references.
3. Diff against the prior reviewed source; classify threshold, wording, method, and scope changes.
4. Draft candidate claims, definitions, parameter rows, rules, dependencies, and unanswered questions.
5. Attach precise evidence to each candidate. Record extraction confidence separately from legal interpretation confidence.
6. Run schema, type, range, conflict, and dependency checks.
7. Draft fixtures and boundary cases, then independently establish expected outcomes.
8. Review interpretation, applicability, calculations, and explanation.
9. Publish a versioned package only after its capability gates pass.

AI can assist steps 2–7. Treat source content and uploaded documents as untrusted input: instructions embedded in them cannot authorize tools or change workflow policy. No autonomous publication of draft rules.

Candidate states: discovered → extracted → drafted → technically validated → interpretation reviewed → released. Rejected candidates remain in history with a reason.

Imported and reviewed rules are code changes in Git. An authoring interface may help populate decision tables, but production must execute immutable reviewed artifacts rather than ad hoc admin-edited formulas.

## Annual and retroactive changes

Each package identifies jurisdiction, tax year, semantic version, engine compatibility, parameters, module versions, coverage manifest, source digests, and test-set digest. Separate changes to annual amounts from changes to calculation methods.

The [2026 inflation-adjustment release](https://www.irs.gov/newsroom/irs-releases-tax-inflation-adjustments-for-tax-year-2026-including-amendments-from-the-one-big-beautiful-bill) and [Revenue Procedure 2025-32](https://www.irs.gov/irb/2025-45_IRB) are research inputs for that year. They are not a complete verified 2026 package. The [2026 withholding and estimated-tax publication](https://www.irs.gov/publications/p505) is another distinct operational source.

Corrections can alter an earlier year's package. Publish a new revision, retain the old result snapshot, and offer a recalculation with an understandable change summary. Do not silently rewrite a saved result or imply an older result was based on newer rules.

Change impact analysis follows rule and evidence consumers: identify affected tests, capabilities, downstream outputs, and eligible saved scenarios. Use minimal metadata to determine affected scenarios; do not expose financial values in notifications.

## Quality gates

- Every released parameter and tax rule has applicable reviewed evidence.
- Every complex module has independent reference cases and step-level evidence mappings.
- Changes are checked across thresholds, household variants, interacting rules, and prior-year regressions.
- Source updates are reviewed; text change detection is a signal, not proof of a tax change.
- Unsupported coverage is deliberate and visible.
- Production packages are immutable, reproducible, and reversible.

Long-term defensibility comes from this verified corpus and update process. A large collection of unreviewed extracted rules would increase risk faster than capability.
