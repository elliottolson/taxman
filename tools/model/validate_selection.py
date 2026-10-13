"""Finite selection checks and synthetic election replay; not a tax evaluator."""
from itertools import product
from datetime import datetime

from validate_model import ModelError, check_schema, require

MAX_CASES = 4096


def assignments(domains):
    size = 1
    for values in domains.values():
        size *= len(values)
    require(size <= MAX_CASES, 'Finite analysis exceeds 4096 combinations')
    keys = sorted(domains)
    return [dict(zip(keys, values)) for values in product(*(domains[k] for k in keys))]


def condition_matches(condition, values):
    return all(values[k] == v for k, v in condition.items())


def analyze_table(table, domains):
    """Check all known inputs; uncovered inputs may deliberately block."""
    reached = set()
    gaps = []
    for values in assignments(domains):
        hits = [row for row in table['rows'] if condition_matches(row['when'], values)]
        require(table['hit_policy'] != 'unique' or len(hits) <= 1,
                f"Overlapping rows in {table['id']}: {values}")
        if not hits:
            gaps.append(values)
        else:
            reached.add(hits[0]['id'])
    for row in table['rows']:
        require(row['id'] in reached, f"Unreachable row: {table['id']}/{row['id']}")
    require(table['coverage'] != 'complete' or not gaps, f"Uncovered cases in {table['id']}: {gaps[:1]}")
    return {'cases': len(assignments(domains)), 'blocked_cases': gaps}


def analyze_core_decisions(model):
    """Analyze existing expression tables when every condition has a finite domain.

    Unsupported numeric/date predicates are reported as not analyzed, never proven.
    """
    symbols = {f'{kind}:{r["id"]}': r for kind, section in
               [('fact', 'facts'), ('election', 'elections'), ('rule', 'rules')]
               for r in model[section]}
    enums = {e['id']: e['values'] for e in model['enum_domains']}
    reports = {}
    for table in model['decisions']:
        domains = {}

        def inspect(expr):
            kind = expr['kind']
            if kind == 'ref':
                record = symbols[expr['target']]
                require(record['shape'] == 'scalar', 'Non-finite condition')
                if record['value_type'] == 'Boolean':
                    domains[expr['target']] = [False, True]
                elif record['value_type'] == 'Enum':
                    domains[expr['target']] = enums[record['enum_domain']]
                else:
                    raise ModelError('Non-finite condition')
            elif kind == 'literal':
                require(expr['value_type'] in {'Boolean', 'Enum'}, 'Non-finite condition')
            else:
                require(kind == 'apply' and expr['operator'] in {'and', 'or', 'not', 'equal'}, 'Non-finite condition')
                for arg in expr['arguments']:
                    inspect(arg)

        def evaluate(expr, values):
            if expr['kind'] == 'ref':
                return values[expr['target']]
            if expr['kind'] == 'literal':
                return expr['value']
            args = [evaluate(a, values) for a in expr['arguments']]
            op = expr['operator']
            if op == 'equal':
                return args[0] == args[1]
            if op == 'not':
                return not args[0]
            return all(args) if op == 'and' else any(args)

        try:
            for row in table['rows']:
                inspect(row['condition'])
        except ModelError:
            reports[table['id']] = {'status': 'not_analyzed', 'reason': 'non-finite predicate'}
            continue
        reached, gaps = set(), []
        cases = assignments(domains)
        for values in cases:
            hits = [row for row in table['rows'] if evaluate(row['condition'], values)]
            require(table['hit_policy'] != 'unique' or len(hits) <= 1,
                    f"Overlapping rows in {table['id']}: {values}")
            if hits:
                reached.add(hits[0]['id'])
            else:
                gaps.append(values)
        for row in table['rows']:
            require(row['id'] in reached, f"Unreachable row: {table['id']}/{row['id']}")
        # Core schema specifies a blocked fallback, not a completeness promise.
        reports[table['id']] = {'status': 'analyzed', 'cases': len(cases), 'blocked_cases': gaps}
    return reports


def route(group, facts):
    """Resolve explicit overrides; any unresolved relevant input blocks."""
    needed = sorted({k for c in group['candidates'] for k in c['when']})
    unresolved = [k for k in needed if k not in facts or facts[k]['state'] != 'confirmed']
    if unresolved:
        return {'status': 'blocked', 'reason': 'unresolved_facts', 'facts': unresolved}
    values = {k: facts[k]['value'] for k in needed}
    active = [c for c in group['candidates'] if condition_matches(c['when'], values)]
    suppressed = {target for c in active for target in c['overrides']}
    winners = sorted(c['id'] for c in active if c['id'] not in suppressed)
    if len(winners) != 1:
        return {'status': 'blocked', 'reason': 'conflicting_methods' if winners else 'no_method', 'candidates': winners}
    winner = next(c for c in active if c['id'] == winners[0])
    return {'status': 'selected', 'candidate': winner['id'], 'target': winner['target'],
            'explanation': winner['explanation'], 'suppressed': sorted(suppressed)}


