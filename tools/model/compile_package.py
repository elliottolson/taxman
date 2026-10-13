"""Portable compiler and bounded synthetic harness; not a production tax engine."""
from copy import deepcopy

from validate_model import ModelError, require, validate
from validate_interactions import digest, seal, instant, contains, cents, index

VERSION = '0.1.0'
SECTIONS = {'fact':'facts','parameter':'parameters','rule':'rules','decision':'decisions','election':'elections','module':'modules'}
OPERATORS = {'add','subtract','min','max','sum','equal','less_than','less_equal','and','or','not'}


def refs(expr):
    if expr['kind'] == 'ref':
        return {expr['target']}
    if expr['kind'] == 'literal':
        return set()
    if expr['kind'] == 'lookup':
        raise ModelError('Indexed parameter lookup is unsupported by this compiler')
    require(expr['operator'] in OPERATORS, 'Unsupported expression operator')
    return set().union(*(refs(a) for a in expr['arguments']))


def prerequisites(target, record):
    kind = target.split(':')[0]
    if kind in {'fact','parameter'}:
        return set()
    if kind == 'rule':
        result = refs(record['applicability'])
        execution = record['execution']
        if execution['kind'] == 'expression':
            return result | refs(execution['expression'])
        if execution['kind'] == 'decision':
            return result | {'decision:'+execution['decision_id']}
        raise ModelError('Module execution is unsupported by this compiler')
    if kind == 'decision':
        return set().union(*(refs(r['condition']) | refs(r['result']) for r in record['rows']))
    if kind == 'election':
        return {record['selection_fact']} | set().union(*(refs(c['eligibility']) for c in record['choices']))
    raise ModelError('Module execution is unsupported by this compiler')


def compile_package(program, request, schemas, catalog, registry, ledger=None):
    require(program['mode'] in {'synthetic','tax_research'}, 'Unknown compilation mode')
    require(request['tax_year'] in program['model']['candidate_tax_years'], 'Tax year outside program')
    model = deepcopy(program['model'])
    revisions = index(program['rule_revisions'], 'rule revision')
    selected = {}
    # No implicit current/latest rule fallback, including for unreachable rules.
    for i, rule in enumerate(model['rules']):
        target = 'rule:'+rule['id']
        matches = [r for r in revisions.values() if r['target'] == target
                   and contains(r['tax_years']['start'],r['tax_years']['end_exclusive'],request['tax_year'])
                   and contains(instant(r['recorded_at']),instant(r['superseded_at']) if r['superseded_at'] else None,instant(request['known_at']))]
        require(len(matches) == 1, 'Rule selection requires exactly one revision: '+target)
        r = matches[0]
        require(r['definition']['id'] == rule['id'] and seal(r) == r['sha256'], 'Revision definition or digest mismatch')
        model['rules'][i] = deepcopy(r['definition'])
        selected[target] = r
    validate(model, catalog, schemas, registry)
    bindings = index(program['parameter_bindings'], 'parameter binding')
    selected_parameters = {}
    for parameter in model['parameters']:
        target = 'parameter:' + parameter['id']
        matches = [b for b in bindings.values() if b['target'] == target and b['tax_year'] == request['tax_year']]
        if matches:
            require(len(matches) == 1, 'Conflicting annual parameter bindings')
            b = matches[0]
            require(b['definition_sha256'] == digest(parameter), 'Stale parameter binding')
            parameter['value'] = b['value']
            selected_parameters[target] = b
    symbols = {f'{kind}:{r["id"]}': r for kind, section in SECTIONS.items() for r in model[section]}
    require(len(request['outputs']) == len(set(request['outputs'])) and request['outputs'], 'Invalid requested outputs')
    graph, visiting, ordered = {}, set(), []
    def visit(target):
        require(target in symbols, 'Missing execution dependency: '+target)
        require(target not in visiting, 'Execution dependency cycle')
        if target in graph:
            return
        visiting.add(target)
        r = symbols[target]
        require(r['scope'] == 'return', 'Subject binding is unsupported outside return scope')
        if target.startswith('rule:'):
            require(r['rounding_policy'] == 'no_rounding', 'Unsupported rounding policy')
        require(r.get('value_type') in {'Money','Boolean','Enum'}, 'Unsupported compiler value type')
        require(r['shape'] == 'scalar' or r['value_type'] == 'Money', 'Unsupported collection type')
        deps = prerequisites(target,r)
        if target.startswith('parameter:'):
            require(target in selected_parameters, 'Missing annual parameter binding')
            require(not r['axes'], 'Indexed parameter lookup is unsupported by this compiler')
            require(r['value_status'] != 'unpopulated' and r['value'] is not None, 'Missing annual parameter value')
            validate_value(r, r['value'], model)
        for dep in sorted(deps):
            visit(dep)
        graph[target] = deps
        visiting.remove(target)
        ordered.append(target)
    for target in sorted(request['outputs']):
        visit(target)
    evidence_ids = sorted({e['source_id'] for target in graph for e in symbols[target].get('evidence',[])})
    if program['mode'] == 'tax_research':
        require(ledger is not None, 'Tax compilation needs the claim ledger')
        from validate_claims import replay_reviews
        states = replay_reviews(ledger, request['known_at'])
        for target in graph:
            if target.startswith('fact:'):
                continue
            require(symbols[target]['status'] == 'reviewed', 'Draft tax definition blocks compilation: '+target)
            supported = [c for c in ledger['claims'] if any(x['target']==target and x['target_sha256']==digest(symbols[target]) for x in c['consumers'])
                         and c['applicability']['start'] <= request['tax_year'] < c['applicability']['end_exclusive']
                         and states[('claim',c['id'])]=='reviewed']
            require(supported, 'Missing reviewed claim for '+target)
        # A facet claim is not a complete interpretation/coverage proof.
        raise ModelError('Tax package coverage and interpretation acceptance are not implemented')
    source_records = {s['id']:s for s in registry['sources']}
    result = {'package_id':request['id'],'contract_version':VERSION,'compiler_version':VERSION,
              'mode':program['mode'],'production_enabled':False,'tax_year':request['tax_year'],
              'known_at':request['known_at'],'program_sha256':digest(program),
              'outputs':sorted(request['outputs']),'enum_domains':deepcopy(model['enum_domains']),
              'sources':[deepcopy(source_records[id]) for id in evidence_ids],
              'nodes':[{'target':target,'definition':deepcopy(symbols[target]),'definition_sha256':digest(symbols[target]),
                        'revision_id':selected[target]['id'] if target in selected else (selected_parameters[target]['id'] if target in selected_parameters else None),
                        'revision_sha256':selected[target]['sha256'] if target in selected else (digest(selected_parameters[target]) if target in selected_parameters else None),
                        'dependencies':sorted(graph[target])} for target in ordered],
              'input_contracts':[{'target':target,'value_type':symbols[target]['value_type'],'shape':symbols[target]['shape'],
                                  'scope':symbols[target]['scope'],'enum_domain':symbols[target].get('enum_domain')} for target in sorted(graph) if target.startswith('fact:')],
              'election_requirements':sorted(t for t in graph if t.startswith('election:')),
              'limitations':['Synthetic harness only; no legal acceptance or released tax support.','Election lifecycle authorization must be established outside this harness.','No indexed tables, modules, date-sensitive rules, or rounding methods.']}
    result['sha256'] = seal(result)
    return result


