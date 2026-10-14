"""Validate immutable return artifacts and separately established reference cases."""
import json
import subprocess

from validate_model import ROOT, require
from validate_interactions import seal
from calculate_return import load_return_package, calculate_return

ARCHIVES = ['model/ordinary-return-package-v1.json', 'model/ordinary-tax-table-2025-v1.json',
            'model/ordinary-return-reference-v1.json']


def validate_return(root=ROOT, baseline_ref=None):
    artifacts = load_return_package(root)
    package, table, _, _ = artifacts
    corpus = json.loads((root / ARCHIVES[2]).read_text())
    require(seal(corpus) == corpus['sha256'] and corpus['production_enabled'] is False
            and corpus['package_path'] == 'ordinary-return-package-v1.json'
            and corpus['package_sha256'] == package['sha256'], 'Return reference pin mismatch')
    identities = set()
    for case in corpus['cases']:
        require(case['id'] not in identities and seal(case) == case['sha256'], 'Reference duplicate or digest mismatch')
        identities.add(case['id'])
        oracle = case['oracle']
        require(oracle['independent_of_candidate_execution'] is True and oracle['derivation']
                and oracle['source_sha256'] == table['source']['sha256']
                and oracle['source_id'] == table['source']['id'] and 2 <= oracle['pdf_page'] <= 13,
                'Missing independent reference evidence')
        actual = calculate_return(case['input'],root,artifacts)
        expected = case['expected']
        require(actual['status'] == expected['status'] and actual['lines'] == expected['lines']
                and sorted({b['code'] for b in actual['blockers']}) == sorted(expected['blocker_codes']),
                'Return reference comparison failed: '+case['id'])
    if baseline_ref:
        import re
        require(re.fullmatch(r'HEAD\^?|[a-f0-9]{40}',baseline_ref), 'Unsupported baseline reference')
        for name in ARCHIVES:
            exists = subprocess.run(['git','-C',str(root),'ls-tree','--name-only',baseline_ref,'--',name],capture_output=True,text=True)
            require(exists.returncode == 0, 'Cannot inspect return baseline')
            if exists.stdout.strip():
                previous = subprocess.run(['git','-C',str(root),'show','--no-ext-diff',baseline_ref+':'+name],capture_output=True,text=True)
                require(previous.returncode == 0 and json.loads(previous.stdout) == json.loads((root/name).read_text()),
                        'Archived return artifact changed; create a new version: '+name)
    return {'package_id':package['id'],'reference_cases':len(corpus['cases']),'table_intervals':len(table['rows']),
            'production_enabled':False,'interpretation_review':'pending'}
