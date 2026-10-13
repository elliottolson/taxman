"""Structural checks for synthetic time, allocation, and carryover contracts."""
from datetime import date, datetime
from fractions import Fraction
import hashlib
import json

from validate_model import ModelError, check_schema, require


def digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def seal(record):
    return digest({k: v for k, v in record.items() if k != 'sha256'})


def cents(value):
    """Parse schema-validated exact cents without floats or decimal context rounding."""
    negative = value.startswith('-')
    whole, fraction = value.lstrip('-').split('.')
    result = int(whole) * 100 + int(fraction)
    return -result if negative else result


def instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def contains(start, end, point):
    return start <= point and (end is None or point < end)


def overlap(a_start, a_end, b_start, b_end):
    return (a_end is None or b_start < a_end) and (b_end is None or a_start < b_end)


def resolve_revision(revisions, rule_ref, context):
    """Resolve an explicit historical context; never default to latest."""
    candidates = []
    for revision in revisions:
        if revision['rule_ref'] != rule_ref:
            continue
        years = revision['tax_years']
        if not contains(years['start'], years['end_exclusive'], context['tax_year']):
            continue
        known = instant(context['known_at'])
        end = instant(revision['superseded_at']) if revision['superseded_at'] else None
        if not contains(instant(revision['recorded_at']), end, known):
            continue
        window = revision['transaction_dates']
        if window is not None:
            require(context['transaction_date'] is not None, 'Missing transaction date for temporal selection')
            end = date.fromisoformat(window['end_exclusive']) if window['end_exclusive'] else None
            if not contains(date.fromisoformat(window['start']), end, date.fromisoformat(context['transaction_date'])):
                continue
        candidates.append(revision)
    require(len(candidates) == 1, 'Temporal selection must have exactly one matching revision')
    return candidates[0]


def index(records, name):
    result = {record['id']: record for record in records}
    require(len(result) == len(records), f'Duplicate {name} ID')
    return result


def preserve_history(data, previous):
    """Check published archives against a previous Git revision, when supplied."""
    if previous is None:
        return
    for section in ['definition_snapshots', 'package_snapshots', 'carryovers']:
        current = index(data[section], section)
        for old in previous[section]:
            require(old['id'] in current and current[old['id']] == old, f'Historical {section} cannot be changed or removed')
    current = index(data['rule_revisions'], 'rule revision')
    for old in previous['rule_revisions']:
        require(old['id'] in current, 'Historical rule revision cannot be removed')
        new = current[old['id']]
        require({k: v for k, v in new.items() if k != 'superseded_at'} == {k: v for k, v in old.items() if k != 'superseded_at'}, 'Historical rule revision cannot be rewritten')
        if old['superseded_at'] is not None:
            require(new['superseded_at'] == old['superseded_at'], 'Historical supersession cannot be rewritten')


