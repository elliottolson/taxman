"""Validate portable modeling artifacts; this is not a tax evaluator."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import argparse
from copy import deepcopy
import re
import subprocess

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]


class ModelError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ModelError(message)


def check_schema(instance, schema):
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(instance))
    if errors:
        first = errors[0]
        raise ModelError(f"Schema error at {list(first.absolute_path)}: {first.message}")


def validate(model, catalog, schemas, source_registry):
    check_schema(model, schemas['model'])
    check_schema(catalog, schemas['catalog'])
    source_ids = [s['id'] for s in source_registry['sources']]
    require(len(source_ids) == len(set(source_ids)), 'Duplicate source ID')
    source_status = {s['id']: s['status'] for s in source_registry['sources']}
    concepts = [c['id'] for f in catalog['families'] for c in f['concepts']]
    require(len(concepts) == len(set(concepts)), 'Duplicate concept ID')
    family_ids = [f['id'] for f in catalog['families']]
    require(len(family_ids) == len(set(family_ids)), 'Duplicate family ID')
    enums = {}
    for enum in model['enum_domains']:
        require(enum['id'] not in enums, 'Duplicate enum domain')
        enums[enum['id']] = set(enum['values'])
    sections = {
        'fact': 'facts', 'parameter': 'parameters', 'rule': 'rules',
        'decision': 'decisions', 'election': 'elections', 'module': 'modules',
        'constraint': 'constraints', 'form_mapping': 'form_mappings',
        'capability': 'capabilities',
    }
    symbols = {}
    for kind, section in sections.items():
        for record in model[section]:
            key = f"{kind}:{record['id']}"
            require(key not in symbols, f'Duplicate ID: {key}')
            symbols[key] = record
            for evidence in record.get('evidence', []):
                require(evidence['source_id'] in source_ids, f'Unknown source: {evidence["source_id"]}')
                if record.get('status') == 'reviewed':
                    require(evidence['interpretation_status'] == 'reviewed' and source_status[evidence['source_id']] in {'reviewed', 'approved'}, 'Reviewed record needs reviewed interpretation and source')
    graph = {key: set() for key in symbols}

    def lookup(key):
        require(key in symbols, f'Unknown reference: {key}')
        return symbols[key]

    def signature(record):
        typ = record['value_type']
        domain = record.get('enum_domain')
        if typ == 'Enum':
            require(domain in enums, f'Unknown enum domain: {domain}')
        return typ, record['shape'], domain if typ == 'Enum' else None

    def expression(expr):
        kind = expr['kind']
        if kind == 'ref':
            record = lookup(expr['target'])
            require(not (expr['target'].startswith('parameter:') and record['axes']), 'Indexed parameter requires lookup')
            return signature(record), {expr['target']}
        if kind == 'literal':
            typ = expr['value_type']
            domain = expr.get('enum_domain')
            if typ == 'Enum':
                require(domain in enums, f'Unknown literal enum domain: {domain}')
                require(expr['value'] in enums[domain], f'Invalid enum literal: {expr["value"]}')
            return (typ, 'scalar', domain if typ == 'Enum' else None), set()
        if kind == 'lookup':
            record = lookup(expr['parameter'])
            require(expr['parameter'].startswith('parameter:'), 'Lookup target must be parameter')
            keys = {key['name']: key for key in expr['keys']}
            require(len(keys) == len(expr['keys']), 'Duplicate lookup key')
            axes = {axis['name']: axis for axis in record['axes']}
            require(set(keys) == set(axes), 'Lookup keys do not match parameter axes')
            deps = {expr['parameter']}
            for name, key in keys.items():
                typ, refs = expression(key['value'])
                axis = axes[name]
                expected = (axis['value_type'], 'scalar', axis.get('enum_domain') if axis['value_type'] == 'Enum' else None)
                require(typ == expected, 'Lookup key type mismatch')
                deps |= refs
            return signature(record), deps
        args = [expression(arg) for arg in expr['arguments']]
        types = [typ for typ, _ in args]
        deps = set().union(*(refs for _, refs in args))
        operator = expr['operator']
        boolean = ('Boolean', 'scalar', None)
        numeric = {'Money', 'Rate', 'Decimal', 'Integer'}
        if operator == 'sum':
            require(len(types) == 1 and types[0][1] == 'collection' and types[0][0] in numeric, 'Sum requires one numeric collection')
            require('aggregation_scope' in expr, 'Sum requires explicit aggregation scope')
            return (types[0][0], 'scalar', types[0][2]), deps
        require(all(typ[1] == 'scalar' for typ in types), f'{operator} requires scalar arguments')
        if operator in {'and', 'or', 'not'}:
            require(all(typ == boolean for typ in types), 'Boolean operator type mismatch')
            require(len(types) == 1 if operator == 'not' else len(types) >= 2, 'Boolean operator arity mismatch')
            return boolean, deps
        if operator in {'equal', 'less_than', 'less_equal'}:
            require(len(types) == 2 and types[0] == types[1], 'Comparison type mismatch')
            if operator != 'equal':
                require(types[0][0] in numeric | {'Date'}, 'Ordered comparison requires ordered values')
            return boolean, deps
        if operator in {'add', 'subtract', 'min', 'max'}:
            require(len(types) >= 2 and len(set(types)) == 1 and types[0][0] in numeric, 'Arithmetic type mismatch')
            require(operator != 'subtract' or len(types) == 2, 'Subtract requires two arguments')
            return types[0], deps
        require(len(types) == 2 and all(t[0] in numeric for t in types), 'Multiply/divide requires two numeric values')
        left, right = types[0][0], types[1][0]
        if operator == 'multiply':
            require(not (left == right == 'Money'), 'Money times Money has unsupported dimensions')
            result = 'Money' if 'Money' in (left, right) else 'Decimal'
        else:
            require(not (right == 'Money' and left != 'Money'), 'Unsupported division dimensions')
            result = 'Rate' if left == right == 'Money' else ('Money' if left == 'Money' else 'Decimal')
        return (result, 'scalar', None), deps

    def expression_for(key, expr, expected=None):
        typ, deps = expression(expr)
        if expected is not None:
            require(typ == expected, f'Output type mismatch: {key}: {typ} != {expected}')
        graph[key] |= deps
        return deps

    boolean = ('Boolean', 'scalar', None)
    for key, record in symbols.items():
        kind = key.split(':')[0]
        if 'value_type' in record:
            signature(record)
        if kind == 'rule':
            require(record['concept_id'] in concepts, f'Unknown concept: {record["concept_id"]}')
            deps = expression_for(key, record['applicability'], boolean)
            execution = record['execution']
            if execution['kind'] == 'expression':
                deps |= expression_for(key, execution['expression'], signature(record))
                if execution['expression'].get('operator') == 'sum':
                    require(execution['expression']['aggregation_scope'] == record['scope'], 'Aggregation/output scope mismatch')
            elif execution['kind'] == 'decision':
                target = 'decision:' + execution['decision_id']
                require(signature(lookup(target)) == signature(record), 'Decision result type mismatch')
                graph[key].add(target); deps.add(target)
            else:
                module = lookup('module:' + execution['module_id'])
                require(module['version'] == execution['module_version'], 'Module version mismatch')
                require((module['result_type'], module['result_shape'], None) == signature(record), 'Module result type mismatch')
                expected = {i['name']: i for i in module['inputs']}
                supplied = {b['input']: b for b in execution['bindings']}
                require(len(supplied) == len(execution['bindings']) and set(supplied) == set(expected), 'Module bindings mismatch')
                for name, binding in supplied.items():
                    item = expected[name]
                    deps |= expression_for(key, binding['value'], (item['value_type'], item['shape'], None))
            require(set(record['declared_dependencies']) == deps and len(record['declared_dependencies']) == len(deps), f'Declared dependencies mismatch: {key}')
        elif kind == 'decision':
            ids = [row['id'] for row in record['rows']]
            require(len(ids) == len(set(ids)), 'Duplicate decision row ID')
            conditions = [json.dumps(row['condition'], sort_keys=True) for row in record['rows']]
            if record['hit_policy'] == 'unique':
                require(len(conditions) == len(set(conditions)), 'Identical conditions in unique decision')
            for row in record['rows']:
                expression_for(key, row['condition'], boolean)
                expression_for(key, row['result'], signature(record))
        elif kind == 'election':
            selected = lookup(record['selection_fact'])
            require(signature(selected) == signature(record), 'Election selection fact type mismatch')
            graph[key].add(record['selection_fact'])
            choices = [choice['id'] for choice in record['choices']]
            require(len(choices) == len(set(choices)), 'Duplicate election choice')
            require(set(choices) == enums[record['enum_domain']], 'Election choices do not match enum domain')
            for choice in record['choices']:
                expression_for(key, choice['eligibility'], boolean)
                for effect in choice['effects']:
                    lookup(effect)  # Domain impact, not an execution prerequisite.
        elif kind == 'constraint':
            expression_for(key, record['predicate'], boolean)
        elif kind == 'form_mapping':
            require(record['tax_year'] in model['candidate_tax_years'], 'Form mapping year outside model')
            expression_for(key, record['value'])
        elif kind == 'capability':
            for target in record['rule_refs']:
                lookup(target)
    for relation in model['relationships']:
        lookup(relation['from']); lookup(relation['to'])
        require(relation['from'] != relation['to'], 'Self relationship is invalid')
        # Relationship cycles are allowed; no execution edges are inferred here.
    active, done = set(), set()

    def visit(key):
        require(key not in active, f'Execution dependency cycle: {key}')
        if key in done:
            return
        active.add(key)
        for dep in sorted(graph[key]):
            visit(dep)
        active.remove(key); done.add(key)

    for key in sorted(graph):
        visit(key)
    from validate_selection import analyze_core_decisions
    decision_analysis = analyze_core_decisions(model)
    return {'decision_analysis': decision_analysis, 'families': len(catalog['families']), 'concepts': len(concepts), 'rules': len(model['rules']), 'execution_edges': sum(map(len, graph.values()))}


def load(root=ROOT):
    def read(name):
        return json.loads((root / name).read_text())
    return read('model/tax-model.json'), read('model/domain-catalog.json'), {'model': read('schemas/tax-model.schema.json'), 'catalog': read('schemas/domain-catalog.schema.json'), 'interactions': read('schemas/interaction-model.schema.json')}, read('examples/source-registry.json')


def load_interactions(root=ROOT):
    model = json.loads((root / 'model/tax-model.json').read_text())
    require(model['interaction_model'] == 'interaction-model.json', 'Unexpected interaction model path')
    return json.loads((root / 'model/interaction-model.json').read_text())


def check_interactions(model, catalog, schemas, sources, data, previous=None):
    from validate_interactions import validate_interactions

    def snapshot(definition):
        candidate = deepcopy(model)
        found = False
        for i, rule in enumerate(candidate['rules']):
            if rule['id'] == definition.get('id'):
                candidate['rules'][i] = definition
                found = True
                break
        require(found, 'Snapshot refers to unknown semantic rule')
        validate(candidate, catalog, schemas, sources)

    return validate_interactions(data, schemas['interactions'], model, catalog, snapshot, previous)


def previous_interactions(ref, root=ROOT):
    require(re.fullmatch(r'HEAD\^?|[a-f0-9]{40}', ref) is not None, 'Unsupported baseline Git reference')
    def read_blob(name):
        result = subprocess.run(['git', '-C', str(root), 'show', '--no-ext-diff', f'{ref}:{name}'], capture_output=True, text=True)
        require(result.returncode == 0, 'Cannot read model baseline from Git')
        return json.loads(result.stdout)
    model = read_blob('model/tax-model.json')
    if 'interaction_model' not in model:
        return None  # The prior 0.2 model predates these contracts.
    require(model['interaction_model'] == 'interaction-model.json', 'Unexpected baseline interaction path')
    return read_blob('model/interaction-model.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-ref', help='Validate archive preservation against HEAD, HEAD^, or a full commit hash')
    args = parser.parse_args()
    try:
        model, catalog, schemas, sources = load()
        require((ROOT / 'model' / model['source_registry']).resolve() == (ROOT / 'examples/source-registry.json').resolve(), 'Unexpected source registry path')
        summary = validate(model, catalog, schemas, sources)
        previous = previous_interactions(args.baseline_ref) if args.baseline_ref else None
        summary['interactions'] = check_interactions(model, catalog, schemas, sources, load_interactions(), previous)
        from validate_selection import validate_selection
        selection = json.loads((ROOT / 'model/selection-model.json').read_text())
        selection_schema = json.loads((ROOT / 'schemas/selection-model.schema.json').read_text())
        summary['selection'] = validate_selection(selection, selection_schema, model)
        from validate_claims import read_ledger, previous_ledger, validate_claims
        ledger_schema = json.loads((ROOT / 'schemas/claim-ledger.schema.json').read_text())
        prior_ledger = previous_ledger(ROOT, args.baseline_ref) if args.baseline_ref else None
        summary['claims'] = validate_claims(read_ledger(ROOT), ledger_schema, model, sources, ROOT, prior_ledger)
        from validate_execution import previous_execution, validate_execution
        execution = json.loads((ROOT / 'model/execution-contract.json').read_text())
        execution_schema = json.loads((ROOT / 'schemas/execution-contract.schema.json').read_text())
        prior_execution = previous_execution(ROOT, args.baseline_ref) if args.baseline_ref else None
        summary['execution'] = validate_execution(execution, execution_schema, schemas, ROOT, prior_execution)
        from validate_worksheet import previous_worksheet, validate_worksheet
        worksheet = json.loads((ROOT / 'model/standard-deduction-package.json').read_text())
        worksheet_schema = json.loads((ROOT / 'schemas/worksheet-package.schema.json').read_text())
        prior_worksheet = previous_worksheet(ROOT, args.baseline_ref) if args.baseline_ref else None
        summary['worksheet'] = validate_worksheet(worksheet, worksheet_schema, read_ledger(ROOT), ROOT, prior_worksheet)
        print('Model contracts validated: ' + json.dumps(summary, sort_keys=True))
        print('Tax interpretations remain drafts; worksheet comparisons passed, independent review and production eligibility remain pending.')
    except (ModelError, OSError, ValueError, KeyError) as error:
        print(f'Validation failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