def validate_value(record, value, model):
    enums = {d['id']:d['values'] for d in model['enum_domains']}
    def scalar(v):
        typ = record['value_type']
        if typ == 'Money':
            import re
            require(type(v) is str and re.fullmatch(r'-?(0|[1-9][0-9]*)\.[0-9]{2}',v) is not None, 'Invalid exact money value')
        elif typ == 'Boolean':
            require(type(v) is bool, 'Invalid Boolean value')
        else:
            require(type(v) is str and v in enums[record['enum_domain']], 'Invalid enum value')
    if record['shape'] == 'collection':
        require(type(value) is list, 'Collection fact needs a list')
        for item in value:
            scalar(item)
    else:
        scalar(value)


def money(value):
    return ('-' if value < 0 else '') + f'{abs(value)//100}.{abs(value)%100:02d}'


def run_case(package, case):
    """Lazy, exact-cent harness for the declared subset, with sensitive traces."""
    require(seal(package) == package['sha256'], 'Package digest mismatch')
    require(package['mode'] == 'synthetic' and not package['production_enabled'], 'Harness only executes synthetic packages')
    require(package['package_id'] in case['package_ids'], 'Fixture belongs to another package')
    nodes = {n['target']:n for n in package['nodes']}
    require(set(case['inputs']) <= set(package_input['target'] for package_input in package['input_contracts']), 'Unknown case input')
    require(set(case['confirmations']) <= set(package['election_requirements']), 'Unknown election confirmation')
    cache, traces, active = {}, [], set()
    def blocked(reason):
        return {'status':'blocked','reason':reason}
    def value(v):
        return {'status':'value','value':v}
    def expr(expression, deps):
        kind = expression['kind']
        if kind == 'ref':
            deps.add(expression['target'])
            return evaluate(expression['target'])
        if kind == 'literal':
            return value(expression['value'])
        arguments = [expr(a,deps) for a in expression['arguments']]
        if any(a['status'] != 'value' for a in arguments):
            return blocked('unresolved_dependency')
        vals = [a['value'] for a in arguments]
        op = expression['operator']
        if op in {'and','or','not'}:
            return value(not vals[0] if op=='not' else (all(vals) if op=='and' else any(vals)))
        if op in {'equal','less_than','less_equal'}:
            first = expression['arguments'][0]
            typ = nodes[first['target']]['definition']['value_type'] if first['kind'] == 'ref' else (first['value_type'] if first['kind'] == 'literal' else ('Boolean' if first['operator'] in {'and','or','not','equal','less_than','less_equal'} else 'Money'))
            if op != 'equal' or typ == 'Money':
                vals = [cents(v) for v in vals]
            return value(vals[0]==vals[1] if op=='equal' else (vals[0]<vals[1] if op=='less_than' else vals[0]<=vals[1]))
        nums = [cents(v) for v in vals[0]] if op=='sum' else [cents(v) for v in vals]
        number = sum(nums) if op in {'add','sum'} else (nums[0]-nums[1] if op=='subtract' else (min(nums) if op=='min' else max(nums)))
        return value(money(number))
    def evaluate(target):
        require(target in nodes and target not in active, 'Invalid harness dependency')
        if target in cache:
            return cache[target]
        active.add(target)
        r = nodes[target]['definition']
        deps, detail = set(), {}
        kind = target.split(':')[0]
        if kind == 'fact':
            fact = case['inputs'].get(target)
            if fact is None or fact['state'] != 'confirmed':
                result = blocked('unresolved_fact')
                detail['fact_state'] = fact['state'] if fact else 'missing'
            else:
                validate_value(r,fact['value'],package)
                result = value(fact['value'])
                detail['fact_state'] = 'confirmed'
        elif kind == 'parameter':
            result = value(r['value'])
        elif kind == 'election':
            selected = expr({'kind':'ref','target':r['selection_fact']},deps)
            confirmation = case['confirmations'].get(target)
            if selected['status'] != 'value':
                result = selected
            elif confirmation is None:
                result = blocked('confirmation_required')
            elif confirmation['return_revision'] != case['return_revision'] or confirmation['choice'] != selected['value']:
                result = blocked('stale_confirmation')
            else:
                choice = next(c for c in r['choices'] if c['id']==selected['value'])
                eligibility = expr(choice['eligibility'],deps)
                if eligibility['status'] != 'value' or eligibility['value'] is not True:
                    result = blocked('ineligible_or_unresolved_choice')
                else:
                    result = selected
                    detail['confirmation_id'] = confirmation['id']
        elif kind == 'rule':
            applicable = expr(r['applicability'],deps)
            detail['applicability'] = applicable
            if applicable['status'] != 'value':
                result = blocked('unresolved_applicability')
            elif not applicable['value']:
                result = {'status':'not_applicable'}
            else:
                execution = r['execution']
                result = expr(execution['expression'],deps) if execution['kind']=='expression' else expr({'kind':'ref','target':'decision:'+execution['decision_id']},deps)
        else:
            hits, unresolved = [], False
            for row in r['rows']:
                condition = expr(row['condition'],deps)
                if condition['status'] != 'value':
                    unresolved = True
                    break
                if condition['value']:
                    hits.append(row)
                    if r['hit_policy']=='first':
                        break
            if unresolved:
                result = blocked('unresolved_condition')
            elif len(hits)>1:
                result = blocked('conflicting_methods')
            elif not hits:
                result = blocked('no_method') if r['fallback']=='blocked' else {'status':'not_applicable'}
            else:
                detail['selected_row'] = hits[0]['id']
                result = expr(hits[0]['result'],deps)
        if result['status'] == 'value':
            validate_value(r, result['value'], package)
        active.remove(target)
        cache[target] = result
        traces.append({'target':target,'definition_sha256':nodes[target]['definition_sha256'],
                       'result':deepcopy(result),'used_dependencies':sorted(deps),'detail':detail,
                       'explanation_key':r.get('explanation_key',r['id']),
                       'evidence':deepcopy(r.get('evidence',[]))})
        return result
    outputs = {target:evaluate(target) for target in package['outputs']}
    trace = {'case_id':case['id'],'return_revision':case['return_revision'],'package_sha256':package['sha256'],
             'input_sha256':digest({'inputs':case['inputs'],'confirmations':case['confirmations'],'return_revision':case['return_revision']}),
             'nodes':traces,'outputs':outputs,'privacy':'synthetic_only_sensitive_in_production'}
    trace['sha256'] = seal(trace)
    return outputs, trace


def verification_report(package, fixtures, runner_sha256, program, request, schemas):
    compiled = compile_package(program, request, schemas, program['catalog'], program['registry'])
    require(package == compiled, 'Structural verification requires the exact compiled plan')
    results = []
    require(len({c['id'] for c in fixtures}) == len(fixtures), 'Duplicate report fixture')
    for case in sorted(fixtures,key=lambda c:c['id']):
        require(seal(case) == case['sha256'], 'Fixture digest mismatch')
        actual, trace = run_case(package,case)
        results.append({'fixture_id':case['id'],'fixture_sha256':seal(case),
                        'expected':deepcopy(case['expected']),'actual':actual,
                        'status':'passed' if actual==case['expected'] else 'failed','trace':trace})
    report = {'contract_version':VERSION,'package_sha256':package['sha256'],'runner_version':VERSION,
              'runner_sha256':runner_sha256,'fixture_set_sha256':digest(sorted(fixtures,key=lambda c:c['id'])),
              'structural_validation':'passed','calculation_comparison':'passed' if results and all(r['status']=='passed' for r in results) else 'failed',
              'interpretation_review':'synthetic_not_tax_law','production_eligible':False,'results':results}
    report['sha256'] = seal(report)
    return report