def validate_interactions(data, schema, model, catalog, validate_snapshot, previous=None):
    check_schema(data, schema)
    preserve_history(data, previous)
    concepts = {c['id'] for family in catalog['families'] for c in family['concepts']}
    symbols = {f'{kind}:{record["id"]}': record for kind, section in [('fact', 'facts'), ('rule', 'rules'), ('parameter', 'parameters')] for record in model[section]}
    snapshots = index(data['definition_snapshots'], 'definition snapshot')
    revisions = index(data['rule_revisions'], 'rule revision')
    packages = index(data['package_snapshots'], 'package snapshot')
    subjects = index(data['subjects'], 'subject')
    limits = index(data['shared_limits'], 'shared limit')
    ledgers = index(data['carryovers'], 'carryover')
    index(data['allocations'], 'allocation')
    versions = set()
    for snapshot in snapshots.values():
        require(snapshot['sha256'] == digest(snapshot['definition']), 'Definition snapshot hash mismatch')
        validate_snapshot(snapshot['definition'])
    for revision in revisions.values():
        require(revision['rule_ref'] in symbols and revision['rule_ref'].startswith('rule:'), 'Unknown temporal rule reference')
        require(revision['definition_snapshot'] in snapshots, 'Unknown definition snapshot')
        require(snapshots[revision['definition_snapshot']]['definition']['id'] == revision['rule_ref'][5:], 'Snapshot belongs to another rule')
        key = (revision['rule_ref'], revision['version'])
        require(key not in versions, 'Duplicate rule version'); versions.add(key)
        years = revision['tax_years']
        require(years['end_exclusive'] is None or years['start'] < years['end_exclusive'], 'Invalid effective tax-year interval')
        transaction = revision['transaction_dates']
        if transaction:
            require(transaction['end_exclusive'] is None or transaction['start'] < transaction['end_exclusive'], 'Invalid transaction-date interval')
        start = instant(revision['recorded_at'])
        require(instant(revision['source_published_at']) <= start, 'Source publication cannot follow observation')
        require(revision['superseded_at'] is None or start < instant(revision['superseded_at']), 'Invalid knowledge interval')
        if revision['supersedes'] is not None:
            require(revision['change_kind'] == 'correction' and revision['supersedes'] in revisions, 'Unknown correction predecessor')
            old = revisions[revision['supersedes']]
            require(old['rule_ref'] == revision['rule_ref'] and old['superseded_at'] == revision['recorded_at'], 'Correction must close its predecessor knowledge interval')
            require(instant(old['recorded_at']) < start, 'Correction predecessor must be earlier')
            require(tuple(map(int, old['version'].split('.'))) < tuple(map(int, revision['version'].split('.'))), 'Rule version must increase')
        else:
            require(revision['change_kind'] == 'initial', 'Correction requires a predecessor')
        if revision['superseded_at'] is not None:
            require(sum(r['supersedes'] == revision['id'] for r in revisions.values()) == 1, 'Superseded revision needs exactly one successor')
    rows = list(revisions.values())
    for i, left in enumerate(rows):
        for right in rows[i + 1:]:
            if left['rule_ref'] != right['rule_ref']:
                continue
            a, b = left['tax_years'], right['tax_years']
            years_overlap = overlap(a['start'], a['end_exclusive'], b['start'], b['end_exclusive'])
            knowledge_overlap = overlap(instant(left['recorded_at']), instant(left['superseded_at']) if left['superseded_at'] else None, instant(right['recorded_at']), instant(right['superseded_at']) if right['superseded_at'] else None)
            a, b = left['transaction_dates'], right['transaction_dates']
            dates_overlap = overlap(date.fromisoformat(a['start']) if a else date.min, date.fromisoformat(a['end_exclusive']) if a and a['end_exclusive'] else None, date.fromisoformat(b['start']) if b else date.min, date.fromisoformat(b['end_exclusive']) if b and b['end_exclusive'] else None)
            require(not (years_overlap and knowledge_overlap and dates_overlap), 'Ambiguous temporal revision overlap')
    for package in packages.values():
        require(package['sha256'] == seal(package), 'Package snapshot hash mismatch')
        context = package['context']
        require(context['tax_year'] in model['candidate_tax_years'], 'Package tax year outside model')
        require(instant(context['known_at']) <= instant(package['created_at']), 'Package cannot observe future knowledge')
        pins = [pin['rule_ref'] for pin in package['rule_pins']]
        require(len(pins) == len(set(pins)), 'Duplicate rule pin')
        for pin in package['rule_pins']:
            require(pin['revision_id'] in revisions, 'Unknown pinned revision')
            chosen = resolve_revision(rows, pin['rule_ref'], context)
            require(chosen['id'] == pin['revision_id'], 'Pinned revision does not match historical context')
            require(pin['definition_sha256'] == snapshots[chosen['definition_snapshot']]['sha256'], 'Pinned definition hash mismatch')
    for subject in subjects.values():
        require(subject['id'].startswith(subject['kind'] + ':'), 'Subject kind/ID mismatch')
        if subject['kind'] == 'household':
            require(subject['household_id'] is None, 'Household cannot have a parent household')
        else:
            require(subject['household_id'] in subjects and subjects[subject['household_id']]['kind'] == 'household', 'Unknown subject household')
            if subject['kind'] == 'return':
                members = subject['taxpayer_ids']
                require(len(members) == len(set(members)), 'Duplicate return taxpayer')
                require(all(m in subjects and subjects[m]['kind'] == 'taxpayer' and subjects[m]['household_id'] == subject['household_id'] for m in members), 'Return taxpayer must belong to its household')

    def binding(value):
        require(value['reference'] in symbols, 'Unknown amount binding')
        record = symbols[value['reference']]
        require(record['value_type'] == 'Money' and record['shape'] == 'scalar', 'Amount binding must be scalar Money')
        require(value['subject_id'] in subjects, 'Unknown binding subject')
        require(record['scope'] == subjects[value['subject_id']]['kind'], 'Amount binding subject scope mismatch')
        require(not (value['reference'].startswith('parameter:') and record['axes']), 'Indexed capacity requires a resolved scalar binding')

    def same_owner_group(owner_id, claimant_id):
        owner, claimant = subjects[owner_id], subjects[claimant_id]
        if owner['kind'] == 'household':
            return claimant_id == owner_id or claimant['household_id'] == owner_id
        if owner['kind'] == 'return':
            return claimant_id == owner_id or claimant_id in owner['taxpayer_ids']
        return claimant_id == owner_id

    for limit in limits.values():
        require(limit['concept_id'] in concepts, 'Unknown shared-limit concept')
        require(limit['tax_year'] in model['candidate_tax_years'], 'Shared-limit year outside model')
        require(limit['owner_id'] in subjects, 'Unknown shared-limit owner')
        binding(limit['capacity_binding'])
        require(limit['capacity_binding']['subject_id'] == limit['owner_id'], 'Capacity binding must belong to limit owner')
        claims = index(limit['claims'], 'claim')
        bindings = [(c['demand_binding']['reference'], c['demand_binding']['subject_id']) for c in claims.values()]
        require(len(bindings) == len(set(bindings)), 'Shared-limit claim duplicates an amount binding')
        for claim in claims.values():
            binding(claim['demand_binding'])
            require(same_owner_group(limit['owner_id'], claim['demand_binding']['subject_id']), 'Claimant outside shared-limit owner group')
    allocation_cases = {}
    for allocation in data['allocations']:
        require(allocation['limit_id'] in limits, 'Unknown allocation limit')
        limit = limits[allocation['limit_id']]
        claims = {c['claim_id']: c for c in allocation['claims']}
        outputs = {c['claim_id']: c for c in allocation['outputs']}
        expected = {c['id'] for c in limit['claims']}
        require(len(claims) == len(allocation['claims']) and len(outputs) == len(allocation['outputs']), 'Duplicate allocation claim')
        require(set(claims) == set(outputs) == expected, 'Allocation must account for every limit claim exactly once')
        case_key = (allocation['scenario_id'], allocation['limit_id'])
        inputs = (allocation['capacity'], tuple(sorted((key, row['requested']) for key, row in claims.items())))
        if case_key in allocation_cases:
            prior_inputs, confirmed = allocation_cases[case_key]
            require(prior_inputs == inputs, 'Allocation alternatives in one scenario must use identical capacity and demands')
            require(not (confirmed and allocation['status'] == 'confirmed'), 'Only one allocation can be confirmed per scenario and limit')
            allocation_cases[case_key] = (inputs, confirmed or allocation['status'] == 'confirmed')
        else:
            allocation_cases[case_key] = (inputs, allocation['status'] == 'confirmed')
        capacity = cents(allocation['capacity'])
        amounts = {key: cents(row['allocated']) for key, row in outputs.items()}
        require(all(amounts[k] <= cents(claims[k]['requested']) for k in claims), 'Allocation exceeds claimant demand')
        require(sum(amounts.values()) <= capacity, 'Allocation exceeds shared capacity')
        require(sum(amounts.values()) + cents(allocation['unallocated']) == capacity, 'Allocation conservation mismatch')
        if allocation['method'] == 'explicit':
            require(allocation['remainder_policy'] == 'explicit', 'Explicit allocation needs explicit remainder policy')
        else:
            require(allocation['remainder_policy'] == 'largest_remainder_by_claim_id', 'Proportional allocation needs deterministic remainder policy')
            weights = {k: Fraction(int(v['weight']['numerator']), int(v['weight']['denominator'])) for k, v in claims.items()}
            total = sum(weights.values())
            require(total > 0, 'Proportional weights must have a positive sum')
            raw = {k: Fraction(capacity) * w / total for k, w in weights.items()}
            planned = {k: v.numerator // v.denominator for k, v in raw.items()}
            remaining = capacity - sum(planned.values())
            order = sorted(claims, key=lambda k: (-(raw[k] - planned[k]), k))
            for k in order[:remaining]:
                planned[k] += 1
            require(planned == amounts and allocation['unallocated'] == '0.00', 'Proportional allocation/remainder mismatch')
    ledger_versions = set()
    roots, successors = {}, {}
    for ledger in ledgers.values():
        if ledger['previous_revision'] is None:
            require(ledger['logical_id'] not in roots, 'Carryover logical history must have exactly one root')
            roots[ledger['logical_id']] = ledger['id']
        else:
            require(ledger['previous_revision'] not in successors, 'Carryover history cannot fork')
            successors[ledger['previous_revision']] = ledger['id']
    for ledger in ledgers.values():
        require(ledger['sha256'] == seal(ledger), 'Carryover snapshot hash mismatch')
        version = (ledger['logical_id'], ledger['version'])
        require(version not in ledger_versions, 'Duplicate carryover version'); ledger_versions.add(version)
        require(ledger['owner_id'] in subjects, 'Unknown carryover owner')
        require(subjects[ledger['owner_id']]['kind'] in {'taxpayer', 'return'}, 'Carryover owner must be taxpayer or return')
        require(ledger['concept_id'] in concepts, 'Unknown carryover concept')
        require(ledger['origin_tax_year'] < ledger['opening_tax_year'], 'Carryover opening must follow origin year')
        expiry = ledger['expires_after_tax_year']
        require(expiry is None or ledger['opening_tax_year'] <= expiry, 'Carryover opens after expiration')
        if ledger['previous_revision'] is not None:
            require(ledger['previous_revision'] in ledgers, 'Unknown carryover predecessor')
            old = ledgers[ledger['previous_revision']]
            for key in ['logical_id', 'owner_id', 'concept_id', 'tax_character', 'currency', 'origin_tax_year', 'opening_tax_year', 'opening_amount', 'opening_provenance']:
                require(old[key] == ledger[key], 'Carryover revision changes immutable origin/owner/character')
            require(instant(old['recorded_at']) < instant(ledger['recorded_at']), 'Carryover predecessor must be earlier')
            require(tuple(map(int, old['version'].split('.'))) < tuple(map(int, ledger['version'].split('.'))), 'Carryover version must increase')
            require(ledger['events'][:len(old['events'])] == old['events'], 'Carryover events cannot be rewritten')
        events = index(ledger['events'], 'carryover event')
        pairs = [(event['tax_year'], event['sequence']) for event in events.values()]
        require(len(pairs) == len(set(pairs)), 'Duplicate carryover event order')
        prior_time = None
        for event in ledger['events']:
            require(event['tax_year'] >= ledger['opening_tax_year'], 'Carryover event precedes opening year')
            observed = instant(event['recorded_at'])
            require(observed <= instant(ledger['recorded_at']), 'Carryover event follows snapshot observation')
            require(prior_time is None or prior_time <= observed, 'Carryover events must preserve observation order'); prior_time = observed
            require(event['calculation_package'] in packages, 'Unknown carryover calculation package')
            package = packages[event['calculation_package']]
            require(package['context']['tax_year'] == event['tax_year'], 'Carryover event/package year mismatch')
            require(instant(package['created_at']) <= observed, 'Carryover event precedes its package')
            amount = cents(event['amount'])
            require(amount != 0, 'Carryover event amount must be nonzero')
            if event['kind'] != 'adjustment':
                require(amount > 0, 'Carryover use/expiration must be positive')
            if event['kind'] == 'use':
                require(expiry is None or event['tax_year'] <= expiry, 'Carryover use after expiration')
            if event['kind'] == 'expiration':
                require(expiry is not None and event['tax_year'] == expiry, 'Expiration event must match expiry year')
        reports = ledger['year_balances']
        years = [row['tax_year'] for row in reports]
        require(years == list(range(ledger['opening_tax_year'], years[-1] + 1)), 'Carryover reports must cover consecutive years from opening')
        require(all(event['tax_year'] in years for event in events.values()), 'Carryover event has no year report')
        balance = cents(ledger['opening_amount'])
        for report in reports:
            require(cents(report['opening']) == balance, 'Carryover opening balance mismatch')
            year_events = sorted((e for e in events.values() if e['tax_year'] == report['tax_year']), key=lambda e: e['sequence'])
            require([e['sequence'] for e in year_events] == list(range(1, len(year_events) + 1)), 'Carryover sequence must be consecutive within a year')
            used = expired = adjustments = 0
            for event in year_events:
                amount = cents(event['amount'])
                if event['kind'] == 'use':
                    used += amount; balance -= amount
                elif event['kind'] == 'expiration':
                    expired += amount; balance -= amount
                else:
                    adjustments += amount; balance += amount
                require(balance >= 0, 'Carryover event overdraws available balance')
            require((cents(report['used']), cents(report['expired']), cents(report['adjustments']), cents(report['closing'])) == (used, expired, adjustments, balance), 'Carryover year reconciliation mismatch')
            require(expiry is None or report['tax_year'] < expiry or balance == 0, 'Expired carryover must have zero closing balance')
    require(all(ledger['logical_id'] in roots for ledger in ledgers.values()), 'Carryover logical history is missing its root')
    return {'rule_revisions': len(revisions), 'package_snapshots': len(packages), 'shared_limits': len(limits), 'allocations': len(data['allocations']), 'carryover_snapshots': len(ledgers)}
