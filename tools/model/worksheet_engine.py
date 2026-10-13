"""Typed, data-authored research worksheets; production approval stays separate."""
from copy import deepcopy
from itertools import product

from validate_model import ModelError, require
from validate_interactions import digest, seal, index, instant
from exact_numbers import Exact, TYPES, parse, arithmetic, quantize, render

VERSION = '0.1.0'


class Unresolved(ValueError):
    pass


def signature(record):
    return record['value_type'], record.get('enum_domain') if record['value_type'] == 'Enum' else None


def annual_table(table, year):
    require(type(year) is int, 'Annual year must be Integer')
    axes = table['axes']
    require(all(axis['values'] and len(set(axis['values']))==len(axis['values']) for axis in axes.values()), 'Annual axis domain must be nonempty and unique')
    require('tax_year' in axes, 'Annual table requires tax_year axis')
    expected = set(product(*(axes[k]['values'] for k in sorted(axes))))
    keys = []
    for row in table['rows']:
        require(set(row['keys']) == set(axes), 'Annual table key set mismatch')
        key = tuple(row['keys'][k] for k in sorted(axes))
        require(key in expected and all(type(row['keys'][k]) is type(axes[k]['values'][0]) for k in axes), 'Annual table key outside domain')
        parse(table['value_type'], row['value'])
        keys.append(key)
    require(len(keys) == len(set(keys)), 'Overlapping annual table rows')
    require(set(keys) == expected, 'Uncovered annual table keys')
    require(year in axes['tax_year']['values'], 'Missing annual table year')
    result = deepcopy(table)
    result['rows'] = [deepcopy(row) for row in table['rows'] if row['keys']['tax_year'] == year]
    result['axes']['tax_year']['values'] = [year]
    return result


