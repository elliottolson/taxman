"""Offline, bounded ordinary-income research estimate; never submits a return."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys

from validate_model import ROOT, ModelError, check_schema, require
from validate_interactions import digest, seal
from exact_numbers import parse, round_line_total
from worksheet_engine import compile_worksheet, evaluate_worksheet

PACKAGE = 'model/ordinary-return-package-v1.json'


def load_return_package(root=ROOT):
    """Verify all pinned artifacts and archived source bytes before calculation."""
    read = lambda name: json.loads((root / name).read_text())
    package = read(PACKAGE)
    check_schema(package, read('schemas/ordinary-return-package.schema.json'))
    require(seal(package) == package['sha256'], 'Return package digest mismatch')
    require(package['contract_version'] == '0.1.0' and package['tax_year'] == 2025
            and package['status'] == 'draft_research' and package['production_enabled'] is False,
            'Unsupported return package')
    require(package['worksheet']['path'] == 'standard-deduction-package-v2.json'
            and package['tax_table']['path'] == 'ordinary-tax-table-2025-v1.json', 'Unsupported pinned artifact path')
    worksheet = read('model/' + package['worksheet']['path'])
    table = read('model/' + package['tax_table']['path'])
    check_schema(table, read('schemas/ordinary-tax-table.schema.json'))
    require(digest(worksheet) == package['worksheet']['sha256']
            and digest(table) == package['tax_table']['sha256'] and seal(table) == table['sha256'],
            'Return dependency digest mismatch')
    require(package['input_schema']['path'] == 'ordinary-return-input.schema.json'
            and digest(read('schemas/' + package['input_schema']['path'])) == package['input_schema']['sha256'],
            'Input schema pin mismatch')
    require(set(package['income_ceiling']) == set(package['supported_statuses'])
            and set(package['eitc_screen']) == set(package['supported_statuses'])
            and all(type(n) is int and 0 < n < 100000 for n in package['income_ceiling'].values())
            and all(type(n) is int and 0 < n < 100000 for n in package['eitc_screen'].values())
            and type(package['payroll_ceiling']) is int and 0 < package['payroll_ceiling'] <= 100000,
            'Invalid screening parameter')
    ledger = read('model/claim-ledger.json')
    sources = {s['id']: s for s in ledger['sources']}
    require(table['source'] == sources[table['source']['id']], 'Tax table source pin mismatch')
    require(compile_worksheet(worksheet['program'], worksheet['context'], ledger) == worksheet['plan'],
            'Deduction plan does not match compilation')
    evidence = package['ceiling_evidence'] + package['eitc_evidence'] + package['assessment_evidence']
    evidence += [e for spec in package['documents'].values() for e in spec['evidence']]
    evidence += [e for step in package['flow'] for e in step['evidence']]
    selected = {table['source']['id']} | {s['id'] for s in worksheet['plan']['sources']}
    for e in evidence:
        require(e['source_id'] in sources and e['source_sha256'] == sources[e['source_id']]['sha256']
                and 1 <= e['pdf_page'] <= sources[e['source_id']]['pdf_pages'], 'Return evidence pin mismatch')
        selected.add(e['source_id'])
    for id in selected:
        source = sources[id]
        require(seal(source) == source['sha256'] and source['tax_years'] == [2025], 'Invalid source metadata')
        path = (root / source['path']).resolve()
        require(path.is_relative_to((root / 'evidence').resolve()), 'Source path outside evidence directory')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == source['content_sha256'], 'Source bytes changed')
    require(table['tax_year'] == package['tax_year'] and table['production_enabled'] is False
            and table['columns'] == ['single', 'married_joint', 'married_separate', 'head_of_household'],
            'Invalid tax table metadata')
    edge = 0
    for row in table['rows']:
        require(type(row['lower']) is int and type(row['upper_exclusive']) is int
                and row['lower'] == edge and row['upper_exclusive'] > edge
                and len(row['tax']) == len(table['columns'])
                and all(type(n) is int and n >= 0 for n in row['tax'])
                and type(row['pdf_page']) is int and 2 <= row['pdf_page'] <= 13, 'Invalid tax table partition')
        edge = row['upper_exclusive']
    require(edge == 100000 and len(table['rows']) == 2062, 'Incomplete tax table')
    seen = set()
    for step in package['flow']:
        require(step['id'] not in seen and step['evidence'], 'Duplicate or unsourced return line')
        op = step['operation']
        require(op in {'sum_boxes', 'sum_lines', 'copy', 'standard_deduction', 'positive_difference', 'tax_table'},
                'Unknown return operation')
        refs = step.get('lines', []) + ([step['line']] if 'line' in step else [])
        if op == 'positive_difference': refs += [step['left'], step['right']]
        require(set(refs) <= seen, 'Return line forward reference or cycle')
        for kind, box in step.get('boxes', []):
            require(kind in package['documents'] and box in package['documents'][kind]['money_boxes'], 'Unknown document box')
        seen.add(step['id'])
    require({'1a','2b','3b','9','11a','12e','15','16','24','25a','25b','25d','33','34','35a','37'} <= seen,
            'Missing required return line')
    return package, table, worksheet, {id: sources[id] for id in sorted(selected)}


def table_tax(table, income, filing_status):
    require(type(income) is int and 0 <= income < 100000 and filing_status in table['columns'],
            'Tax table input outside domain')
    row = next(row for row in table['rows'] if row['lower'] <= income < row['upper_exclusive'])
    return row['tax'][table['columns'].index(filing_status)], row


def calculate_return(request, root=ROOT, artifacts=None):
    package, table, worksheet, sources = artifacts or load_return_package(root)
    schema = json.loads((root / 'schemas/ordinary-return-input.schema.json').read_text())
    try:
        check_schema(request, schema)
    except ModelError:
        raise ModelError('Invalid normalized return input') from None
    blockers = []
    def block(code, path, reason, evidence=None):
        blockers.append({'code': code, 'path': path, 'reason': reason, 'evidence': evidence or []})
    def confirmed(fact, path):
        if fact is None or fact['state'] != 'confirmed':
            if fact is not None and fact['state'] in {'missing','invalid','not_applicable'}:
                require(fact['value'] is None, 'Unusable fact must contain null')
            block('unresolved_fact', path, 'A confirmed value is required; missing and estimated values are not zero.')
            return None
        require(fact['value'] is not None, 'Confirmed fact cannot contain null')
        return fact['value']
    if request['tax_year'] != package['tax_year']:
        block('unsupported_year', 'tax_year', 'This package supports tax year 2025 only.')
    if confirmed(request.get('deduction_method'), 'deduction_method') not in (None, 'standard'):
        block('unsupported_deduction_method', 'deduction_method', 'Itemized deduction calculations are not implemented.')
    for key, explanation in package['required_assessments'].items():
        value = confirmed(request['assessments'].get(key), 'assessments.' + key)
        if value is False: block('unsupported_situation', 'assessments.' + key, explanation, package['assessment_evidence'])
    facts = deepcopy(request['deduction_facts'])
    for item in worksheet['program']['inputs']:
        if item['id'] != 'earned_income': confirmed(facts.get(item['id']), 'deduction_facts.' + item['id'])
    status_fact = facts.get('filing_status', {})
    status = status_fact.get('value') if status_fact.get('state') == 'confirmed' else None
    if status is not None and status not in package['supported_statuses']:
        block('unsupported_filing_status', 'deduction_facts.filing_status', 'Head-of-household and surviving-spouse eligibility and dependent rules need more support.')
    for key in ('self_claimable','spouse_claimable','self_age_qualified','spouse_age_qualified'):
        if facts.get(key, {}).get('state') == 'confirmed' and facts[key]['value'] is True:
            block('unsupported_filer', 'deduction_facts.' + key, 'Dependent or senior filer interactions need more support.')
    amounts, identities = {}, set()
    for kind, spec in package['documents'].items():
        if kind not in request['documents']:
            block('unresolved_documents', 'documents.' + kind, 'Provide a complete document list, including an explicit empty list when none exist.')
            continue
        amounts[kind] = []
        for doc in request['documents'][kind]:
            require(doc['id'] not in identities, 'Duplicate document identity')
            identities.add(doc['id'])
            prefix = 'documents.' + kind + '.' + doc['id']
            for key in spec['clear_assessments']:
                value = confirmed(doc['assessments'].get(key), prefix + '.assessments.' + key)
                if value is False: block('unsupported_document', prefix, 'Special or unhandled document fields need more support.', spec['evidence'])
            boxes = {}
            for box in spec['money_boxes']:
                value = confirmed(doc['boxes'].get(box), prefix + '.boxes.' + box)
                if value is not None:
                    boxes[box] = parse('Money', value)
                    if box in spec['zero_boxes'] and boxes[box].amount != 0:
                        block('preferential_income', prefix + '.boxes.' + box, 'Qualified dividends and capital-gain distributions need preferential-rate calculations.', spec['evidence'])
            if kind == 'div' and 'box1b' in boxes and 'box1a' in boxes:
                require(boxes['box1b'].amount <= boxes['box1a'].amount, 'Qualified dividends exceed ordinary dividends')
            amounts[kind].append(boxes)
    output = {'package_id': package['id'], 'package_sha256': package['sha256'], 'input_sha256': digest(request),
              'tax_year': request['tax_year'], 'production_enabled': False, 'interpretation_review': 'pending',
              'scope': package['scope'], 'excluded': ['penalties', 'interest', 'refund offsets', 'state taxes', 'return preparation and filing'],
              'sources': list(sources.values()), 'blockers': blockers, 'lines': {}, 'steps': [],
              'line_units': 'USD_whole_dollars',
              'runner_sha256': {name: hashlib.sha256((root / 'tools/model' / name).read_bytes()).hexdigest()
                                for name in ('calculate_return.py','worksheet_engine.py','exact_numbers.py')}}
    def finish():
        output['status'] = 'blocked' if blockers else 'estimate'
        if blockers: output['lines'] = {}; output['steps'] = []
        output['sha256'] = seal(output)
        return output
    if blockers: return finish()
    def raw_box_total(kind, box): return sum((doc[box].amount for doc in amounts[kind]), start=0)
    for box in ('box3','box5'):
        if raw_box_total('w2', box) > package['payroll_ceiling']:
            block('unsupported_payroll_range', 'documents.w2.' + box, 'Payroll wages exceed the conservative limit for screening additional payroll taxes and withholding adjustments.')
    for step in package['flow']:
        op = step['operation']; lines = output['lines']; detail = {}
        if op == 'sum_boxes':
            values = [doc[box] for kind, box in step['boxes'] for doc in amounts[kind]]
            value = int(round_line_total(values or [parse('Money','0.00')]))
            detail['rounding'] = 'sum exact cents for this return line, then whole-dollar half-up'
            detail['document_boxes'] = step['boxes']
            detail['document_ids'] = [doc['id'] for kind, _ in step['boxes'] for doc in request['documents'][kind]]
        elif op == 'sum_lines':
            value = sum(lines[id] for id in step['lines']); detail['input_lines'] = step['lines']
        elif op == 'copy':
            value = lines[step['line']]; detail['input_lines'] = [step['line']]
        elif op == 'positive_difference':
            value = max(0, lines[step['left']] - lines[step['right']]); detail['input_lines'] = [step['left'], step['right']]
        elif op == 'standard_deduction':
            facts['earned_income'] = {'state':'confirmed','value':str(lines['1a']) + '.00'}
            deduction = evaluate_worksheet(worksheet['plan'], facts)
            detail['worksheet'] = deduction
            result = deduction['result']
            if result['status'] != 'value':
                block('deduction_' + result['status'], 'deduction_facts', result['reason'], result.get('evidence'))
                return finish()
            value = int(parse('Money', result['value']).amount)
        else:
            value, row = table_tax(table, lines[step['line']], status)
            detail['tax_table_row'] = deepcopy(row)
            detail['table_sha256'] = table['sha256']
            detail['evidence'] = [{'source_id': table['source']['id'], 'source_sha256': table['source']['sha256'],
                                   'pdf_page': row['pdf_page'], 'locator': '2025 Tax Table: inclusive lower, exclusive upper; '+status}]
        lines[step['id']] = value
        output['steps'].append({'line': step['id'], 'operation': op, 'value': value, 'evidence': step['evidence'], **detail})
        if step['id'] == '11a':
            raw_income = raw_box_total('w2','box1') + raw_box_total('int','box1') + raw_box_total('int','box3') + raw_box_total('div','box1a')
            if max(raw_income, value) > package['income_ceiling'][status]:
                block('unsupported_income_range', 'income', 'Income exceeds this package’s conservative AMT and additional-tax screening ceiling.', package['ceiling_evidence'])
            if value < package['eitc_screen'][status] and 0 < lines['1a'] < package['eitc_screen'][status]:
                block('possible_eitc', 'income', 'Low income may qualify for earned income credit; credit calculation and eligibility screening are not implemented.', package['eitc_evidence'])
            if blockers: return finish()
    return finish()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='Normalized input JSON; use synthetic data during development')
    parser.add_argument('--output', type=Path, required=True, help='New private report file; existing files are never overwritten')
    args = parser.parse_args()
    try:
        def unique_pairs(pairs):
            result = {}
            for key,value in pairs:
                require(key not in result, 'Duplicate JSON object key')
                result[key] = value
            return result
        request = json.loads(args.input.read_text(), object_pairs_hook=unique_pairs)
        output = calculate_return(request)
        # Explicit exclusive creation and owner-only access; amounts never go to logs.
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as file: file.write(json.dumps(output, indent=2) + '\n')
        print('Return report written; status: ' + output['status'] + '. No financial values logged.')
        return 2 if output['status'] == 'blocked' else 0
    except (ModelError, OSError, ValueError, KeyError, StopIteration):
        print('Cannot calculate return: input, pinned artifacts, or output path failed validation. No financial values logged.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
