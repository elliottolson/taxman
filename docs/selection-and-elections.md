# Selection, exceptions, and elections

The [selection contract](../model/selection-model.json) and [closed schema](../schemas/selection-model.schema.json) add synthetic method routing, election histories, and finite consistency checks. The deadlines, election duration, and predicates are invented. References to draft deduction rules test model compatibility; they do not assert real deduction election law. Production remains disabled.

## Explicit method routing

A route contains candidates with input predicates, compatible result types/scopes, explicit `overrides` edges, and explanation text. An applicable exception displaces only the candidates it explicitly overrides. Edges are direct, not an inferred transitive legal hierarchy. Cycles, self edges, unknown targets, and incompatible outputs fail validation.

Author order has no effect. After checking every relevant input is confirmed, routing finds applicable candidates and suppresses explicitly overridden candidates. Exactly one survivor selects a target. No survivor or competing survivors blocks the result. Missing, invalid, provisional, estimated, and not-applicable states block rather than becoming false. This initial policy conservatively requires every routing input, even when further predicate analysis might prove one irrelevant.

The example base method applies generally. Two alternatives can displace it, but neither displaces the other. When both apply, the validator exposes the input combination and conflicting candidates. A compiler must not invent a priority or select the lowest calculated tax. A legitimate precedence rule requires a reviewed interpretation and an authored edge.

Low-level `route_cases` test applicability alone. `selection_cases` combine routing with election replay: an explicit binding maps each confirmed election choice to a routing input. Ordinary supplied facts cannot override that input. Unconfirmed, revoked, or stale choices block this combined route. This is a synthetic executable contract test, not a production tax engine.

## Election lifecycle

A policy specifies its tax year, choices, Boolean eligibility inputs, confirmation and revocation deadlines, whether revocation is allowed, and affected rule/fact targets. A confirmation event identifies the owner, return, exact return revision, choice, eligibility assertion, authorizing owner, and UTC timestamp. A proposed choice alone has no effect; in this prototype proposals are outside the confirmation log.

Replay requires confirmed true eligibility and matching owner, return, year, and known revision. Confirmation deadlines are inclusive UTC instants. Local filing deadlines, extensions, relief, and consent rules require later researched policies. `authorized_by` is a synthetic identity assertion, not authentication or a legal signature.

An active choice cannot be replaced silently. Revocation must identify its active confirmation and revision, be authorized, be permitted, and occur by its deadline. A subsequent confirmation can bind a different revision. Replay at `as_of` requires an ordered event prefix ending at or before that instant; future events in the supplied prefix are rejected. Equal timestamps use array order. A changed current return revision makes the old confirmation stale.

Confirmed choices emit explicit effect intervals `[tax_year, tax_year + effect_years)` linked to the confirmation ID. These describe potential future-year effects; they are not automatic inherited elections. Revocation removes the active effects in the replayed state. Propagating a change into already filed years, relief, transfers, per-choice durations, and consent-based revocations remain research work.

Revision IDs and eligibility values are asserted test inputs. Production must bind them to immutable return content, fact provenance, archived election policies, authenticated authorization, and filing signatures. Election logs here have no cross-commit immutability guarantee; archived rule packages and carryover ledgers retain their separate existing checks.

## Finite decision consistency

The validator enumerates complete declared Boolean and enum input domains, up to 4,096 combinations per analysis. It checks:

- Unique tables: overlapping rows fail with a concrete input witness, including nonidentical predicates.
- First-match tables: rows that can never win fail. Author order is intentional only for these tables.
- Coverage: `complete` tables reject gaps; `blocked_gaps` tables report every uncovered known-input combination.
- Routing: conflicting or absent methods are reported with the input combinations that produce them.
- Targets and predicates: unknown references, invalid domain values, mixed domain types, and incompatible output types/scopes fail.

Existing core decision expressions are also analyzed when their conditions contain scalar Boolean/enum references, literals, equality, and Boolean operators. Their blocked fallback allows gaps, which are reported. Numeric, date, lookup, and other predicates receive `not_analyzed`; this is not a proof of consistency. Exceeding the case limit fails explicitly. Enumeration treats input combinations independently and conservatively; it does not infer constraints between facts or prove that every combination is legally reachable. Enum completeness depends on the authored domain being complete.

Known-input coverage and missing-information handling are different checks. Complete tables do not make unknown inputs usable. This milestone adds no money calculations, reviewed tax interpretations, populated annual parameters, or filing capability.

## Next milestone

Bind each tax interpretation and precedence/election policy to precise source claims, applicability periods, review decisions, and independently established fixtures. Then compile a small reviewed package into a reproducible execution plan. Expand numeric/date predicate analysis only with a defined solver and explicit proof boundaries.