def compile_worksheet(program, context, ledger):
    require(program['production_enabled'] is False and program['status'] == 'draft_research', 'Research mode required')
    require(context['tax_year'] in program['tax_years'], 'Unsupported worksheet tax year')
    index(program['outcomes'], 'outcome')
    facts, steps, tables = index(program['inputs'], 'input'), index(program['steps'], 'step'), index(program['tables'], 'table')
    symbols = {'input:'+id: signature(r) for id,r in facts.items()}
    symbols.update({'step:'+id:signature(r) for id,r in steps.items()})
    symbols['context:tax_year'] = 'Integer', None
    for table in tables.values():
        for axis in table['axes'].values():
            if axis['value_type']=='Enum':
                require(axis.get('enum_domain') in program['enum_domains'] and set(axis['values'])==set(program['enum_domains'][axis['enum_domain']]), 'Annual enum axis must cover its declared domain')
            else:
                for value in axis['values']:parse('Integer',value)
        require(set(table['axes']['tax_year']['values'])<=set(program['tax_years']), 'Annual table year outside program')
    compiled_tables = {id:annual_table(table, context['tax_year']) for id,table in tables.items()}
    edges = {id:set() for id in steps}
    def infer(expr, deps):
        kind = expr['kind']
        if kind == 'ref':
            require(expr['target'] in symbols, 'Unknown worksheet reference')
            if expr['target'].startswith('step:'):
                deps.add(expr['target'][5:])
            return symbols[expr['target']]
        if kind == 'literal':
            typ = expr['value_type']
            if typ in TYPES:
                parse(typ, expr['value'])
            elif typ == 'Boolean':
                require(type(expr['value']) is bool, 'Invalid Boolean literal')
            else:
                require(expr.get('enum_domain') in program['enum_domains'] and expr['value'] in program['enum_domains'][expr['enum_domain']], 'Invalid enum literal')
            return signature(expr)
        if kind == 'lookup':
            require(expr['table'] in tables, 'Unknown worksheet table')
            table = tables[expr['table']]
            require(set(expr['keys']) == set(table['axes'])-{'tax_year'}, 'Lookup axes mismatch')
            for key, value in expr['keys'].items():
                require(infer(value, deps) == signature(table['axes'][key]), 'Lookup key type mismatch')
            return table['value_type'], None
        if kind == 'choose':
            require(infer(expr['condition'], deps) == ('Boolean',None), 'Choice condition must be Boolean')
            left, right = infer(expr['then'],deps), infer(expr['else'],deps)
            require(left == right, 'Choice branch type mismatch')
            return left
        types = [infer(arg,deps) for arg in expr['arguments']]
        op = expr['operator']
        if op in {'and','or','not'}:
            require(all(t==('Boolean',None) for t in types) and (len(types)==1 if op=='not' else len(types)>=2), 'Boolean operator mismatch')
            return 'Boolean', None
        if op == 'boolean_to_integer':
            require(types==[('Boolean',None)], 'Box count needs Boolean')
            return 'Integer', None
        if op in {'equal','less_than','less_equal'}:
            require(len(types)==2 and types[0]==types[1], 'Comparison type mismatch')
            require(op=='equal' or types[0][0] in TYPES, 'Ordered comparison needs numeric values')
            return 'Boolean', None
        if op == 'round':
            require(len(types)==1 and types[0][0] in TYPES, 'Rounding needs numeric argument')
            quantize(parse(types[0][0],1 if types[0][0]=='Integer' else '1.00'),expr['scale'],expr['mode'])
            return types[0]
        require(all(t[0] in TYPES for t in types), 'Arithmetic needs numeric values')
        example = [parse(t[0],1 if t[0]=='Integer' else '1.00') for t in types]
        return arithmetic(op,example).value_type, None
    for id,step in steps.items():
        require(infer(step['expression'],edges[id])==signature(step), 'Worksheet step type mismatch: '+id)
    for branch in program['outcomes']:
        require(infer(branch['condition'],set())==('Boolean',None), 'Outcome condition type mismatch')
        if 'expression' in branch:
            require(infer(branch['expression'],set())==('Money',None), 'Outcome requires Money')
    active, done, ordered = set(), set(), []
    def visit(id):
        require(id not in active, 'Worksheet dependency cycle')
        if id in done:
            return
        active.add(id)
        for dep in sorted(edges[id]):visit(dep)
        active.remove(id);done.add(id);ordered.append(id)
    for id in sorted(steps):visit(id)
    sources = index(ledger['sources'],'source')
    claims = index(ledger['claims'],'claim')
    from validate_claims import replay_reviews
    states = replay_reviews(ledger,context['known_at'])
    selected_claims = []
    for pin in program['claim_refs']:
        require(pin['id'] in claims and claims[pin['id']]['sha256']==pin['sha256'], 'Worksheet claim pin mismatch')
        c = claims[pin['id']]
        require(c['applicability']['start'] <= context['tax_year'] < c['applicability']['end_exclusive'], 'Worksheet claim year mismatch')
        require(instant(c['recorded_at']) <= instant(context['known_at']), 'Worksheet claim not yet recorded')
        selected_claims.append({'id':c['id'],'sha256':c['sha256'],'review_state':states[('claim',c['id'])]})
    def evidence(items):
        for e in items:
            require(e['source_id'] in sources and e['source_sha256']==sources[e['source_id']]['sha256'], 'Worksheet evidence pin mismatch')
            source=sources[e['source_id']]
            require(context['tax_year'] in source['tax_years'] and 1 <= e['pdf_page'] <= source['pdf_pages'], 'Worksheet evidence year/page mismatch')
    all_evidence = []
    for record in program['steps']+program['tables']+program['outcomes']:
        require(record['evidence'], 'Worksheet source evidence required')
        evidence(record['evidence']);all_evidence.extend(record['evidence'])
    source_ids = sorted({e['source_id'] for e in all_evidence})
    result={'id':context['id'],'contract_version':VERSION,'production_enabled':False,'tax_year':context['tax_year'],
            'known_at':context['known_at'],'program_sha256':digest(program),'program':deepcopy(program),
            'tables':[compiled_tables[id] for id in sorted(compiled_tables)],'step_order':ordered,
            'step_dependencies':{id:sorted(edges[id]) for id in sorted(edges)},'claims':selected_claims,
            'sources':[deepcopy(sources[id]) for id in source_ids],'interpretation_review':'pending',
            'scope':'standard_deduction_candidate_only'}
    result['sha256']=seal(result)
    return result


