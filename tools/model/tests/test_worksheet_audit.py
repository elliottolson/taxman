"""Second-source differential checks; this is a same-author audit, not approval."""
import copy
from itertools import product
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from validate_model import ROOT,ModelError
from validate_interactions import seal
from validate_worksheet import load_worksheet_registry,validate_worksheet,worksheet_report,preserve_worksheet_registry
from worksheet_engine import evaluate_worksheet

# Published Form 1040 2025 chart, PDF page 35. Deliberately not read from program parameters.
CHART={
    'single':[1575000,1775000,1975000],
    'married_joint':[3150000,3310000,3470000,3630000,3790000],
    'married_separate':[1575000,1735000,1895000,2055000,2215000],
    'head_of_household':[2362500,2562500,2762500],
}


class WorksheetAuditTests(unittest.TestCase):
    def setUp(self):
        self.registry,self.packages=load_worksheet_registry(ROOT)
        self.data=copy.deepcopy(self.packages[self.registry['active']])
        self.ledger=json.loads((ROOT/'model/claim-ledger.json').read_text())
        self.schema=json.loads((ROOT/'schemas/worksheet-package.schema.json').read_text())
        self.base=copy.deepcopy(next(c for c in self.data['cases'] if c['id']=='table6.single')['inputs'])

    def test_current_and_historical_packages_are_verified(self):
        self.assertEqual(len(self.packages),2)
        self.assertEqual(self.registry['active'],'standard-deduction-package-v2.json')
        result=validate_worksheet(self.data,self.schema,self.ledger,ROOT)
        self.assertEqual(result['cases'],48)

    def test_requested_disaster_adjustment_is_explicitly_unsupported(self):
        self.base['disaster_loss_adjustment_requested']['value']=True
        result=evaluate_worksheet(self.data['plan'],self.base)['result']
        self.assertEqual(result['status'],'unsupported')
        self.assertEqual(result['reason'],'qualified_disaster_loss_adjustment_unimplemented')
        self.assertNotIn('value',result)

    def test_absent_disaster_fact_cannot_silently_mean_false(self):
        del self.base['disaster_loss_adjustment_requested']
        self.assertEqual(evaluate_worksheet(self.data['plan'],self.base)['result'],{'status':'blocked','reason':'unresolved_fact:disaster_loss_adjustment_requested'})

    def test_estimated_disaster_fact_blocks(self):
        self.base['disaster_loss_adjustment_requested']['state']='estimated'
        self.assertEqual(evaluate_worksheet(self.data['plan'],self.base)['result']['status'],'blocked')

    def test_report_does_not_assign_tax_audit_to_user(self):
        report=worksheet_report(self.data,self.ledger,ROOT)
        self.assertEqual(report['designated_reviewer'],'not_assigned')
        self.assertEqual(report['interpretation_review'],'pending')

    def test_disaster_scope_guard_precedes_numeric_exclusion_results(self):
        self.base['disaster_loss_adjustment_requested']['value']=True
        for field in ['short_year_accounting_change','spouse_itemizes']:
            facts=copy.deepcopy(self.base)
            facts['filing_status']['value']='married_separate'
            facts[field]['value']=True
            self.assertEqual(evaluate_worksheet(self.data['plan'],facts)['result']['status'],'unsupported')

    def test_unknown_disaster_fact_does_not_emit_a_premature_zero(self):
        self.base['short_year_accounting_change']['value']=True
        del self.base['disaster_loss_adjustment_requested']
        self.assertEqual(evaluate_worksheet(self.data['plan'],self.base)['result']['status'],'blocked')

    def test_registry_cannot_remove_an_old_archive(self):
        changed=copy.deepcopy(self.registry);changed['archives'].pop()
        with self.assertRaisesRegex(ModelError,'archive pin removed'):
            preserve_worksheet_registry(changed,self.registry)

    def test_registry_cannot_retarget_a_historical_hash(self):
        changed=copy.deepcopy(self.registry);changed['archives'][0]['sha256']='0'*64
        with self.assertRaisesRegex(ModelError,'archive pin removed'):
            preserve_worksheet_registry(changed,self.registry)

    def test_form1040_second_source_agrees_across_10240_combinations(self):
        # Form 1040 dependent worksheet asks "earned income > $900?" and uses a chart offset.
        # This differs from the program's max/floor expressions and rate*box calculation.
        earned_cases=[0,89949,89999,90000,90001,90100,1529999,1530000,1530001,4000000]
        checks=0
        for status in CHART:
            for flags in product([False,True],repeat=8):
                self_claim,spouse_claim,self_age,self_blind,spouse_age,spouse_blind,gross_zero,files_return=flags
                dependent=self_claim or (status=='married_joint' and spouse_claim)
                spouse_allowed=status=='married_joint' or (status=='married_separate' and gross_zero and not files_return and not spouse_claim)
                count=int(self_age)+int(self_blind)+(int(spouse_age)+int(spouse_blind) if spouse_allowed else 0)
                published=CHART[status][count]
                base=CHART[status][0]
                facts=copy.deepcopy(self.base)
                for name,val in {'filing_status':status,'self_claimable':self_claim,'spouse_claimable':spouse_claim,'self_age_qualified':self_age,'self_blind_qualified':self_blind,'spouse_age_qualified':spouse_age,'spouse_blind_qualified':spouse_blind,'spouse_gross_income_zero':gross_zero,'spouse_files_return':files_return}.items():facts[name]['value']=val
                for earned in earned_cases:
                    facts['earned_income']={'state':'confirmed','value':f'{earned//100}.{earned%100:02d}'}
                    worksheet_line2=earned+45000 if earned>90000 else 135000
                    limited=worksheet_line2 if worksheet_line2<base else base
                    expected=limited+(published-base) if dependent else published
                    result=evaluate_worksheet(self.data['plan'],facts)['result']
                    self.assertEqual(result['status'],'value')
                    self.assertEqual(result['value'],f'{expected//100}.{expected%100:02d}',(status,flags,earned))
                    checks+=1
        self.assertEqual(checks,10240)


if __name__=='__main__':unittest.main()
