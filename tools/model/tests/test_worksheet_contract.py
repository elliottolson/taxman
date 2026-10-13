import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from validate_model import ROOT,ModelError
from validate_interactions import seal,digest
from worksheet_engine import annual_table,compile_worksheet,evaluate_worksheet
from validate_worksheet import validate_worksheet,worksheet_report,validate_worksheet_report


class WorksheetTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/'model/standard-deduction-package.json').read_text())
        self.schema=json.loads((ROOT/'schemas/worksheet-package.schema.json').read_text())
        self.ledger=json.loads((ROOT/'model/claim-ledger.json').read_text())

    def case(self,id):return next(c for c in self.data['cases'] if c['id']==id)
    def evaluate(self,id):return evaluate_worksheet(self.data['plan'],self.case(id)['inputs'])
    def compile(self):return compile_worksheet(self.data['program'],self.data['context'],self.ledger)
    def check(self,previous=None):return validate_worksheet(self.data,self.schema,self.ledger,ROOT,previous)

    def test_reference_corpus_compares_final_and_intermediate_values(self):
        r=self.check()
        self.assertEqual((r['cases'],r['reused_references']),(46,10))
        self.assertEqual(r['calculation_comparison'],'passed')
        self.assertEqual(r['interpretation_review'],'pending')
        self.assertFalse(r['production_eligible'])

    def test_published_blind_dependent_steps(self):
        r=self.evaluate('published.dependent.blind');steps={s['id']:s['result'].get('value') for s in r['steps'] if s['status']=='value'}
        self.assertEqual(r['result']['value'],'5350.00')
        self.assertEqual([steps[k] for k in ['line1','line2','line3','line4','line5','line6','line7a','line7b','line7c']],['2900.00','450.00','3350.00','1350.00','3350.00','15750.00','3350.00','2000.00','5350.00'])

    def test_published_business_loss_example_uses_normalized_earned_input(self):
        r=self.evaluate('published.dependent.net-earned')
        self.assertEqual(r['result']['value'],'4450.00')
        self.assertEqual(self.case('published.dependent.net-earned')['inputs']['earned_income']['value'],'4000.00')

    def test_filing_status_tables_and_all_published_box_counts(self):
        for c in self.data['cases']:
            if c['id'].startswith(('table6.','table7.')):
                actual=evaluate_worksheet(self.data['plan'],c['inputs'])
                self.assertEqual(actual['result']['value'],c['expected']['value'],c['id'])

    def test_non_dependent_does_not_need_earned_income(self):
        facts=self.case('table6.single')['inputs'];facts.pop('earned_income',None)
        actual=evaluate_worksheet(self.data['plan'],facts)
        self.assertEqual(actual['result']['value'],'15750.00')
        self.assertFalse(any(s['id']=='line1' for s in actual['steps']))

    def test_missing_earned_income_does_not_become_zero(self):
        r=self.evaluate('reference.dependent.missing-earned')
        self.assertEqual(r['result'],{'status':'blocked','reason':'unresolved_fact:earned_income'})

    def test_dependent_spouse_routes_mfj_to_dependent_cap(self):
        r=self.evaluate('mfj.spouse-dependent')
        self.assertEqual(r['result']['value'],'31500.00')
        self.assertTrue(next(s for s in r['steps'] if s['id']=='dependent')['result']['value'])

    def test_age_addition_is_added_after_dependent_cap(self):
        r=self.evaluate('dependent.addition-after-cap')
        self.assertEqual(r['result']['value'],'17750.00')

    def test_mfs_spouse_footnote_conditions_are_separate(self):
        for id in ['mfs.spouse-income','mfs.spouse-files','mfs.spouse-claimable']:
            self.assertEqual(self.evaluate(id)['result']['value'],'15750.00')
        self.assertEqual(self.evaluate('table7.married_separate.4')['result']['value'],'22150.00')

    def test_qualifying_surviving_spouse_does_not_count_deceased_spouse_boxes(self):
        c=self.case('table6.qualifying_surviving_spouse');c['inputs']['spouse_age_qualified']['value']=True;c['inputs']['spouse_blind_qualified']['value']=True
        self.assertEqual(evaluate_worksheet(self.data['plan'],c['inputs'])['result']['value'],'31500.00')

    def test_known_exclusions_return_explained_zero(self):
        for id in ['excluded.short-year','excluded.spouse-itemizes']:
            r=self.evaluate(id)['result'];self.assertEqual(r['status'],'ineligible');self.assertEqual(r['value'],'0.00')

    def test_residency_and_treaty_scope_is_not_silently_denied(self):
        for id in ['scope.nonresident','scope.dual-status']:
            r=self.evaluate(id)['result'];self.assertEqual(r['status'],'unsupported');self.assertNotIn('value',r)

    def test_other_entities_and_dependent_qss_remain_unsupported(self):
        for id in ['scope.estate','scope.dependent-qss']:self.assertEqual(self.evaluate(id)['result']['status'],'unsupported')

    def test_enhanced_senior_deduction_not_included(self):
        self.assertEqual(self.evaluate('table7.single.1')['result']['value'],'17750.00')

    def test_cents_are_preserved_until_explicit_rounding(self):
        self.assertEqual(self.evaluate('dependent.cents')['result']['value'],'1350.50')

    def test_exact_annual_year_selection(self):
        t=copy.deepcopy(self.data['program']['tables'][0]);t['axes']['tax_year']['values']=[2025,2026]
        rows=[]
        for row in t['rows']:
            new=copy.deepcopy(row);new['keys']['tax_year']=2026;new['value']='1.00';rows.append(new)
        t['rows']+=rows
        self.assertTrue(all(r['value']=='1.00' for r in annual_table(t,2026)['rows']))
        self.assertTrue(all(r['value']!='1.00' for r in annual_table(t,2025)['rows']))
        with self.assertRaisesRegex(ModelError,'Missing annual table year'):annual_table(t,2027)

    def test_unpopulated_year_cannot_fall_back(self):
        self.data['context']['tax_year']=2026
        with self.assertRaisesRegex(ModelError,'Unsupported worksheet tax year'):self.compile()

    def test_duplicate_annual_keys_fail(self):
        self.data['program']['tables'][0]['rows'].append(copy.deepcopy(self.data['program']['tables'][0]['rows'][0]))
        with self.assertRaisesRegex(ModelError,'Overlapping annual'):self.compile()

    def test_uncovered_annual_keys_fail(self):
        self.data['program']['tables'][0]['rows'].pop()
        with self.assertRaisesRegex(ModelError,'Uncovered annual'):self.compile()

    def test_enum_axis_cannot_hide_unsupported_statuses(self):
        table=self.data['program']['tables'][0]
        table['axes']['filing_status']['values']=['single']
        table['rows']=table['rows'][:1]
        with self.assertRaisesRegex(ModelError,'must cover its declared domain'):self.compile()

    def test_fractional_cent_intermediates_require_explicit_rounding(self):
        final=next(s for s in self.data['program']['steps'] if s['id']=='line7c')
        final['expression']={'kind':'operator','operator':'round','scale':2,'mode':'half_up','arguments':[{'kind':'operator','operator':'divide','arguments':[{'kind':'literal','value_type':'Money','value':'1.00'},{'kind':'literal','value_type':'Integer','value':3}]}]}
        plan=self.compile()
        self.assertEqual(evaluate_worksheet(plan,self.case('table6.single')['inputs'])['result']['value'],'0.33')

    def test_lookup_key_type_mismatch(self):
        s=next(s for s in self.data['program']['steps'] if s['id']=='line6')
        s['expression']['keys']['filing_status']={'kind':'ref','target':'input:self_claimable'}
        with self.assertRaisesRegex(ModelError,'Lookup key type'):self.compile()

    def test_cycle_and_unknown_reference_fail(self):
        s=self.data['program']['steps'][0];s['expression']={'kind':'ref','target':'step:'+s['id']}
        with self.assertRaisesRegex(ModelError,'dependency cycle'):self.compile()
        s['expression']={'kind':'ref','target':'step:absent'}
        with self.assertRaisesRegex(ModelError,'Unknown worksheet reference'):self.compile()

    def test_arithmetic_unit_mismatch_fails(self):
        s=next(s for s in self.data['program']['steps'] if s['id']=='line7b')
        s['expression']['arguments'][1]={'kind':'literal','value_type':'Money','value':'1.00'}
        with self.assertRaisesRegex(ModelError,'Money times Money'):self.compile()

    def test_unknown_inputs_and_invalid_booleans_fail(self):
        facts=self.case('table6.single')['inputs'];facts['unknown']={'state':'confirmed','value':True}
        with self.assertRaisesRegex(ModelError,'Unknown worksheet input'):evaluate_worksheet(self.data['plan'],facts)
        del facts['unknown'];facts['self_age_qualified']['value']='false'
        with self.assertRaisesRegex(ModelError,'Invalid Boolean'):evaluate_worksheet(self.data['plan'],facts)

    def test_estimated_or_missing_eligibility_blocks(self):
        facts=self.case('table6.single')['inputs'];facts['self_age_qualified']['state']='estimated'
        self.assertEqual(evaluate_worksheet(self.data['plan'],facts)['result']['status'],'blocked')

    def test_missing_irrelevant_spouse_criterion_does_not_block_single(self):
        facts=self.case('table6.single')['inputs']
        for k in list(facts):
            if k.startswith('spouse_'):del facts[k]
        self.assertEqual(evaluate_worksheet(self.data['plan'],facts)['result']['value'],'15750.00')

    def test_plan_tamper_even_after_resealing_fails_compilation_comparison(self):
        self.data['plan']['tables'][0]['rows'][0]['value']='1.00';self.data['plan']['sha256']=seal(self.data['plan'])
        with self.assertRaisesRegex(ModelError,'plan differs'):self.check()

    def test_claim_and_source_pins_are_checked(self):
        self.data['program']['claim_refs'][0]['sha256']='0'*64
        with self.assertRaisesRegex(ModelError,'claim pin mismatch'):self.compile()
        self.data['program']['claim_refs'][0]['sha256']=self.ledger['claims'][0]['sha256']
        self.data['program']['steps'][0]['evidence'][0]['source_sha256']='0'*64
        with self.assertRaisesRegex(ModelError,'evidence pin mismatch'):self.compile()

    def test_worksheet_does_not_claim_approval_or_production(self):
        self.data['production_enabled']=True
        with self.assertRaisesRegex(ModelError,'Schema error'):self.check()

    def test_original_fixture_result_cannot_be_reinterpreted(self):
        c=self.case('reference.base.single');c['expected']['value']='1.00';c['sha256']=seal(c)
        with self.assertRaisesRegex(ModelError,'Original reference result changed|Review fixture worksheet expectations mismatch'):self.check()

    def test_wrong_intermediate_result_fails_verification(self):
        c=self.case('published.dependent.blind');c['expected_steps']['line3']='1.00';c['sha256']=seal(c)
        r=worksheet_report(self.data,self.ledger,ROOT)
        self.assertEqual(r['calculation_comparison'],'failed')

    def test_archived_package_cannot_be_rewritten(self):
        previous=copy.deepcopy(self.data);c=self.case('table6.single');c['oracle_note']='Changed';c['sha256']=seal(c)
        with self.assertRaisesRegex(ModelError,'Archived worksheet package changed'):self.check(previous)

    def test_resealed_forged_intermediate_trace_is_rejected(self):
        r=worksheet_report(self.data,self.ledger,ROOT)
        case=next(c for c in r['results'] if c['case_id']=='published.dependent.blind')
        next(s for s in case['actual']['steps'] if s['id']=='line3')['result']['value']='1.00'
        case['actual']['sha256']=seal(case['actual']);r['sha256']=seal(r)
        with self.assertRaisesRegex(ModelError,'report does not match'):
            validate_worksheet_report(r,self.data,self.schema,self.ledger,ROOT)

    def test_approval_claim_cannot_be_added_to_report(self):
        r=worksheet_report(self.data,self.ledger,ROOT);r['interpretation_review']='approved';r['sha256']=seal(r)
        with self.assertRaisesRegex(ModelError,'Schema error'):
            validate_worksheet_report(r,self.data,self.schema,self.ledger,ROOT)

    def test_persistent_review_subject_includes_adapter_assumptions(self):
        c=self.case('reference.base.single')
        record=next(f for f in self.ledger['fixtures'] if f['id']==c['review_fixture']['id'])
        record['inputs']['residency']['data']['value']='nonresident'
        record['sha256']=seal(record);c['review_fixture']['sha256']=record['sha256'];c['sha256']=seal(c)
        with self.assertRaisesRegex(ModelError,'input assumptions mismatch'):self.check()

    def test_research_report_pins_all_runner_sources(self):
        r=worksheet_report(self.data,self.ledger,ROOT)
        self.assertEqual(set(r['runner_sources']),{'worksheet_engine.py','exact_numbers.py','validate_worksheet.py'})
        self.assertEqual(r['interpretation_review'],'pending');self.assertEqual(r['reference_review'],'pending')
        self.assertFalse(r['production_eligible'])


if __name__=='__main__':unittest.main()
