"""Check compiled plans and reproduce synthetic verification/explanation artifacts."""
import hashlib
import json
import re
import subprocess

from validate_model import check_schema, require
from validate_interactions import seal, index, instant
from compile_package import compile_package, verification_report


def previous_execution(root, ref):
    require(re.fullmatch(r'HEAD\^?|[a-f0-9]{40}',ref) is not None,'Unsupported baseline Git reference')
    path='model/execution-contract.json'
    listing=subprocess.run(['git','-C',str(root),'ls-tree','--name-only',ref,'--',path],capture_output=True,text=True)
    require(listing.returncode==0,'Cannot inspect execution baseline')
    if not listing.stdout.strip():
        return None
    result=subprocess.run(['git','-C',str(root),'show','--no-ext-diff',f'{ref}:{path}'],capture_output=True,text=True)
    require(result.returncode==0,'Cannot read execution baseline')
    return json.loads(result.stdout)


def package_index(packages):
    result={p['package_id']:p for p in packages}
    require(len(result)==len(packages),'Duplicate compiled package ID')
    return result


def validate_trace(trace, package, case, schema):
    check_schema(trace, {'$defs':schema['$defs'], '$ref':'#/$defs/trace'})
    require(seal(trace)==trace['sha256'],'Trace digest mismatch')
    from compile_package import run_case
    _, expected=run_case(package,case)
    require(trace==expected,'Trace does not match pinned inputs and execution')


def validate_report(report, package, cases, schema, runner_sha256, program, request, schemas):
    check_schema(report, {'$defs':schema['$defs'], '$ref':'#/$defs/report'})
    require(seal(report)==report['sha256'],'Report digest mismatch')
    expected=verification_report(package,cases,runner_sha256,program,request,schemas)
    require(report==expected,'Verification report does not match pinned package, fixtures, or runner')
    for result in report['results']:
        case=next(c for c in cases if c['id']==result['fixture_id'])
        validate_trace(result['trace'],package,case,schema)


def validate_execution(data,schema,schemas,root,previous=None):
    check_schema(data,schema)
    programs=index(data['programs'],'program')
    requests=index(data['requests'],'request')
    cases=index(data['fixtures'],'fixture')
    packages=package_index(data['packages'])
    require(set(requests)==set(packages),'Requests and compiled packages must match')
    for program in programs.values():
        rule_ids={r['id'] for r in program['model']['rules']}
        for revision in program['rule_revisions']:
            require(revision['target']=='rule:'+revision['definition']['id'] and revision['definition']['id'] in rule_ids,'Invalid rule revision target')
            require(revision['tax_years']['start'] < revision['tax_years']['end_exclusive'],'Empty rule year interval')
            require(revision['superseded_at'] is None or instant(revision['recorded_at']) < instant(revision['superseded_at']),'Empty rule knowledge interval')
        require(len({(b['target'],b['tax_year']) for b in program['parameter_bindings']})==len(program['parameter_bindings']),'Conflicting annual parameter bindings')
        parameter_ids={'parameter:'+p['id'] for p in program['model']['parameters']}
        require(all(b['target'] in parameter_ids for b in program['parameter_bindings']),'Unknown parameter binding target')
    for case in cases.values():
        require(seal(case)==case['sha256'],'Fixture digest mismatch')
        require(len(set(case['package_ids']))==len(case['package_ids']) and set(case['package_ids'])<=set(packages),'Unknown or duplicate fixture package')
        for fact in case['inputs'].values():
            require(fact['state'] not in {'missing','invalid','not_applicable'} or fact['value'] is None,'Unusable input must omit value')
    runner_sha256=hashlib.sha256((root/'tools/model/compile_package.py').read_bytes()).hexdigest()
    summaries={}
    for id, request in requests.items():
        require(request['program_id'] in programs,'Unknown request program')
        program=programs[request['program_id']]
        compiled=compile_package(program,request,schemas,program['catalog'],program['registry'])
        require(compiled==packages[id],'Compiled package differs from deterministic plan')
        fixtures=[c for c in cases.values() if id in c['package_ids']]
        require(fixtures,'Package needs verification fixtures')
        require(all(set(c['expected'])==set(compiled['outputs']) for c in fixtures),'Fixture outputs do not match package')
        report=verification_report(compiled,fixtures,runner_sha256,program,request,schemas)
        validate_report(report,compiled,fixtures,schema,runner_sha256,program,request,schemas)
        require(report['calculation_comparison']=='passed','Synthetic calculation comparison failed')
        summaries[id]={'nodes':len(compiled['nodes']),'fixtures':len(fixtures),'package_sha256':compiled['sha256'],
                       'calculation_comparison':report['calculation_comparison'],'production_eligible':False}
    if previous:
        for section in ['programs','requests','fixtures']:
            current=index(data[section],section)
            for old in previous[section]:
                require(old['id'] in current and old==current[old['id']],'Archived execution record changed: '+old['id'])
        for old in previous['packages']:
            require(old['package_id'] in packages and old==packages[old['package_id']],'Archived compiled package changed')
    return summaries


def main():
    """Emit a reviewable synthetic report. Values/traces must stay out of production logs."""
    import argparse
    from pathlib import Path
    from validate_model import ROOT, load
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',required=True)
    parser.add_argument('--output',required=True,help='Write the sensitive report JSON to an explicit file')
    args=parser.parse_args()
    data=json.loads((ROOT/'model/execution-contract.json').read_text())
    schema=json.loads((ROOT/'schemas/execution-contract.schema.json').read_text())
    _,_,schemas,_=load()
    validate_execution(data,schema,schemas,ROOT)
    packages=package_index(data['packages'])
    require(args.package in packages,'Unknown compiled package')
    fixtures=[c for c in data['fixtures'] if args.package in c['package_ids']]
    runner_sha256=hashlib.sha256((ROOT/'tools/model/compile_package.py').read_bytes()).hexdigest()
    request=next(r for r in data['requests'] if r['id']==args.package)
    program=next(p for p in data['programs'] if p['id']==request['program_id'])
    report=verification_report(packages[args.package],fixtures,runner_sha256,program,request,schemas)
    output=Path(args.output)
    with output.open('x') as stream:
        json.dump(report,stream,indent=2)
        stream.write('\n')
    print('Synthetic verification report written; production remains disabled.')


if __name__=='__main__':
    main()
