"""Source-backed research comparisons, without independent approval claims."""
import hashlib
import json
import re
import subprocess

from validate_model import check_schema, require
from validate_interactions import seal, digest, index
from worksheet_engine import compile_worksheet, evaluate_worksheet


def previous_worksheet(root,ref):
    require(re.fullmatch(r'HEAD\^?|[a-f0-9]{40}',ref) is not None,'Unsupported baseline Git reference')
    name='model/standard-deduction-package.json'
    listing=subprocess.run(['git','-C',str(root),'ls-tree','--name-only',ref,'--',name],capture_output=True,text=True)
    require(listing.returncode==0,'Cannot inspect worksheet baseline')
    if not listing.stdout.strip():return None
    result=subprocess.run(['git','-C',str(root),'show','--no-ext-diff',f'{ref}:{name}'],capture_output=True,text=True)
    require(result.returncode==0,'Cannot read worksheet baseline')
    return json.loads(result.stdout)


def worksheet_report(data,ledger,root):
    plan=compile_worksheet(data['program'],data['context'],ledger)
    require(plan==data['plan'],'Worksheet plan differs from compilation')
    results=[]
    for case in sorted(data['cases'],key=lambda c:c['id']):
        require(seal(case)==case['sha256'],'Worksheet fixture digest mismatch')
        actual=evaluate_worksheet(plan,case['inputs'])
        expected=case['expected']
        result=actual['result']
        match=all(result.get(key)==value for key,value in expected.items())
        steps={step['id']:step.get('result',{}).get('value') for step in actual['steps'] if step['status']=='value'}
        intermediate=all(steps.get(id)==value for id,value in case['expected_steps'].items())
        results.append({'case_id':case['id'],'fixture_sha256':case['sha256'],'expected':expected,'actual':actual,
                        'result_comparison':'passed' if match else 'failed','step_comparison':'passed' if intermediate else 'failed'})
    runner={name:hashlib.sha256((root/'tools/model'/name).read_bytes()).hexdigest() for name in ['worksheet_engine.py','exact_numbers.py','validate_worksheet.py']}
    report={'contract_version':'0.1.0','plan_sha256':plan['sha256'],'fixture_set_sha256':digest(data['cases']),
            'runner_sources':runner,'structural_validation':'passed',
            'calculation_comparison':'passed' if results and all(r['result_comparison']==r['step_comparison']=='passed' for r in results) else 'failed',
            'interpretation_review':'pending','reference_review':'pending','designated_reviewer':'Elliott Olson',
            'production_eligible':False,'results':results}
    report['sha256']=seal(report)
    return report


def validate_worksheet_report(report,data,schema,ledger,root):
    check_schema(report,{'$defs':schema['$defs'],'$ref':'#/$defs/report'})
    require(seal(report)==report['sha256'],'Worksheet report digest mismatch')
    require(report==worksheet_report(data,ledger,root),'Worksheet report does not match pinned plan, cases, or runner')


def validate_worksheet(data,schema,ledger,root,previous=None):
    check_schema(data,schema)
    cases=index(data['cases'],'worksheet case')
    inputs=index(data['program']['inputs'],'worksheet input')
    steps=index(data['program']['steps'],'worksheet step')
    for record in list(inputs.values())+list(steps.values()):
        if record['value_type']=='Enum':require(record.get('enum_domain') in data['program']['enum_domains'],'Unknown worksheet enum domain')
    for name,values in data['program']['enum_domains'].items():
        require(len(values)==len(set(values)),'Duplicate worksheet enum value')
    require(len({p['id'] for p in data['program']['claim_refs']})==len(data['program']['claim_refs']),'Duplicate worksheet claim pin')
    sources=index(ledger['sources'],'source');originals=index(ledger['fixtures'],'reference fixture')
    for case in cases.values():
        require(set(case['inputs'])<=set(inputs),'Unknown worksheet case input')
        require(set(case['expected_steps'])<=set(steps),'Unknown expected worksheet step')
        for fact in case['inputs'].values():
            require(fact['state'] not in {'missing','invalid','not_applicable'} or fact['value'] is None,'Unusable worksheet fact must omit value')
        for e in case['evidence']:
            require(e['source_id'] in sources and e['source_sha256']==sources[e['source_id']]['sha256'],'Case evidence pin mismatch')
            require(1<=e['pdf_page']<=sources[e['source_id']]['pdf_pages'],'Case evidence page mismatch')
        review=case['review_fixture']
        require(review['id'] in originals and originals[review['id']]['sha256']==review['sha256'],'Worksheet review fixture pin mismatch')
        subject=originals[review['id']]
        require(subject.get('worksheet_expectations')=={'case_id':case['id'],'expected_result':case['expected'],'expected_steps':case['expected_steps'],'original_fixture':case['original_fixture']},'Review fixture worksheet expectations mismatch')
        require(subject['evidence']==case['evidence'],'Review fixture evidence mismatch')
        # Verify the persistent review subject includes all adapter input assumptions.
        translated={id:{'state':f['state'],'data':{'type':inputs[id]['value_type'],'value':f['value']} if f['value'] is not None else None} for id,f in case['inputs'].items()}
        require(subject['inputs']==translated,'Review fixture input assumptions mismatch')
        expected=case['expected']
        if expected['status'] in {'value','ineligible'}:
            require(subject['expected']=={'status':'value','data':{'type':'Money','value':expected['value']}},'Review fixture expected amount mismatch')
        elif expected['status']=='blocked':require(subject['expected']==expected,'Review fixture blocking mismatch')
        else:require(subject['expected']=={'status':'undetermined','reason':expected['reason']},'Review fixture scope mismatch')
        pin=case['original_fixture']
        if pin:
            require(pin['id'] in originals and originals[pin['id']]['sha256']==pin['sha256'],'Original fixture pin mismatch')
            original=originals[pin['id']]
            require(original['tax_year']==data['context']['tax_year'],'Original fixture year mismatch')
            require(original['expected']['status']==case['expected']['status'],'Original fixture status mismatch')
            if original['expected']['status']=='value':
                require(original['expected']['data']['value']==case['expected']['value'],'Original reference result changed')
    report=worksheet_report(data,ledger,root)
    validate_worksheet_report(report,data,schema,ledger,root)
    require(report['calculation_comparison']=='passed','Worksheet reference comparison failed')
    if previous is not None:require(data==previous,'Archived worksheet package changed; add a new version')
    return {'cases':len(cases),'reused_references':sum(c['original_fixture'] is not None for c in cases.values()),
            'intermediate_cases':sum(bool(c['expected_steps']) for c in cases.values()),'calculation_comparison':'passed',
            'interpretation_review':'pending','production_eligible':False}


def main():
    from pathlib import Path
    import argparse
    from validate_model import ROOT
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    data=json.loads((ROOT/'model/standard-deduction-package.json').read_text())
    schema=json.loads((ROOT/'schemas/worksheet-package.schema.json').read_text())
    ledger=json.loads((ROOT/'model/claim-ledger.json').read_text())
    # Run all source/claim/compiler checks before emitting a research report.
    require(subprocess.run([__import__('sys').executable,str(ROOT/'tools/model/validate_model.py')],capture_output=True,text=True).returncode==0,'Model/source validation failed')
    validate_worksheet(data,schema,ledger,ROOT)
    report=worksheet_report(data,ledger,ROOT)
    with Path(args.output).open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
    print('Research worksheet report written; interpretation review is pending.')


if __name__=='__main__':main()