def evaluate_worksheet(plan, inputs):
    require(seal(plan)==plan['sha256'] and plan['production_enabled'] is False, 'Invalid research worksheet plan')
    program=plan['program'];facts=index(program['inputs'],'input');steps=index(program['steps'],'step');tables=index(plan['tables'],'table')
    require(set(inputs)<=set(facts), 'Unknown worksheet input')
    cache, trace = {}, []
    def typed(typ,value,domain=None):
        if typ in TYPES:return parse(typ,value)
        if typ=='Boolean':
            require(type(value) is bool, 'Invalid Boolean input')
        else:
            require(type(value) is str and domain in program['enum_domains'] and value in program['enum_domains'][domain], 'Invalid enum input')
        return value
    for id, fact in inputs.items():
        require(fact['state'] in {'confirmed','missing','invalid','estimated','provisional','not_applicable'}, 'Unknown fact state')
        if fact['state']=='confirmed':
            record=facts[id]
            typed(record['value_type'],fact['value'],record.get('enum_domain'))
        elif fact['state'] in {'missing','invalid','not_applicable'}:
            require(fact['value'] is None,'Unusable input must omit value')

    def encode(v):
        if type(v) is Exact:
            result={'value_type':v.value_type,'numerator':v.amount.numerator,'denominator':v.amount.denominator}
            if v.value_type=='Money' and (v.amount*100).denominator==1:result['value']=render(v)
            elif v.value_type=='Integer':result['value']=int(v.amount)
            return result
        return {'value':v}
    def evaluate(expr):
        kind=expr['kind']
        if kind=='ref':
            target=expr['target']
            if target=='context:tax_year':return parse('Integer',plan['tax_year'])
            if target.startswith('input:'):
                id=target[6:];require(id in facts,'Unknown worksheet input reference')
                fact=inputs.get(id)
                if fact is None or fact['state']!='confirmed':raise Unresolved('unresolved_fact:'+id)
                r=facts[id];return typed(r['value_type'],fact['value'],r.get('enum_domain'))
            id=target[5:]
            if id not in cache:
                step=steps[id]
                try:
                    value=evaluate(step['expression']);cache[id]=value
                    trace.append({'id':id,'status':'value','result':encode(value),'evidence':deepcopy(step['evidence'])})
                except Unresolved as error:
                    trace.append({'id':id,'status':'blocked','reason':str(error),'evidence':deepcopy(step['evidence'])})
                    raise
            return cache[id]
        if kind=='literal':return typed(expr['value_type'],expr['value'],expr.get('enum_domain'))
        if kind=='choose':return evaluate(expr['then'] if evaluate(expr['condition']) else expr['else'])
        if kind=='lookup':
            table=tables[expr['table']];keys={'tax_year':plan['tax_year']}
            for key,e in expr['keys'].items():
                v=evaluate(e);keys[key]=int(v.amount) if type(v) is Exact and v.value_type=='Integer' else v
            matches=[r for r in table['rows'] if r['keys']==keys]
            require(len(matches)==1,'Lookup requires exactly one annual row')
            return parse(table['value_type'],matches[0]['value'])
        op=expr['operator']
        if op in {'and','or'}:
            unknown=None
            for arg in expr['arguments']:
                try:v=evaluate(arg)
                except Unresolved as error:unknown=error;continue
                if (op=='and' and not v) or (op=='or' and v):return v
            if unknown:raise unknown
            return op=='and'
        values=[evaluate(a) for a in expr['arguments']]
        if op=='not':return not values[0]
        if op=='boolean_to_integer':return parse('Integer',int(values[0]))
        if op in {'equal','less_than','less_equal'}:
            a,b=values
            if type(a) is Exact:a,b=a.amount,b.amount
            return a==b if op=='equal' else (a<b if op=='less_than' else a<=b)
        if op=='round':return quantize(values[0],expr['scale'],expr['mode'])
        return arithmetic(op,values)
    try:
        for branch in program['outcomes']:
            if evaluate(branch['condition']):
                result={'status':branch['status'],'reason':branch['reason']}
                if 'expression' in branch:result['value']=render(evaluate(branch['expression']))
                result['outcome_id']=branch['id']
                result['evidence']=deepcopy(branch['evidence'])
                break
        else:raise Unresolved('no_applicable_outcome')
    except Unresolved as error:
        result={'status':'blocked','reason':str(error)}
    output={'plan_sha256':plan['sha256'],'input_sha256':digest(inputs),'result':result,'steps':trace,
            'production_enabled':False,'interpretation_review':'pending'}
    output['sha256']=seal(output)
    return output
