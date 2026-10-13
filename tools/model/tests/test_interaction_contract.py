import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validate_model import ModelError, check_interactions, load, load_interactions
from validate_interactions import resolve_revision, seal


class InteractionContractTests(unittest.TestCase):
    def setUp(self):
        self.model, self.catalog, self.schemas, self.sources = copy.deepcopy(load())
        self.data = copy.deepcopy(load_interactions())

    def check(self, previous=None):
        return check_interactions(self.model, self.catalog, self.schemas, self.sources, self.data, previous)

    def reseal(self, record):
        record['sha256'] = seal(record)

    def test_complete_synthetic_contracts_and_unchanged_history_pass(self):
        result = self.check(copy.deepcopy(self.data))
        self.assertEqual(result['carryover_snapshots'], 2)
        self.assertEqual(result['allocations'], 2)

    def test_historical_context_selects_original_after_correction_exists(self):
        context = self.data['package_snapshots'][0]['context']
        self.assertEqual(resolve_revision(self.data['rule_revisions'], 'rule:income.wages', context)['id'], 'wages.v1')

    def test_correction_boundary_is_half_open(self):
        context = copy.deepcopy(self.data['package_snapshots'][1]['context'])
        context['known_at'] = '2026-03-01T00:00:00Z'
        self.assertEqual(resolve_revision(self.data['rule_revisions'], 'rule:income.wages', context)['id'], 'wages.v2')

    def test_tax_year_end_is_exclusive(self):
        context = copy.deepcopy(self.data['package_snapshots'][1]['context']); context['tax_year'] = 2027
        with self.assertRaisesRegex(ModelError, 'exactly one matching revision'):
            resolve_revision(self.data['rule_revisions'], 'rule:income.wages', context)

    def test_transaction_end_is_exclusive(self):
        context = copy.deepcopy(self.data['package_snapshots'][2]['context']); context['transaction_date'] = '2027-01-01'
        with self.assertRaisesRegex(ModelError, 'exactly one matching revision'):
            resolve_revision(self.data['rule_revisions'], 'rule:income.wages', context)

    def test_missing_transaction_date_does_not_default_to_applicable(self):
        context = copy.deepcopy(self.data['package_snapshots'][0]['context']); context['transaction_date'] = None
        with self.assertRaisesRegex(ModelError, 'Missing transaction date'):
            resolve_revision(self.data['rule_revisions'], 'rule:income.wages', context)

    def test_invalid_effective_interval_is_rejected(self):
        self.data['rule_revisions'][0]['tax_years']['end_exclusive'] = 2025
        with self.assertRaisesRegex(ModelError, 'Invalid effective tax-year interval'):
            self.check()

    def test_publication_cannot_follow_observation(self):
        self.data['rule_revisions'][0]['source_published_at'] = '2025-02-01T00:00:00Z'
        with self.assertRaisesRegex(ModelError, 'publication cannot follow observation'):
            self.check()

    def test_overlapping_revision_fork_is_rejected(self):
        fork = copy.deepcopy(self.data['rule_revisions'][1])
        fork.update(id='wages.fork', version='0.2.0', supersedes=None, change_kind='initial')
        self.data['rule_revisions'].append(fork)
        with self.assertRaisesRegex(ModelError, 'Ambiguous temporal revision overlap'):
            self.check()

    def test_correction_must_close_its_predecessor(self):
        self.data['rule_revisions'][0]['superseded_at'] = '2026-03-02T00:00:00Z'
        with self.assertRaisesRegex(ModelError, 'Correction must close its predecessor'):
            self.check()

    def test_snapshot_corruption_is_detected(self):
        self.data['definition_snapshots'][0]['definition']['label'] = 'Changed'
        with self.assertRaisesRegex(ModelError, 'Definition snapshot hash mismatch'):
            self.check()

    def test_package_cannot_pin_new_rules_into_old_context(self):
        package = self.data['package_snapshots'][0]
        package['rule_pins'][0]['revision_id'] = 'wages.v2'; self.reseal(package)
        with self.assertRaisesRegex(ModelError, 'Pinned revision does not match historical context'):
            self.check()

    def test_pinned_content_hash_is_checked(self):
        package = self.data['package_snapshots'][0]
        package['rule_pins'][0]['definition_sha256'] = '0' * 64; self.reseal(package)
        with self.assertRaisesRegex(ModelError, 'Pinned definition hash mismatch'):
            self.check()

    def test_rehashed_history_cannot_be_rewritten(self):
        previous = copy.deepcopy(self.data)
        snapshot = self.data['definition_snapshots'][0]
        snapshot['definition']['label'] = 'Rewritten history'
        from validate_interactions import digest
        snapshot['sha256'] = digest(snapshot['definition'])
        with self.assertRaisesRegex(ModelError, 'Historical definition_snapshots cannot be changed'):
            self.check(previous)

    def test_archived_package_cannot_be_removed(self):
        previous = copy.deepcopy(self.data); self.data['package_snapshots'].pop()
        with self.assertRaisesRegex(ModelError, 'Historical package_snapshots cannot be changed or removed'):
            self.check(previous)

    def test_overallocation_is_rejected(self):
        allocation = self.data['allocations'][0]
        allocation['outputs'][0]['allocated'] = '80.00'
        with self.assertRaisesRegex(ModelError, 'exceeds shared capacity'):
            self.check()

    def test_allocation_cannot_exceed_individual_demand(self):
        self.data['allocations'][0]['claims'][0]['requested'] = '50.00'
        with self.assertRaisesRegex(ModelError, 'exceeds claimant demand'):
            self.check()

    def test_explicit_allocation_can_leave_capacity_unused(self):
        allocation = self.data['allocations'][0]
        allocation['outputs'][0]['allocated'] = '50.00'
        allocation['outputs'][1]['allocated'] = '25.00'
        allocation['unallocated'] = '25.00'
        self.check()

    def test_zero_capacity_is_valid_when_all_allocations_are_zero(self):
        allocation = self.data['allocations'][1]; allocation['capacity'] = '0.00'
        for output in allocation['outputs']:
            output['allocated'] = '0.00'
        self.check()

    def test_unallocated_balance_must_reconcile(self):
        self.data['allocations'][0]['unallocated'] = '1.00'
        with self.assertRaisesRegex(ModelError, 'Allocation conservation mismatch'):
            self.check()

    def test_duplicate_amount_claim_is_rejected(self):
        limit = self.data['shared_limits'][0]
        limit['claims'][1]['demand_binding'] = copy.deepcopy(limit['claims'][0]['demand_binding'])
        with self.assertRaisesRegex(ModelError, 'duplicates an amount binding'):
            self.check()

    def test_cross_household_claim_is_rejected(self):
        self.data['subjects'].append({'id': 'household:other', 'kind': 'household', 'household_id': None})
        self.data['subjects'][2]['household_id'] = 'household:other'
        with self.assertRaisesRegex(ModelError, 'outside shared-limit owner group'):
            self.check()

    def test_return_limit_cannot_include_unlisted_taxpayer(self):
        self.data['subjects'].append({'id': 'return:alice', 'kind': 'return', 'household_id': 'household:example', 'taxpayer_ids': ['taxpayer:alice']})
        limit = self.data['shared_limits'][0]
        limit['owner_id'] = 'return:alice'; limit['capacity_binding']['subject_id'] = 'return:alice'
        next(f for f in self.model['facts'] if f['id'] == 'design.limit_capacity')['scope'] = 'return'
        with self.assertRaisesRegex(ModelError, 'outside shared-limit owner group'):
            self.check()

    def test_amount_binding_scope_is_checked(self):
        self.data['shared_limits'][0]['capacity_binding']['subject_id'] = 'taxpayer:alice'
        with self.assertRaisesRegex(ModelError, 'subject scope mismatch'):
            self.check()

    def test_proportional_cent_tie_is_deterministic(self):
        outputs = self.data['allocations'][1]['outputs']
        outputs[0]['allocated'], outputs[1]['allocated'] = outputs[1]['allocated'], outputs[0]['allocated']
        with self.assertRaisesRegex(ModelError, 'Proportional allocation/remainder mismatch'):
            self.check()

    def test_zero_weight_sum_is_rejected(self):
        for claim in self.data['allocations'][1]['claims']:
            claim['weight']['numerator'] = '0'
        with self.assertRaisesRegex(ModelError, 'positive sum'):
            self.check()

    def test_negative_allocation_is_rejected_by_schema(self):
        self.data['allocations'][0]['outputs'][0]['allocated'] = '-1.00'
        with self.assertRaisesRegex(ModelError, 'Schema error'):
            self.check()

    def test_carryover_overdraw_is_rejected(self):
        ledger = self.data['carryovers'][0]
        ledger['events'][0]['amount'] = '150.00'; self.reseal(ledger)
        with self.assertRaisesRegex(ModelError, 'overdraws available balance'):
            self.check()

    def test_carryover_years_must_be_contiguous(self):
        ledger = self.data['carryovers'][1]
        ledger['year_balances'].pop(0); self.reseal(ledger)
        with self.assertRaisesRegex(ModelError, 'consecutive years from opening'):
            self.check()

    def test_carryover_character_cannot_change_between_revisions(self):
        ledger = self.data['carryovers'][1]
        ledger['tax_character'] = 'another_character'; self.reseal(ledger)
        with self.assertRaisesRegex(ModelError, 'immutable origin/owner/character'):
            self.check()

    def test_carryover_owner_cannot_change_between_revisions(self):
        ledger = self.data['carryovers'][1]
        ledger['owner_id'] = 'taxpayer:bob'; self.reseal(ledger)
        with self.assertRaisesRegex(ModelError, 'immutable origin/owner/character'):
            self.check()

    def test_carryover_existing_events_cannot_be_rewritten(self):
        ledger = self.data['carryovers'][1]
        ledger['events'][0]['reason'] = 'Changed old event'; self.reseal(ledger)
        with self.assertRaisesRegex(ModelError, 'events cannot be rewritten'):
            self.check()

    def test_use_after_expiration_is_rejected(self):
        ledger = self.data['carryovers'][1]
        ledger['expires_after_tax_year'] = 2025; self.reseal(ledger)
        with self.assertRaisesRegex(ModelError, 'use after expiration'):
            self.check()

    def test_carryover_reported_closing_must_match_events(self):
        ledger = self.data['carryovers'][0]
        ledger['year_balances'][0]['closing'] = '71.00'; self.reseal(ledger)
        with self.assertRaisesRegex(ModelError, 'year reconciliation mismatch'):
            self.check()

    def test_carryover_usage_must_reference_the_same_year_package(self):
        ledger = self.data['carryovers'][0]
        ledger['events'][0]['calculation_package'] = 'year2026.corrected'; self.reseal(ledger)
        with self.assertRaisesRegex(ModelError, 'event/package year mismatch'):
            self.check()

    def test_signed_adjustment_is_reconciled_exactly(self):
        ledger = self.data['carryovers'][0]
        event = copy.deepcopy(ledger['events'][0])
        event.update(id='adjust2025', sequence=2, kind='adjustment', amount='-10.00')
        ledger['events'].append(event)
        ledger['year_balances'][0].update(adjustments='-10.00', closing='60.00')
        self.reseal(ledger); self.data['carryovers'] = [ledger]
        self.check()

    def test_expiration_is_an_explicit_conserving_event(self):
        ledger = self.data['carryovers'][0]; ledger['expires_after_tax_year'] = 2025
        event = copy.deepcopy(ledger['events'][0])
        event.update(id='expire2025', sequence=2, kind='expiration', amount='70.00')
        ledger['events'].append(event)
        ledger['year_balances'][0].update(expired='70.00', closing='0.00')
        self.reseal(ledger); self.data['carryovers'] = [ledger]
        self.check()

    def test_rule_revision_version_cannot_move_backward(self):
        self.data['rule_revisions'][1]['version'] = '0.0.9'
        with self.assertRaisesRegex(ModelError, 'Rule version must increase'):
            self.check()

    def test_multiple_confirmed_allocations_cannot_double_count_a_limit(self):
        first = self.data['allocations'][0]; first['status'] = 'confirmed'
        second = copy.deepcopy(first); second['id'] = 'another.confirmed'
        self.data['allocations'].append(second)
        with self.assertRaisesRegex(ModelError, 'Only one allocation can be confirmed'):
            self.check()

    def test_scenario_inputs_cannot_change_between_alternative_allocations(self):
        self.data['allocations'][1]['scenario_id'] = self.data['allocations'][0]['scenario_id']
        with self.assertRaisesRegex(ModelError, 'must use identical capacity and demands'):
            self.check()

    def test_carryover_lineage_cannot_fork(self):
        fork = copy.deepcopy(self.data['carryovers'][1])
        fork.update(id='synthetic.loss.fork', version='0.2.0', recorded_at='2027-01-11T00:00:00Z')
        self.reseal(fork); self.data['carryovers'].append(fork)
        with self.assertRaisesRegex(ModelError, 'Carryover history cannot fork'):
            self.check()

    def test_duplicate_carryover_origin_cannot_double_count_a_balance(self):
        root = copy.deepcopy(self.data['carryovers'][0])
        root.update(id='synthetic.loss.another_root', version='0.0.9')
        self.reseal(root); self.data['carryovers'].append(root)
        with self.assertRaisesRegex(ModelError, 'exactly one root'):
            self.check()


if __name__ == '__main__':
    unittest.main()