def authorized_route(group, policy, case, facts):
    selection = replay_election(policy, case)
    if selection['status'] != 'confirmed':
        return {'status': 'blocked', 'reason': selection['reason']}
    binding = group['election_binding']
    require(binding['input'] not in facts, 'Election selection cannot be supplied as an ordinary fact')
    values = dict(facts)
    values[binding['input']] = {'state': 'confirmed', 'value': binding['choice_values'][selection['choice']]}
    return route(group, values)


def instant(value):
    require(value.endswith('Z'), 'Timestamp must use UTC Z')
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def replay_election(policy, case):
    """Replay a synthetic choice history and resolve it at an explicit instant."""
    require(case['tax_year'] == policy['tax_year'], 'Election policy year mismatch')
    choices = {c['id']: c for c in policy['choices']}
    events, active = {}, None
    last_time = None
    as_of = instant(case['as_of'])
    for event in case['events']:
        require(event['id'] not in events, 'Duplicate election event')
        time = instant(event['at'])
        require(time <= as_of and (last_time is None or time >= last_time), 'Election event chronology')
        last_time = time
        require(event['return_id'] == case['return_id'] and event['owner_id'] == case['owner_id']
                and event['tax_year'] == case['tax_year'], 'Election event context mismatch')
        require(event['return_revision'] in case['return_revisions'], 'Unknown return revision')
        if event['action'] == 'confirm':
            require(active is None, 'Revoke an active choice before replacing it')
            require(event['choice'] in choices, 'Unknown election choice')
            require(event['authorized_by'] == case['owner_id'], 'Election lacks owner confirmation')
            require(time <= instant(policy['confirmation_deadline']), 'Election confirmation deadline passed')
            eligibility = event['eligibility']
            require(eligibility['fact'] == choices[event['choice']]['eligibility_fact'], 'Wrong election eligibility fact')
            require(eligibility['state'] == 'confirmed' and eligibility['value'] is True, 'Election eligibility unresolved or false')
            active = event
        else:
            require(active is not None and event['confirmation_id'] == active['id'], 'Revocation must reference active confirmation')
            require(event['return_revision'] == active['return_revision'], 'Revocation revision mismatch')
            require(event['authorized_by'] == case['owner_id'], 'Revocation lacks owner confirmation')
            require(policy['revocation_allowed'], 'Election cannot be revoked')
            require(time <= instant(policy['revocation_deadline']), 'Election revocation deadline passed')
            active = None
        events[event['id']] = event
    if active is None:
        return {'status': 'blocked', 'reason': 'confirmation_required'}
    if active['return_revision'] != case['current_return_revision']:
        return {'status': 'blocked', 'reason': 'stale_return_revision', 'confirmation_id': active['id']}
    choice = choices[active['choice']]
    return {'status': 'confirmed', 'choice': active['choice'], 'confirmation_id': active['id'],
            'effects': [{'target': target, 'start_year': case['tax_year'],
                         'end_year_exclusive': case['tax_year'] + policy['effect_years']} for target in choice['effects']]}


