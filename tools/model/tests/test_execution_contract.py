import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from validate_model import ROOT, ModelError, load
from validate_interactions import seal, digest
from compile_package import compile_package, run_case, verification_report
from validate_execution import validate_execution, validate_report, validate_trace


class ExecutionContractTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/'model/execution-contract.json').read_text())
        self.schema=json.loads((ROOT/'schemas/execution-contract.schema.json').read_text())
        _,_,self.schemas,_=load()
        self.program=self.data['programs'][0]
        self.request=self.data['requests'][0]
        self.package=self.data['packages'][0]
        self.cases=[c for c in self.data['fixtures'] if self.package['package_id'] in c['package_ids']]
        self.runner_hash=hashlib.sha256((ROOT/'tools/model/compile_package.py').read_bytes()).hexdigest()

    def compile(self):
        return compile_package(self.program,self.request,self.schemas,self.program['catalog'],self.program['registry'])

    def check(self,previous=None):
        return validate_execution(self.data,self.schema,self.schemas,ROOT,previous)

    def reject_compile(self,pattern):
        with self.assertRaisesRegex(ModelError,pattern):self.compile()

    def case(self,id):
        return next(c for c in self.data['fixtures'] if c['id']==id)

    def test_saved_packages_reproduce(self):
        reports=self.check()
        self.assertEqual(len(reports),3)
        self.assertTrue(all(r['calculation_comparison']=='passed' for r in reports.values()))
        self.assertTrue(all(not r['production_eligible'] for r in reports.values()))

    def test_compilation_is_deterministic(self):
        self.assertEqual(self.compile(),self.compile())
        self.assertEqual(self.compile(),self.package)

    def test_dependency_order_does_not_follow_author_order(self):
        before=self.compile()
        for section in ['facts','parameters','rules','decisions','elections']:
            self.program['model'][section].reverse()
        self.program['rule_revisions'].reverse()
        after=self.compile()
        self.assertEqual(before['nodes'],after['nodes'])
        self.assertNotEqual(before['program_sha256'],after['program_sha256'])

    def test_all_potential_branches_are_in_plan(self):
        targets={n['target'] for n in self.package['nodes']}
        self.assertIn('fact:design.exception_amount',targets)
        seen=set()
        for node in self.package['nodes']:
            self.assertTrue(set(node['dependencies']) <= seen)
            seen.add(node['target'])

    def test_historical_correction_pins_distinct_versions(self):
        versions=[next(n for n in p['nodes'] if n['target']=='rule:design.adjusted')['revision_id'] for p in self.data['packages']]
        self.assertEqual(versions,['design.adjusted.v1','design.adjusted.v2','design.adjusted.v2'])

    def test_missing_historical_revision_does_not_fall_back(self):
        self.request['known_at']='2025-01-01T00:00:00Z'
        self.reject_compile('exactly one revision')

    def test_ambiguous_revisions_rejected(self):
        r=copy.deepcopy(self.program['rule_revisions'][0]);r['id']='competing';r['sha256']=seal(r)
        self.program['rule_revisions'].append(r)
        self.reject_compile('exactly one revision')

    def test_wrong_revision_digest_rejected(self):
        self.program['rule_revisions'][0]['definition']['label']='Changed'
        self.reject_compile('digest mismatch')

    def test_missing_dependency_rejected(self):
        self.program['model']['facts']=[f for f in self.program['model']['facts'] if f['id']!='design.gross']
        self.reject_compile('Unknown reference')

    def test_cycle_rejected(self):
        r=self.program['rule_revisions'][0]
        r['definition']['execution']['expression']={'kind':'ref','target':'rule:design.base'}
        r['definition']['declared_dependencies']=['rule:design.base'];r['sha256']=seal(r)
        self.reject_compile('Execution dependency cycle')

    def test_missing_parameter_year_rejected(self):
        self.program['parameter_bindings']=[b for b in self.program['parameter_bindings'] if b['tax_year']!=2025]
        self.reject_compile('Missing annual parameter binding')

    def test_stale_parameter_binding_rejected(self):
        self.program['parameter_bindings'][0]['definition_sha256']='0'*64
        self.reject_compile('Stale parameter binding')

    def test_conflicting_parameter_bindings_rejected(self):
        b=copy.deepcopy(self.program['parameter_bindings'][0]);b['id']='competing'
        self.program['parameter_bindings'].append(b)
        self.reject_compile('Conflicting annual parameter')

    def test_invalid_parameter_value_rejected(self):
        self.program['parameter_bindings'][0]['value']=100.0
        self.reject_compile('Invalid exact money')

    def test_unpopulated_parameter_rejected(self):
        p=self.program['model']['parameters'][0];p.update(value_status='unpopulated',value=None)
        for b in self.program['parameter_bindings']:b['definition_sha256']=digest(p)
        self.program['parameter_bindings'][0]['value']=None
        self.reject_compile('Missing annual parameter value')

    def test_annual_amounts_cannot_leak_between_years(self):
        p=self.data['packages'][2]
        actual,_=run_case(p,self.case('2026-base'))
        self.assertEqual(actual,{'rule:design.adjusted':{'status':'value','value':'880.00'}})
        self.assertEqual(next(n['definition']['value'] for n in p['nodes'] if n['target']=='parameter:design.base'),'120.00')

    def test_unused_missing_input_does_not_block_selected_result(self):
        actual,trace=run_case(self.package,self.case('base-unused-missing'))
        self.assertEqual(actual,{'rule:design.adjusted':{'status':'value','value':'900.00'}})
        self.assertNotIn('fact:design.exception_amount',{n['target'] for n in trace['nodes']})

    def test_selected_missing_input_blocks(self):
        actual,trace=run_case(self.package,self.case('exception-missing'))
        self.assertEqual(actual['rule:design.adjusted']['status'],'blocked')
        fact=next(n for n in trace['nodes'] if n['target']=='fact:design.exception_amount')
        self.assertEqual(fact['detail']['fact_state'],'missing')

    def test_trace_explains_exception_and_confirmation(self):
        _,trace=run_case(self.package,self.case('exception'))
        nodes={n['target']:n for n in trace['nodes']}
        self.assertEqual(nodes['decision:design.exception']['detail']['selected_row'],'exception')
        self.assertEqual(nodes['election:design.method']['detail']['confirmation_id'],'design.confirmation')
        self.assertTrue(nodes['rule:design.exception']['detail']['applicability']['value'])
        self.assertEqual(nodes['rule:design.exception']['evidence'][0]['source_id'],'design-spec')

    def test_stale_confirmation_has_explicit_reason(self):
        _,trace=run_case(self.package,self.case('stale-confirmation'))
        node=next(n for n in trace['nodes'] if n['target']=='election:design.method')
        self.assertEqual(node['result']['reason'],'stale_confirmation')

    def test_unknown_condition_is_visible(self):
        _,trace=run_case(self.package,self.case('unknown-condition'))
        node=next(n for n in trace['nodes'] if n['target']=='decision:design.exception')
        self.assertEqual(node['result']['reason'],'unresolved_condition')

    def test_unconfirmed_and_ineligible_elections_do_not_select(self):
        for id in ['unconfirmed','ineligible']:
            actual,_=run_case(self.package,self.case(id))
            self.assertEqual(actual['rule:design.adjusted']['status'],'blocked')

    def test_unknown_case_inputs_are_rejected(self):
        c=self.case('exception');c['inputs']['fact:unknown']={'state':'confirmed','value':'1.00'}
        with self.assertRaisesRegex(ModelError,'Unknown case input'):run_case(self.package,c)

    def test_type_and_float_values_rejected(self):
        c=self.case('exception');c['inputs']['fact:design.gross']['value']=1000.0
        with self.assertRaisesRegex(ModelError,'Invalid exact money'):run_case(self.package,c)
        c['inputs']['fact:design.gross']['value']='1000.00';c['inputs']['fact:design.exception']['value']='false'
        with self.assertRaisesRegex(ModelError,'Invalid Boolean'):run_case(self.package,c)

    def test_estimated_values_never_become_confirmed(self):
        c=self.case('exception');c['inputs']['fact:design.gross']['state']='estimated'
        actual,_=run_case(self.package,c)
        self.assertEqual(actual['rule:design.adjusted']['status'],'blocked')

    def test_report_binds_package_fixtures_and_runner(self):
        r=verification_report(self.package,self.cases,self.runner_hash,self.program,self.request,self.schemas)
        validate_report(r,self.package,self.cases,self.schema,self.runner_hash,self.program,self.request,self.schemas)
        self.assertEqual(r['package_sha256'],self.package['sha256'])
        self.assertEqual(r['runner_sha256'],self.runner_hash)
        self.assertEqual(r['interpretation_review'],'synthetic_not_tax_law')
        self.assertFalse(r['production_eligible'])

    def test_wrong_expected_result_generates_failed_comparison(self):
        self.cases[0]['expected']['rule:design.adjusted']={'status':'value','value':'42.00'}
        self.cases[0]['sha256']=seal(self.cases[0])
        r=verification_report(self.package,self.cases,self.runner_hash,self.program,self.request,self.schemas)
        self.assertEqual(r['calculation_comparison'],'failed')
        validate_report(r,self.package,self.cases,self.schema,self.runner_hash,self.program,self.request,self.schemas)

    def test_empty_report_cannot_claim_pass(self):
        r=verification_report(self.package,[],self.runner_hash,self.program,self.request,self.schemas)
        self.assertEqual(r['calculation_comparison'],'failed')

    def test_report_tamper_even_after_resealing_is_rejected(self):
        r=verification_report(self.package,self.cases,self.runner_hash,self.program,self.request,self.schemas)
        r['results'][0]['actual']['rule:design.adjusted']={'status':'value','value':'42.00'};r['sha256']=seal(r)
        with self.assertRaisesRegex(ModelError,'Verification report does not match'):
            validate_report(r,self.package,self.cases,self.schema,self.runner_hash,self.program,self.request,self.schemas)

    def test_runner_hash_mismatch_rejected(self):
        r=verification_report(self.package,self.cases,self.runner_hash,self.program,self.request,self.schemas)
        with self.assertRaisesRegex(ModelError,'Verification report does not match'):
            validate_report(r,self.package,self.cases,self.schema,'0'*64,self.program,self.request,self.schemas)

    def test_trace_forged_branch_rejected_even_after_resealing(self):
        c=self.case('exception');_,t=run_case(self.package,c)
        next(n for n in t['nodes'] if n['target']=='decision:design.exception')['detail']['selected_row']='base'
        t['sha256']=seal(t)
        with self.assertRaisesRegex(ModelError,'Trace does not match'):validate_trace(t,self.package,c,self.schema)

    def test_trace_cannot_hide_missing_input(self):
        c=self.case('exception-missing');_,t=run_case(self.package,c)
        t['nodes']=[n for n in t['nodes'] if n['target']!='fact:design.exception_amount'];t['sha256']=seal(t)
        with self.assertRaisesRegex(ModelError,'Trace does not match'):validate_trace(t,self.package,c,self.schema)

    def test_package_tamper_rejected(self):
        self.package['nodes'][0]['definition']['label']='Changed'
        with self.assertRaisesRegex(ModelError,'Package digest'):run_case(self.package,self.cases[0])

    def test_resealed_package_not_matching_compiler_rejected(self):
        self.package['nodes'][0]['definition']['label']='Changed';self.package['sha256']=seal(self.package)
        with self.assertRaisesRegex(ModelError,'differs from deterministic'):self.check()

    def test_report_cannot_claim_structural_success_for_resealed_bad_plan(self):
        self.package['nodes'][0]['definition']['label']='Changed'
        self.package['sha256']=seal(self.package)
        with self.assertRaisesRegex(ModelError,'Structural verification requires'):
            verification_report(self.package,self.cases,self.runner_hash,self.program,self.request,self.schemas)

    def test_production_mode_is_rejected(self):
        self.data['production_enabled']=True
        with self.assertRaisesRegex(ModelError,'Schema error'):self.check()

    def test_history_cannot_be_rewritten(self):
        previous=copy.deepcopy(self.data)
        self.data['fixtures'][0]['oracle']='Changed provenance';self.data['fixtures'][0]['sha256']=seal(self.data['fixtures'][0])
        with self.assertRaisesRegex(ModelError,'Archived execution record changed'):self.check(previous)

    def test_saved_dependency_edge_cannot_be_removed(self):
        node=next(n for n in self.package['nodes'] if n['target']=='rule:design.adjusted')
        node['dependencies']=[];self.package['sha256']=seal(self.package)
        with self.assertRaisesRegex(ModelError,'differs from deterministic'):self.check()

    def test_draft_tax_mode_is_never_silently_executed(self):
        self.program['mode']='tax_research'
        with self.assertRaisesRegex(ModelError,'Tax compilation needs'):self.compile()
        ledger=json.loads((ROOT/'model/claim-ledger.json').read_text())
        with self.assertRaisesRegex(ModelError,'Draft tax definition blocks'):
            compile_package(self.program,self.request,self.schemas,self.program['catalog'],self.program['registry'],ledger)

    def test_unsupported_modules_fail_even_with_an_interface(self):
        module={'id':'design.module','label':'Synthetic module interface','status':'drafted','version':'0.1.0','implementation_status':'interface_only','inputs':[],'result_type':'Money','result_shape':'scalar','cycle_policy':'acyclic','evidence':copy.deepcopy(self.program['model']['rules'][0]['evidence'])}
        self.program['model']['modules'].append(module)
        r=self.program['rule_revisions'][0]
        r['definition']['execution']={'kind':'module','module_id':'design.module','module_version':'0.1.0','bindings':[]}
        r['definition']['declared_dependencies']=[];r['sha256']=seal(r)
        self.reject_compile('Module execution is unsupported')

    def test_unsupported_indexed_lookup_fails(self):
        p=self.program['model']['parameters'][0]
        p['axes']=[{'name':'exception','value_type':'Boolean'}]
        for b in self.program['parameter_bindings']:b['definition_sha256']=digest(p)
        r=self.program['rule_revisions'][0]
        r['definition']['execution']['expression']={'kind':'lookup','parameter':'parameter:design.base','keys':[{'name':'exception','value':{'kind':'ref','target':'fact:design.exception'}}]}
        r['definition']['declared_dependencies']=['parameter:design.base','fact:design.exception'];r['sha256']=seal(r)
        self.reject_compile('Indexed parameter lookup is unsupported')

    def test_report_fixture_cannot_be_reused_for_other_year(self):
        with self.assertRaisesRegex(ModelError,'belongs to another package'):
            run_case(self.data['packages'][2],self.case('base-unused-missing'))

    def test_report_requires_fixture_content_integrity(self):
        self.cases[0]['oracle']='Changed without resealing'
        with self.assertRaisesRegex(ModelError,'Fixture digest mismatch'):
            verification_report(self.package,self.cases,self.runner_hash,self.program,self.request,self.schemas)

    def test_unsupported_rounding_fails(self):
        r=self.program['rule_revisions'][0];r['definition']['rounding_policy']='year_method_defined';r['sha256']=seal(r)
        self.reject_compile('Unsupported rounding')

    def test_multi_subject_values_require_a_binding_compiler(self):
        self.program['model']['facts'][0]['scope']='taxpayer'
        self.reject_compile('Subject binding is unsupported')


if __name__=='__main__':unittest.main()
