import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validate_model import ModelError, load, validate


class ModelContractTests(unittest.TestCase):
    def setUp(self):
        self.model, self.catalog, self.schemas, self.sources = copy.deepcopy(load())

    def check(self):
        return validate(self.model, self.catalog, self.schemas, self.sources)

    def rule(self, identity):
        return next(r for r in self.model['rules'] if r['id'] == identity)

    def test_draft_model_and_domain_relationship_cycle_are_valid(self):
        self.assertEqual(self.check()['rules'], 10)
        self.assertFalse(self.model['production_enabled'])

    def test_missing_reference_is_rejected(self):
        self.rule('income.nonqualified')['execution']['expression']['arguments'][0]['target'] = 'rule:absent'
        with self.assertRaisesRegex(ModelError, 'Unknown reference'):
            self.check()

    def test_duplicate_rule_id_is_rejected(self):
        self.model['rules'].append(copy.deepcopy(self.model['rules'][0]))
        with self.assertRaisesRegex(ModelError, 'Duplicate ID'):
            self.check()

    def test_source_reference_is_required_to_exist(self):
        self.model['rules'][0]['evidence'][0]['source_id'] = 'absent-source'
        with self.assertRaisesRegex(ModelError, 'Unknown source'):
            self.check()

    def test_unpopulated_parameter_cannot_contain_a_value(self):
        self.model['parameters'][0]['value'] = '100.00'
        with self.assertRaisesRegex(ModelError, 'Schema error'):
            self.check()

    def test_declared_dependencies_cannot_hide_a_reference(self):
        self.rule('income.nonqualified')['declared_dependencies'] = []
        with self.assertRaisesRegex(ModelError, 'Declared dependencies mismatch'):
            self.check()

    def test_rule_output_type_must_match_expression(self):
        self.rule('income.nonqualified')['value_type'] = 'Boolean'
        with self.assertRaisesRegex(ModelError, 'Output type mismatch'):
            self.check()

    def test_execution_cycle_is_rejected(self):
        rule = self.rule('income.nonqualified')
        rule['execution']['expression']['arguments'][0]['target'] = 'rule:income.nonqualified'
        rule['declared_dependencies'] = ['rule:income.nonqualified', 'rule:income.qualified']
        with self.assertRaisesRegex(ModelError, 'Execution dependency cycle'):
            self.check()

    def test_identical_unique_decision_conditions_are_rejected(self):
        rows = self.model['decisions'][0]['rows']
        rows[1]['condition'] = copy.deepcopy(rows[0]['condition'])
        with self.assertRaisesRegex(ModelError, 'Identical conditions'):
            self.check()

    def test_module_requires_exact_bindings(self):
        self.rule('deduction.dependent')['execution']['bindings'] = []
        with self.assertRaisesRegex(ModelError, 'Module bindings mismatch'):
            self.check()

    def test_enum_domains_cannot_be_compared_interchangeably(self):
        condition = self.model['decisions'][1]['rows'][0]['condition']
        condition['arguments'][0]['target'] = 'fact:filing.status'
        with self.assertRaisesRegex(ModelError, 'Comparison type mismatch'):
            self.check()

    def test_model_cannot_be_marked_production_ready(self):
        self.model['production_enabled'] = True
        with self.assertRaisesRegex(ModelError, 'Schema error'):
            self.check()

    def test_lookup_requires_the_correct_enum_domain(self):
        expression = self.rule('deduction.standard_base')['execution']['expression']
        expression['keys'][0]['value']['target'] = 'fact:deductions.selected_method'
        with self.assertRaisesRegex(ModelError, 'Lookup key type mismatch'):
            self.check()

    def test_draft_evidence_cannot_support_a_reviewed_rule(self):
        self.model['rules'][0]['status'] = 'reviewed'
        with self.assertRaisesRegex(ModelError, 'Reviewed record needs reviewed interpretation'):
            self.check()


if __name__ == '__main__':
    unittest.main()