def validate_selection(data, schema, model):
    check_schema(data, schema)
    domains = {d['id']: d['values'] for d in data['domains']}
    require(len(domains) == len(data['domains']), 'Duplicate selection domain')
    for values in domains.values():
        require(len({(type(v).__name__, str(v)) for v in values}) == len(values), 'Duplicate domain value')
        require(all(type(v) is bool for v in values) or all(type(v) is str for v in values), 'Mixed domain types')
        if type(values[0]) is bool:
            require(set(values) == {False, True}, 'Boolean domain must be complete')
    inputs = {i['id']: i['domain'] for i in data['inputs']}
    require(len(inputs) == len(data['inputs']), 'Duplicate selection input')
    require(all(d in domains for d in inputs.values()), 'Unknown selection domain')
    groups = {g['id']: g for g in data['routes']}
    tables = {t['id']: t for t in data['tables']}
    policies = {p['id']: p for p in data['elections']}
    for section, mapping in [('routes', groups), ('tables', tables), ('elections', policies)]:
        require(len(data[section]) == len(mapping), f'Duplicate {section} ID')
    targets = {f'{kind}:{r["id"]}': r for kind, section in [('rule', 'rules'), ('fact', 'facts')] for r in model[section]}

    def target_type(key):
        r = targets[key]
        return r['value_type'], r['shape'], r['scope'], r.get('enum_domain')

    def predicate(condition):
        for key, value in condition.items():
            require(key in inputs, 'Unknown predicate input')
            require(any(type(value) is type(v) and value == v for v in domains[inputs[key]]), 'Predicate value outside domain')

    for group in groups.values():
        candidates = {c['id']: c for c in group['candidates']}
        require(len(candidates) == len(group['candidates']), 'Duplicate route candidate')
        for c in candidates.values():
            predicate(c['when'])
            require(c['target'] in targets, 'Unknown route target')
            require(len(c['overrides']) == len(set(c['overrides'])), 'Duplicate override')
            require(all(t in candidates and t != c['id'] for t in c['overrides']), 'Invalid override target')
        require(len({target_type(c['target']) for c in candidates.values()}) == 1, 'Route target type/scope mismatch')
        def visit(key, path):
            require(key not in path, 'Override cycle')
            for target in candidates[key]['overrides']:
                visit(target, path | {key})
        for key in candidates:
            visit(key, set())
        # Overrides are explicit direct edges, not implicit transitive priorities.
    route_reports = {}
    for group in groups.values():
        keys = {k for c in group['candidates'] for k in c['when']}
        cases = assignments({k: domains[inputs[k]] for k in keys})
        blocked = []
        for values in cases:
            result = route(group, {k: {'state': 'confirmed', 'value': v} for k, v in values.items()})
            if result['status'] == 'blocked':
                blocked.append({'inputs': values, 'result': result})
        route_reports[group['id']] = {'cases': len(cases), 'blocked_cases': blocked}
    table_reports = {}
    for table in tables.values():
        require(len({r['id'] for r in table['rows']}) == len(table['rows']), 'Duplicate table row')
        for row in table['rows']:
            predicate(row['when'])
            require(row['target'] in targets, 'Unknown table target')
        require(len({target_type(r['target']) for r in table['rows']}) == 1, 'Table target type/scope mismatch')
        keys = {k for r in table['rows'] for k in r['when']}
        table_reports[table['id']] = analyze_table(table, {k: domains[inputs[k]] for k in keys})
    for policy in policies.values():
        require(instant(policy['revocation_deadline']) >= instant(policy['confirmation_deadline']), 'Revocation deadline before confirmation deadline')
        require(len({c['id'] for c in policy['choices']}) == len(policy['choices']), 'Duplicate election choice')
        for choice in policy['choices']:
            require(choice['eligibility_fact'] in inputs and domains[inputs[choice['eligibility_fact']]] == [False, True], 'Eligibility must use Boolean input')
            require(all(t in targets for t in choice['effects']), 'Unknown election effect')
    for group in groups.values():
        binding = group['election_binding']
        require(binding['policy_id'] in policies, 'Unknown bound election policy')
        require(set(binding['choice_values']) == {c['id'] for c in policies[binding['policy_id']]['choices']}, 'Election binding choices mismatch')
        for value in binding['choice_values'].values():
            predicate({binding['input']: value})
        require(any(binding['input'] in c['when'] for c in group['candidates']), 'Election binding does not affect routing')
    for case in data['route_cases']:

        require(case['route_id'] in groups, 'Unknown route case group')
        for key, fact in case['facts'].items():
            predicate({key: fact['value']})
        require(route(groups[case['route_id']], case['facts']) == case['expected'], f"Route expectation mismatch: {case['id']}")
    for case in data['election_cases']:
        require(case['policy_id'] in policies, 'Unknown election policy')
        require(len(set(case['return_revisions'])) == len(case['return_revisions']) and case['current_return_revision'] in case['return_revisions'], 'Invalid return revisions')
        require(replay_election(policies[case['policy_id']], case) == case['expected'], f"Election expectation mismatch: {case['id']}")
    election_cases = {c['id']: c for c in data['election_cases']}
    for case in data['selection_cases']:
        require(case['route_id'] in groups and case['election_case_id'] in election_cases, 'Unknown authorized selection reference')
        group = groups[case['route_id']]
        election_case = election_cases[case['election_case_id']]
        require(election_case['policy_id'] == group['election_binding']['policy_id'], 'Bound election policy mismatch')
        for key, fact in case['facts'].items():
            predicate({key: fact['value']})
        result = authorized_route(group, policies[election_case['policy_id']], election_case, case['facts'])
        require(result == case['expected'], f"Authorized route expectation mismatch: {case['id']}")
    for section in ['route_cases', 'election_cases', 'selection_cases']:

        require(len({c['id'] for c in data[section]}) == len(data[section]), 'Duplicate case ID')
    return {'routes': route_reports, 'tables': table_reports, 'selection_cases': len(data['selection_cases']), 'route_cases': len(data['route_cases']), 'election_cases': len(data['election_cases'])}
