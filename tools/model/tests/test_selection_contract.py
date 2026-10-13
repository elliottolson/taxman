import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validate_model import ModelError, ROOT, load, validate
from validate_selection import analyze_table, replay_election, route, validate_selection


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'model/selection-model.json').read_text())
        self.schema = json.loads((ROOT / 'schemas/selection-model.schema.json').read_text())
        self.model, self.catalog, self.schemas, self.sources = copy.deepcopy(load())

    def check(self):
        return validate_selection(self.data, self.schema, self.model)

    def reject(self, message):
        with self.assertRaisesRegex(ModelError, message):
            self.check()

    def test_valid_examples_and_explicit_gap(self):
        result = self.check()
        self.assertEqual(result['route_cases'], 10)
        self.assertEqual(result['tables']['design.authorized_method']['blocked_cases'],
                         [{'eligible': False, 'method': 'alternative'}])

    def test_routing_is_independent_of_author_order(self):
        group = self.data['routes'][0]
        for case in self.data['route_cases']:
            expected = route(group, case['facts'])
            reversed_group = copy.deepcopy(group)
            reversed_group['candidates'].reverse()
            self.assertEqual(route(reversed_group, case['facts']), expected)

    def test_exception_requires_explicit_override(self):
        self.data['routes'][0]['candidates'][1]['overrides'] = []
        self.reject('Route expectation mismatch')

    def test_override_cycle_is_rejected(self):
        self.data['routes'][0]['candidates'][0]['overrides'] = ['exception']
        self.reject('Override cycle')

    def test_self_override_is_rejected(self):
        self.data['routes'][0]['candidates'][0]['overrides'] = ['base']
        self.reject('Invalid override')

    def test_unknown_override_target(self):
        self.data['routes'][0]['candidates'][1]['overrides'] = ['absent']
        self.reject('Invalid override')

    def test_unknown_rule_target(self):
        self.data['routes'][0]['candidates'][0]['target'] = 'rule:absent'
        self.reject('Unknown route target')

    def test_out_of_domain_value(self):
        self.data['routes'][0]['candidates'][1]['when']['exception'] = 'true'
        self.reject('outside domain')

    def test_partial_boolean_domain_cannot_claim_proof(self):
        self.data['domains'][0]['values'] = [True]
        self.reject('Boolean domain must be complete')

    def test_duplicate_and_mixed_domain_values(self):
        self.data['domains'][0]['values'] = [False, True, True]
        self.reject('Duplicate domain value')
        self.data['domains'][0]['values'] = [False, 'true']
        self.reject('Mixed domain types')

    def test_unique_table_detects_nonidentical_overlap(self):
        self.data['tables'][0]['rows'][0]['when'] = {}
        self.reject('Overlapping rows')

    def test_complete_table_rejects_gap(self):
        self.data['tables'][1]['coverage'] = 'complete'
        self.reject('Uncovered cases')

    def test_first_table_rejects_shadowed_row(self):
        table = self.data['tables'][0]
        table['hit_policy'] = 'first'
        table['rows'][0]['when'] = {}
        self.reject('Unreachable row')

    def test_first_table_allows_reachable_overlap(self):
        table = self.data['tables'][0]
        table['hit_policy'] = 'first'
        table['rows'][1]['when'] = {}
        self.check()

    def test_finite_analysis_is_bounded(self):
        with self.assertRaisesRegex(ModelError, '4096'):
            analyze_table(self.data['tables'][0], {str(i): [False, True] for i in range(13)})

    def test_core_decisions_are_analyzed(self):
        reports = validate(self.model, self.catalog, self.schemas, self.sources)['decision_analysis']
        self.assertTrue(all(r['status'] == 'analyzed' and not r['blocked_cases'] for r in reports.values()))

    def test_core_nonidentical_overlap(self):
        self.model['decisions'][0]['rows'][0]['condition'] = {'kind':'literal','value_type':'Boolean','value':True}
        with self.assertRaisesRegex(ModelError, 'Overlapping rows'):
            validate(self.model, self.catalog, self.schemas, self.sources)

    def test_core_first_unreachable(self):
        self.model['decisions'][0]['hit_policy'] = 'first'
        self.model['decisions'][0]['rows'][0]['condition'] = {'kind':'literal','value_type':'Boolean','value':True}
        with self.assertRaisesRegex(ModelError, 'Unreachable row'):
            validate(self.model, self.catalog, self.schemas, self.sources)

    def test_numeric_predicate_reports_not_analyzed(self):
        self.model['decisions'][0]['rows'][0]['condition'] = {'kind':'apply','operator':'equal','arguments':[{'kind':'ref','target':'fact:deductions.itemized_total'},{'kind':'literal','value_type':'Money','value':'0.00'}]}
        result = validate(self.model, self.catalog, self.schemas, self.sources)
        self.assertEqual(result['decision_analysis']['deduction.standard_method']['status'], 'not_analyzed')

    def test_missing_election_confirmation_blocks(self):
        self.assertEqual(replay_election(self.data['elections'][0], self.data['election_cases'][1]),
                         {'status':'blocked','reason':'confirmation_required'})

    def test_late_confirmation(self):
        self.data['election_cases'][0]['events'][0]['at'] = '2026-04-16T00:00:00Z'
        self.data['election_cases'][0]['as_of'] = '2026-04-17T00:00:00Z'
        self.reject('confirmation deadline passed')

    def test_exact_deadline_is_inclusive(self):
        case = self.data['election_cases'][0]
        case['events'][0]['at'] = self.data['elections'][0]['confirmation_deadline']
        case['as_of'] = '2026-04-16T00:00:00Z'
        self.check()

    def test_unresolved_and_false_eligibility(self):
        event = self.data['election_cases'][0]['events'][0]
        event['eligibility']['state'] = 'missing'
        self.reject('eligibility unresolved or false')
        event['eligibility']['state'] = 'confirmed'
        event['eligibility']['value'] = False
        self.reject('eligibility unresolved or false')

    def test_wrong_eligibility_fact(self):
        self.data['election_cases'][0]['events'][0]['eligibility']['fact'] = 'exception'
        self.reject('Wrong election eligibility')

    def test_unauthorized_confirmation(self):
        self.data['election_cases'][0]['events'][0]['authorized_by'] = 'other'
        self.reject('owner confirmation')

    def test_different_owner_or_return_context(self):
        self.data['election_cases'][0]['events'][0]['return_id'] = 'other'
        self.reject('context mismatch')

    def test_unknown_revision(self):
        self.data['election_cases'][0]['events'][0]['return_revision'] = 'absent'
        self.reject('Unknown return revision')

    def test_duplicate_confirmation_does_not_replace_choice(self):
        case = self.data['election_cases'][0]
        event = copy.deepcopy(case['events'][0]); event['id'] = 'confirm-2'
        case['events'].append(event)
        self.reject('Revoke an active choice')

    def test_future_event_and_reversed_chronology(self):
        case = self.data['election_cases'][3]
        case['events'][1]['at'] = '2027-01-01T00:00:00Z'
        self.reject('chronology')
        case['events'][1]['at'] = '2026-03-01T00:00:00Z'
        self.reject('chronology')

    def test_revocation_must_reference_active_event(self):
        self.data['election_cases'][3]['events'][1]['confirmation_id'] = 'absent'
        self.reject('reference active confirmation')

    def test_revocation_cannot_cross_revision(self):
        self.data['election_cases'][3]['events'][1]['return_revision'] = 'revision-2'
        self.reject('Revocation revision mismatch')

    def test_irrevocable_election(self):
        self.data['elections'][0]['revocation_allowed'] = False
        self.reject('cannot be revoked')

    def test_revocation_deadline(self):
        case = self.data['election_cases'][3]
        case['events'][1]['at'] = '2026-05-16T00:00:00Z'
        case['as_of'] = '2026-05-17T00:00:00Z'
        self.reject('revocation deadline passed')

    def test_reconfirmation_on_new_revision_requires_revocation(self):
        case = self.data['election_cases'][3]
        event = copy.deepcopy(case['events'][0]); event.update(id='confirm-2', at='2026-04-03T12:00:00Z', return_revision='revision-2',choice='base')
        case['events'].append(event); case['current_return_revision'] = 'revision-2'
        case['expected'] = {'status':'confirmed','choice':'base','confirmation_id':'confirm-2','effects':[{'target':'rule:deduction.standard_base','start_year':2025,'end_year_exclusive':2027}]}
        candidate = self.data['routes'][0]['candidates'][0]
        self.data['selection_cases'][3]['expected'] = {'status':'selected','candidate':'base','target':candidate['target'],'explanation':candidate['explanation'],'suppressed':[]}
        self.check()

    def test_effects_are_explicit_and_cross_year(self):
        result = replay_election(self.data['elections'][0], self.data['election_cases'][0])
        self.assertEqual(result['effects'], [{'target':'rule:deduction.standard','start_year':2025,'end_year_exclusive':2027}])

    def test_authorized_routing_blocks_unconfirmed_and_stale_choices(self):
        self.assertEqual(self.check()['selection_cases'], 4)

    def test_ordinary_fact_cannot_bypass_election_confirmation(self):
        self.data['selection_cases'][0]['facts']['alternative'] = {'state':'confirmed','value':True}
        self.reject('cannot be supplied as an ordinary fact')

    def test_election_binding_must_cover_all_choices(self):
        del self.data['routes'][0]['election_binding']['choice_values']['base']
        self.reject('binding choices mismatch')

    def test_election_binding_must_use_declared_domain(self):
        self.data['routes'][0]['election_binding']['choice_values']['base'] = 'base'
        self.reject('outside domain')

    def test_policy_cannot_be_reused_for_another_year(self):
        self.data['election_cases'][0]['tax_year'] = 2026
        self.reject('policy year mismatch')

    def test_route_output_type_mismatch(self):
        self.data['routes'][0]['candidates'][0]['target'] = 'fact:income.documents_complete'
        self.reject('Route target type/scope mismatch')

    def test_table_output_type_mismatch(self):
        self.data['tables'][0]['rows'][0]['target'] = 'fact:income.documents_complete'
        self.reject('Table target type/scope mismatch')

    def test_route_analysis_surfaces_conflicting_combinations(self):
        report = self.check()['routes']['design.method']
        self.assertEqual(report['cases'], 4)
        self.assertEqual(report['blocked_cases'][0]['inputs'], {'alternative':True, 'exception':True})
        self.assertEqual(report['blocked_cases'][0]['result']['reason'], 'conflicting_methods')

    def test_schema_rejects_unknown_fields_and_production(self):
        self.data['production_enabled'] = True
        self.reject('Schema error')
        self.data['production_enabled'] = False
        self.data['elections'][0]['implicit_best_tax_choice'] = True
        self.reject('Schema error')


if __name__ == '__main__':
    unittest.main()
