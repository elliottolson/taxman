# Time, shared limits, allocations, and carryovers

These contracts extend the portable tax model to 0.3. They are implemented as schemas, synthetic examples, and verification tooling. They do not determine actual tax eligibility or calculate a taxpayer return.

See [interaction examples](../model/interaction-model.json), [their schema](../schemas/interaction-model.schema.json), and [the validator](../tools/model/validate_interactions.py).

## Time and versioning

Rule selection has explicit independent dimensions:

- Tax-year applicability: an integer interval.
- Transaction-date applicability: an optional date interval.
- Source publication: when the referenced information became public.
- Observation: when Taxman recorded that revision.
- Supersession: when a later recorded revision replaced it.
- Package creation: when a pinned package snapshot was assembled.

Intervals use an inclusive start and exclusive end. A null end is open-ended. Instants are UTC timestamps. No implicit latest version is selected, and missing required transaction context blocks resolution.

The synthetic example has one version observed in 2025 and a correction observed in March 2026 that applies to the same earlier tax year. A historical package keeps the original version; a later recalculation selects the correction. The invented dates are not an assertion about IRS publications.

Version IDs and snapshot hashes identify exact rule definitions. Package snapshots pin revision IDs and definition hashes alongside the selection context. A successful schema check cannot substitute for pinning the actual definition.

The validator rejects overlapping revisions when tax-year, transaction-date, and observation windows all overlap for the same semantic rule. It also rejects backward versions, invalid intervals, incorrect predecessor links, and pins inconsistent with their historical context.

Archive preservation is checked against an explicit previous Git revision. Published definition snapshots, packages, and carryover snapshots cannot be rewritten or removed. A rule's open observation interval may be closed once by a linked successor; the earlier definition remains unchanged.

The hash encoding is UTF-8 JSON with sorted object keys, compact separators, no ASCII escaping, and no nonfinite numbers. Package/ledger hashes omit their own sha256 field. Definitions hash their complete payload. Other implementation languages must reproduce this encoding or introduce a separately versioned digest format. These hashes detect content inconsistencies; they are not signatures or independent legal verification.

The demonstration packages pin one rule only. Complete executable package dependency closure, parameter archives, and source archives remain separate future work.

## Shared limits and allocations

A shared limit identifies its concept, currency, year, owner, capacity binding, and individual claim bindings. Bindings connect to typed Money definitions and explicit synthetic subjects. A claim's owner must be within the declared owner group; return-scoped groups name their taxpayers explicitly.

Each allocation identifies a scenario, limit, proposed/confirmed status, exact capacity, requested amounts, outputs, and unused balance. Alternatives in the same scenario must use the same inputs. Only one outcome can be confirmed for a scenario and limit. Alternative scenarios are never added together as simultaneous consumption.

The current contract supports:

| Method | Verification |
|---|---|
| Explicit allocation | Each output is nonnegative, does not exceed its claim, and fits the shared capacity; allocated plus unused equals capacity |
| Proportional allocation | Exact rational weights determine the split; whole-cent floors plus largest remainders distribute the capacity; ties use claim ID order |

The synthetic proportional example splits $100.01 equally into $50.01 and $50.00. The fixture supplies the expected outcome independently; verification checks it without binary floating-point arithmetic.

Zero capacity is allowed. Zero total weight is not. Duplicate amount bindings, missing claims, cross-household claims, scope mismatches, negative amounts, and inconsistent remainder policies are rejected.

Proportional validation covers an uncapped weighted split. If a requested amount is too small for that split, it is rejected; redistribution among capped recipients requires another explicit method. Tax-defined priority, complex allocation worksheets, and taxpayer authorization are not inferred from a mathematical split.

Capacity and demand values in these examples are synthetic assertions. A future evaluator must resolve them from confirmed facts or reviewed calculations and bind the outcome to an immutable input revision. Structural conservation does not prove that a tax allowance applies.

## Carryover records

A carryover snapshot preserves logical identity, version, owner, tax character, origin year, opening year, confirmed opening amount/provenance, optional expiration year, event history, and reported yearly balances.

The opening year follows the origin year. The opening amount is an asserted imported balance with provenance; this layer does not reconstruct unprovided prior-year returns or determine the legal treatment of that balance.

Events are explicit uses, signed adjustments, or expirations. Each identifies its tax year, sequence, observation time, reason, and pinned calculation package. Transfers and changes of owner or tax character are not supported implicitly.

Each year's reconciliation is:

```text
closing = opening + adjustments - used - expired
next year's opening = previous year's closing
```

Balances cannot be overdrawn, reports cover consecutive years, and use cannot occur after the declared expiration year. Expiration needs an explicit event and a zero closing balance. Observation order and tax-year order remain distinct so a later recorded adjustment can address an earlier year.

The example begins with a synthetic $120 balance, uses $50 in 2025, and carries $70 into 2026. A later snapshot records another $10 use and closes at $60. The first snapshot remains archived.

A new carryover revision retains its immutable origin/owner/character and the exact prefix of prior events. It may append events and reconcile revised derived balances. Each logical history has one root and cannot fork. Separate hypothetical scenarios need separate logical histories rather than duplicate active roots.

## Validation and remaining boundaries

CI runs schema/type/reference checks, temporal resolution, archive preservation, allocation conservation, and carryover reconciliation tests. The normal command can also run against a baseline:

```sh
.venv/bin/python tools/model/validate_model.py --baseline-ref HEAD^
```

The first migration accepts a 0.2 baseline without interaction records. Later changes compare existing archives strictly. An intentional future schema migration needs an explicit migration strategy instead of silently rehashing old archives.

Source-grounded expiration policies, legal allocation methods, reviewed elections, and complete rule-package execution remain future capabilities. The current tooling verifies the contracts and synthetic assertions, not the whole tax code.
