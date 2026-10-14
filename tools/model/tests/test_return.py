import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from validate_model import ROOT, ModelError
from calculate_return import calculate_return, load_return_package, table_tax
from validate_return import validate_return
from validate_interactions import seal
from import_tax_table import extract_rows


class ReturnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifacts = load_return_package()
        cls.request = json.loads((ROOT/'examples/ordinary-return-2025.json').read_text())

    def run_request(self, request):return calculate_return(request,artifacts=self.artifacts)

    def test_references(self):
        summary=validate_return()
        self.assertEqual(summary['reference_cases'],13)
        self.assertFalse(summary['production_enabled'])

    def test_refund_and_source_trace(self):
        report=self.run_request(self.request)
        self.assertEqual(report['lines']['35a'],438)
        self.assertEqual(report['lines']['37'],0)
        self.assertEqual(seal(report),report['sha256'])
        step=next(s for s in report['steps'] if s['line']=='16')
        self.assertEqual(step['tax_table_row']['lower'],25300)
        self.assertEqual(step['evidence'][0]['pdf_page'],5)
        self.assertFalse(report['production_enabled'])
        self.assertIn('penalties',report['excluded'])

    def test_all_tax_table_interval_edges(self):
        table=self.artifacts[1]
        for row in table['rows']:
            for column,status in enumerate(table['columns']):
                for income in (row['lower'], row['upper_exclusive']-1):
                    self.assertEqual(table_tax(table,income,status)[0],row['tax'][column])
        for income in (-1,100000,25300.0,True):
            with self.assertRaises(ModelError):table_tax(table,income,'single')

    def test_published_table_sample(self):
        table=self.artifacts[1]
        self.assertEqual(table_tax(table,25299,'married_joint')[0],2556)
        self.assertEqual(table_tax(table,25300,'married_joint')[0],2562)
        self.assertEqual(table_tax(table,99999,'single')[0],16909)
        self.assertEqual(table_tax(table,0,'single')[0],0)
        self.assertEqual(table_tax(table,5,'single')[0],1)

    def test_whole_dollar_combination_and_document_order(self):
        r=copy.deepcopy(self.request)
        doc=copy.deepcopy(r['documents']['w2'][0]);doc['id']='second-employer'
        doc['boxes']['box1']['value']='27500.25';doc['boxes']['box2']['value']='1500.25'
        doc['boxes']['box3']['value']='27500.25';doc['boxes']['box5']['value']='27500.25'
        first=copy.deepcopy(doc);first['id']='first-employer'
        r['documents']['w2']=[first,doc]
        report=self.run_request(r)
        self.assertEqual(report['lines']['1a'],55001)
        self.assertEqual(report['lines']['25a'],3001)
        r['documents']['w2'].reverse()
        self.assertEqual(self.run_request(r)['lines'],report['lines'])

    def test_missing_each_required_fact_blocks(self):
        for section in ('assessments','deduction_facts'):
            for key in self.request[section]:
                r=copy.deepcopy(self.request);del r[section][key]
                report=self.run_request(r)
                self.assertEqual(report['status'],'blocked',(section,key))
                self.assertEqual(report['lines'],{})
        for kind,docs in self.request['documents'].items():
            for key in docs[0]['boxes']:
                r=copy.deepcopy(self.request);del r['documents'][kind][0]['boxes'][key]
                self.assertEqual(self.run_request(r)['status'],'blocked')

    def test_unconfirmed_facts_do_not_authorize_execution(self):
        for state in ('missing','invalid','estimated','provisional','not_applicable'):
            r=copy.deepcopy(self.request)
            r['documents']['w2'][0]['boxes']['box1']={'state':state,'value':None if state not in ('estimated','provisional') else '55000.00'}
            report=self.run_request(r)
            self.assertEqual(report['status'],'blocked')
            self.assertFalse(report['steps'])

    def test_missing_arrays_are_different_from_empty(self):
        r=copy.deepcopy(self.request);r['documents']['int']=[]
        self.assertEqual(self.run_request(r)['status'],'estimate')
        del r['documents']['int']
        self.assertEqual(self.run_request(r)['status'],'blocked')

    def test_qualified_dividends_not_silently_double_counted(self):
        r=copy.deepcopy(self.request);r['documents']['div'][0]['boxes']['box1b']['value']='100.00'
        self.assertEqual(self.run_request(r)['status'],'blocked')
        r['documents']['div'][0]['boxes']['box1b']['value']='301.00'
        with self.assertRaises(ModelError):self.run_request(r)

    def test_invalid_values_and_unknown_fields(self):
        for value in (-1,55000.0,True,'55000','55000.000','-1.00',None):
            r=copy.deepcopy(self.request);r['documents']['w2'][0]['boxes']['box1']['value']=value
            with self.assertRaises(ModelError):self.run_request(r)
        r=copy.deepcopy(self.request);r['documents']['int'][0]['boxes']['box8']={'state':'confirmed','value':'3.00'}
        with self.assertRaises(ModelError):self.run_request(r)
        r=copy.deepcopy(self.request);r['deduction_facts']['earned_income']={'state':'confirmed','value':'0.00'}
        with self.assertRaises(ModelError):self.run_request(r)

    def test_duplicate_document_ids(self):
        r=copy.deepcopy(self.request);r['documents']['int'][0]['id']=r['documents']['w2'][0]['id']
        with self.assertRaises(ModelError):self.run_request(r)

    def test_each_scope_assessment_and_document_assessment(self):
        for key in self.request['assessments']:
            r=copy.deepcopy(self.request);r['assessments'][key]['value']=False
            self.assertEqual(self.run_request(r)['status'],'blocked',key)
        for kind,docs in self.request['documents'].items():
            for key in docs[0]['assessments']:
                r=copy.deepcopy(self.request);r['documents'][kind][0]['assessments'][key]['value']=False
                self.assertEqual(self.run_request(r)['status'],'blocked',(kind,key))

    def test_filing_status_income_ceilings(self):
        for status,ceiling in self.artifacts[0]['income_ceiling'].items():
            r=copy.deepcopy(self.request);r['deduction_facts']['filing_status']['value']=status
            r['documents']['int']=[];r['documents']['div']=[]
            r['documents']['w2'][0]['boxes']['box1']['value']=str(ceiling)+'.00'
            self.assertEqual(self.run_request(r)['status'],'estimate',status)
            r['documents']['w2'][0]['boxes']['box1']['value']=str(ceiling)+'.01'
            self.assertEqual(self.run_request(r)['status'],'blocked',status)

    def test_eitc_boundary(self):
        for status,threshold in self.artifacts[0]['eitc_screen'].items():
            r=copy.deepcopy(self.request);r['deduction_facts']['filing_status']['value']=status
            r['documents']['int']=[];r['documents']['div']=[]
            r['documents']['w2'][0]['boxes']['box1']['value']=str(threshold-1)+'.00'
            self.assertIn('possible_eitc',{b['code'] for b in self.run_request(r)['blockers']})
            r['documents']['w2'][0]['boxes']['box1']['value']=str(threshold)+'.00'
            self.assertEqual(self.run_request(r)['status'],'estimate')

    def test_payroll_wages_screened_separately_from_box1(self):
        for box in ('box3','box5'):
            r=copy.deepcopy(self.request);r['documents']['w2'][0]['boxes'][box]['value']='200001.00'
            report=self.run_request(r)
            self.assertEqual(report['status'],'blocked')
            self.assertEqual(report['lines'],{})

    def test_deduction_scope_and_year(self):
        for key,value in [('residency','dual_status'),('entity_kind','estate_trust'),('disaster_loss_adjustment_requested',True),('short_year_accounting_change',True),('self_claimable',True),('self_age_qualified',True),('filing_status','head_of_household')]:
            r=copy.deepcopy(self.request);r['deduction_facts'][key]['value']=value
            self.assertEqual(self.run_request(r)['status'],'blocked',(key,value))
        r=copy.deepcopy(self.request);r['tax_year']=2026
        self.assertEqual(self.run_request(r)['status'],'blocked')
        r=copy.deepcopy(self.request);r['deduction_method']['value']='itemized'
        self.assertEqual(self.run_request(r)['status'],'blocked')

    def test_source_bytes_are_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for directory in ('model','evidence','schemas'):
                shutil.copytree(ROOT/directory,root/directory)
            path=root/'evidence/irs/2025/p1040.pdf'
            with path.open('ab') as file:file.write(b'changed')
            with self.assertRaises(ModelError):load_return_package(root)

    def test_import_rejects_missing_and_duplicate_rows(self):
        with self.assertRaises(ModelError):extract_rows([(2,'0 5 0 0 0 0')])
        with self.assertRaises(ModelError):extract_rows([(2,'0 5 0 0 0 0\n0 5 0 0 0 0')])

    def test_cli_private_output_no_overwrite_no_amount_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'report.json'
            cmd=[sys.executable,str(ROOT/'tools/model/calculate_return.py'),'--input',str(ROOT/'examples/ordinary-return-2025.json'),'--output',str(path)]
            result=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertNotIn('55000',result.stdout+result.stderr)
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            content=path.read_bytes()
            self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,1)
            self.assertEqual(content,path.read_bytes())

    def test_cli_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            input=Path(tmp)/'request.json';input.write_text('{"tax_year":2025,"tax_year":2026}')
            output=Path(tmp)/'report.json'
            result=subprocess.run([sys.executable,str(ROOT/'tools/model/calculate_return.py'),'--input',str(input),'--output',str(output)],capture_output=True,text=True)
            self.assertEqual(result.returncode,1)
            self.assertFalse(output.exists())


if __name__=='__main__':unittest.main()
