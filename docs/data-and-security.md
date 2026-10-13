# Saved data and security design

## Privacy with cross-device storage

Users can save their financial information securely without requiring browser-only execution. The server is authorized to process confirmed facts for calculations. Do not promise end-to-end encryption while the service can decrypt them. A separate encrypted user-only document vault could be considered later, with its recovery and processing limitations stated explicitly.

Unsaved calculations need not require an account. Saved scenarios and prepared returns do. Do not require SSNs, complete account numbers, or bank routing details for estimation. Filing introduces necessary identity/signature information and may require payment or refund details for the selected method. Collect these only at the appropriate stage, isolate them from scenario calculations, and define purpose and retention. Uploaded documents may contain them; minimize retention and redact extracted displays where feasible.

## Proposed entities

| Entity | Responsibility |
|---|---|
| Account | Authentication identity, sessions, recovery, preferences |
| Household | Taxpayer/spouse subjects and explicit ownership/access |
| Scenario | Tax year, mode, assumptions, revisions, choices |
| Document | Private object reference, tax year, owner/subject, type, correction relationships |
| DocumentField | Original field value, location, extraction provenance, confirmation state |
| FactRevision | Typed normalized information and provenance |
| Election | Eligible choices, selection, user confirmation, version |
| CalculationRun | Immutable input snapshot reference, engine/package version, outcomes |
| TaxReturnRevision | Confirmed return facts, forms, validation, and filing-readiness status |
| FilingIdentity | Separately protected taxpayer identity and selected payment/refund instructions |
| SignatureRecord | Method, authorized signer, time, and exact finalized revision |
| SubmissionAttempt | Finalized return digest, transport/provider references, idempotency, and state |
| Acknowledgment | Provider/IRS outcome and structured correction information |
| Trace | Sensitive step-level explanation and source references |
| AccessEvent | Minimal security metadata without document contents or amounts |
| RetentionJob | Deletion requests and confirmation of covered stores |

Filing jointly is a calculation relationship, not automatic account sharing. Start with one account owner per household. Add spouse collaboration through explicit invitations and permissions later.

Document identities support corrected replacements and duplicate detection. Do not deduplicate across unrelated accounts or reveal whether another user uploaded the same document. Consolidated brokerage PDFs may contain multiple document types and pages; a PDF is not equivalent to one form.

## Access and storage

Use managed authentication rather than designing password storage. Protect every read/write/export/download/worker operation with ownership checks. Postgres row-level policies can add a second boundary, but privileged workers and backups need separate controls. Random IDs are not access control. Reference: [OWASP authorization guidance](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html).

Use TLS, managed encrypted Postgres, and private encrypted object storage. Evaluate application-level authenticated encryption for financial payloads and raw documents using envelope keys under a managed KMS. Keep key access separate from routine infrastructure access, support rotation, and document what metadata remains queryable. Do not invent cryptography. Reference: [OWASP cryptographic storage](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html).

The calculation service needs decryption; restrict and audit that identity. Store public IRS evidence separately from private financial documents. All logs, traces, error reporters, analytics, queue payloads, and exports need a deliberate data classification policy.

## Upload and extraction

Private direct upload with short-lived authorization; size/page/type limits; content inspection; isolated scanning and parsing; bounded CPU/memory/time; no public bucket access. Validate content rather than trusting extensions. Reference: [OWASP upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html).

Extract fields with page/box coordinates and confidence. Store proposed values separately from user-confirmed facts. Handle disagreements, blank boxes, duplicates, year mismatch, corrected forms, and partial scans explicitly.

Prefer deterministic parsing/OCR for common layouts. If an external AI/OCR vendor is used, evaluate contractual retention, training use, region, subprocessors, and incident processes before transmitting documents. Do not assert that vendor processing is private simply because transport is encrypted. Give users an understandable explanation of who processes their documents.

The user chooses whether original documents are retained. For temporary processing, purge originals after confirmation under a stated retention policy; include processing copies and extraction artifacts. For retained documents, offer download and deletion controls.

## Operational requirements

- Secrets in managed secret storage; separate development, staging, and production identities.
- Synthetic financial documents in development, tests, demonstrations, and agent sessions.
- No amounts, SSNs, document bodies, bearer links, or complete traces in logs or third-party analytics.
- CSRF/session protections appropriate to the authentication scheme; rate limits and expiring sessions.
- Background jobs carry IDs, not document bodies, and re-check access when resolving resources.
- Autosaved edits use optimistic concurrency and conflict handling to avoid cross-device overwrites.
- Idempotent extraction/calculation jobs; durable status and retry policy; no repeated document ingestion.
- Backup encryption, restore drills, key recovery, and documented loss/recovery expectations.
- Private result responses and downloads must not enter public/CDN caches.

Deletion covers active database rows, raw objects, extraction artifacts, traces, result caches, vendor copies where applicable, and future restore handling. Backups may expire on a published schedule rather than instant deletion; restored backups must reapply deletion records. Do not promise instant erasure from every historical backup.

Filing records need retention rules consistent with the selected provider roles and applicable requirements; review [IRS Publication 1345](https://www.irs.gov/pub/irs-pdf/p1345.pdf). User deletion must explain which filed records must be retained and for how long, rather than promising universal immediate erasure.

Define retention durations and incident response before accepting real documents. Security review is part of release readiness, not a claim that this planning document establishes security.
