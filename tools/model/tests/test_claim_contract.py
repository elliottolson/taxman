import copy
from datetime import timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validate_model import ModelError, ROOT, load
from validate_claims import read_ledger, validate_claims, replay_reviews, package_preflight, preserve_archives
from validate_interactions import digest, seal, instant


class ClaimContractTests(unittest.TestCase):
    def setUp(self):
        self.data = copy.deepcopy(read_ledger(ROOT))
        self.schema = json.loads((ROOT / 'schemas/claim-ledger.schema.json').read_text())
        self.model, _, _, self.registry = copy.deepcopy(load())
        self.time = max(instant(s['retrieved_at']) for s in self.data['sources'])
        self.time = max(self.time, *(instant(c['recorded_at']) for c in self.data['claims']))

    def check(self, previous=None, root=ROOT):
        return validate_claims(self.data, self.schema, self.model, self.registry, root, previous)

    def reject(self, pattern):
        with self.assertRaisesRegex(ModelError, pattern):
            self.check()

    def repin(self):
        sources = {s['id']: s for s in self.data['sources']}
        for s in sources.values():
            s['sha256'] = seal(s)
        for c in self.data['claims']:
            for e in c['evidence']:
                e['source_sha256'] = sources[e['source_id']]['sha256']
            c['sha256'] = seal(c)
        claims = {c['id']: c for c in self.data['claims']}
        for f in self.data['fixtures']:
            f['claim_sha256'] = claims[f['claim_id']]['sha256']
            for e in f['evidence']:
                e['source_sha256'] = sources[e['source_id']]['sha256']
            f['sha256'] = seal(f)

    def event(self, kind, record, action, actor=None, successor=None):
        self.time += timedelta(seconds=1)
        e = {'id':'test-event-'+str(len(self.data['reviews'])),'subject_kind':kind,'subject_id':record['id'],
             'subject_sha256':record['sha256'],'action':action,'actor_id':actor or ('test.reviewer' if action in {'approve','dispute'} else record['author_id']),
             'at':self.time.strftime('%Y-%m-%dT%H:%M:%SZ'),'reason':'Synthetic review transition test.','successor_id':successor}
        self.data['reviews'].append(e)
        self.data['packages'][0]['known_at'] = e['at']
        return e

    def enable_reviewer(self):
        self.data['reviewers'] = [{'id':'test.reviewer','qualification':'Synthetic test identity, not an actual reviewer.','enabled':True}]

    def review_sources(self):
        self.enable_reviewer()
        for s in self.data['sources']:
            self.event('source', s, 'submit')
            self.event('source', s, 'approve')

    def review_claim(self, index=0):
        c = self.data['claims'][index]
        c['open_questions'] = []
        self.repin()
        self.event('claim', c, 'submit')
        self.event('claim', c, 'approve')
        return c

    def test_real_drafts_validate_and_cannot_release(self):
        r = self.check()
        self.assertEqual((r['sources'], r['claims'], r['fixtures']), (5,7,109))
        self.assertFalse(r['packages']['research.2025']['release_eligible'])
        self.assertTrue(all(s == 'drafted' for s in r['review_states'].values()))

    def test_published_reference_values_are_preserved(self):
        f = {f['id']:f for f in self.data['fixtures']}
        self.assertEqual(f['base.published.mfj']['expected']['data']['value'],'31500.00')
        self.assertEqual(f['dependent.published.floor']['expected']['data']['value'],'1350.00')
        self.assertEqual(f['base.published.mfj']['oracle']['method'],'irs_published_example')
        self.assertEqual(f['dependent.published.floor']['evidence'][0]['pdf_page'],24)

    def test_threshold_nontrigger_never_asserts_no_schedule_b(self):
        cases = [f for f in self.data['fixtures'] if f['id'] in {'schedule-b.interest-equal','schedule-b.combined-not-trigger'}]
        self.assertEqual(len(cases),2)
        self.assertTrue(all(f['expected']['status']=='undetermined' for f in cases))

    def test_release_candidate_rejects_unapproved_rules(self):
        self.data['packages'][0]['stage']='release_candidate'
        self.reject('Release candidate blocked')

    def test_production_cannot_be_enabled(self):
        self.data['production_enabled']=True
        self.reject('Schema error')

    def test_claim_tamper(self):
        self.data['claims'][0]['statement']='Changed without sealing.'
        self.reject('Content digest mismatch')

    def test_fixture_tamper(self):
        self.data['fixtures'][0]['expected']['data']['value']='1.00'
        self.reject('Content digest mismatch')

    def test_missing_source_pin(self):
        self.data['claims'][0]['evidence'][0]['source_sha256']='0'*64
        self.data['claims'][0]['sha256']=seal(self.data['claims'][0])
        self.reject('Evidence source pin mismatch')

    def test_source_bytes_mismatch(self):
        self.data['sources'][0]['content_sha256']='0'*64
        self.repin()
        self.reject('Source bytes digest mismatch')

    def test_source_missing_or_html(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for source in self.data['sources']:
                path=root/source['path'];path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'<html>not a PDF</html>')
            with self.assertRaisesRegex(ModelError,'not a PDF'):
                self.check(root=root)

    def test_path_traversal_rejected(self):
        self.data['sources'][0]['path']='../../private.pdf'
        self.repin()
        self.reject('Schema error')

    def test_unknown_registry(self):
        self.data['sources'][0]['registry_id']='absent'
        self.repin()
        self.reject('Unknown source registry')

    def test_wrong_authority(self):
        self.data['sources'][0]['authority_class']='statute'
        self.repin()
        self.reject('Source authority mismatch')

    def test_year_and_page_pins(self):
        self.data['claims'][0]['evidence'][0]['pdf_page']=32
        self.repin()
        self.reject('page outside source')
        self.data['claims'][0]['evidence'][0]['pdf_page']=25
        self.data['claims'][0]['applicability']['end_exclusive']=2027
        self.repin()
        self.reject('Evidence year mismatch')

    def test_supporting_evidence_required(self):
        for e in self.data['claims'][0]['evidence']:e['relationship']='limits'
        self.repin()
        self.reject('Supporting evidence required')

    def test_unknown_consumer(self):
        self.data['claims'][0]['consumers'][0]['target']='rule:absent'
        self.repin()
        self.reject('Unknown claim consumer')

    def test_changed_consumer_invalidates_preflight(self):
        self.model['rules'][5]['label']='Changed interpretation'
        r=self.check()
        self.assertIn('stale_consumer:rule:deduction.standard_base',r['packages']['research.2025']['blockers'])

    def test_fixture_year_outside_claim(self):
        self.data['fixtures'][0]['tax_year']=2026
        self.repin()
        self.reject('Fixture year outside claim')

    def test_fixture_claim_pin_mismatch(self):
        self.data['fixtures'][0]['claim_sha256']='0'*64
        self.data['fixtures'][0]['sha256']=seal(self.data['fixtures'][0])
        self.reject('Fixture claim pin mismatch')

    def test_unknown_fact_is_not_zero(self):
        f=next(f for f in self.data['fixtures'] if f['id']=='dependent.missing-earned')
        f['inputs']['earned_income']['data']={'type':'Money','value':'0.00'}
        self.repin()
        self.reject('Unusable fact must omit value')

    def test_reference_cannot_claim_candidate_generated_expectations(self):
        self.data['fixtures'][0]['oracle']['independent_of_candidate_execution']=False
        self.repin()
        self.reject('Schema error')

    def test_valid_review_path(self):
        self.review_sources()
        c=self.review_claim()
        f=self.data['fixtures'][0]
        self.event('fixture',f,'submit');self.event('fixture',f,'approve')
        r=self.check()
        self.assertEqual(r['review_states']['claim:'+c['id']],'reviewed')
        self.assertEqual(r['review_states']['fixture:'+f['id']],'reviewed')
        self.assertFalse(r['packages']['research.2025']['release_eligible'])

    def test_self_approval(self):
        self.enable_reviewer()
        s=self.data['sources'][0]
        self.data['reviewers'][0]['id']=s['author_id']
        self.event('source',s,'submit')
        self.event('source',s,'approve',actor=s['author_id'])
        self.reject('Independent reviewer required')

    def test_unregistered_or_disabled_reviewer(self):
        s=self.data['sources'][0]
        self.event('source',s,'submit');self.event('source',s,'approve')
        self.reject('Reviewer is not enabled')
        self.enable_reviewer();self.data['reviewers'][0]['enabled']=False
        self.reject('Reviewer is not enabled')

    def test_open_questions_block_approval(self):
        self.review_sources()
        c=self.data['claims'][0]
        self.event('claim',c,'submit');self.event('claim',c,'approve')
        self.reject('Open claim questions')

    def test_source_review_required_before_claim(self):
        self.enable_reviewer();self.review_claim()
        self.reject('Evidence sources must be reviewed')

    def test_disagreement_blocks_approval(self):
        self.review_sources()
        c=self.data['claims'][0];c['open_questions']=[];c['evidence'][1]['relationship']='disagrees';self.repin()
        self.event('claim',c,'submit');self.event('claim',c,'approve')
        self.reject('Conflicting evidence')

    def test_approval_requires_submission(self):
        self.enable_reviewer();self.event('source',self.data['sources'][0],'approve')
        self.reject('Approval requires submitted')

    def test_dispute_invalidates_package_without_changing_history(self):
        self.review_sources();c=self.review_claim()
        approved_at=self.data['packages'][0]['known_at']
        self.event('claim',c,'dispute')
        r=self.check()
        self.assertEqual(r['review_states']['claim:'+c['id']],'disputed')
        self.assertIn('claim_not_reviewed:'+c['id'],r['packages']['research.2025']['blockers'])
        self.assertEqual(replay_reviews(self.data,approved_at)[('claim',c['id'])],'reviewed')

    def test_disputed_content_cannot_be_reapproved(self):
        self.review_sources();c=self.review_claim();self.event('claim',c,'dispute');self.event('claim',c,'approve')
        self.reject('Approval requires submitted')

    def test_source_dispute_blocks_approved_claim_package(self):
        self.review_sources();self.review_claim()
        self.event('source',self.data['sources'][0],'dispute')
        r=self.check()
        self.assertIn('source_not_reviewed:p501-2025-snapshot',r['packages']['research.2025']['blockers'])

    def test_review_hash_binding(self):
        self.event('source',self.data['sources'][0],'submit')['subject_sha256']='0'*64
        self.reject('Review content hash mismatch')

    def test_review_order_is_not_a_future_dependency(self):
        self.review_sources()
        self.data['reviews'].reverse()
        self.reject('Approval requires submitted|Review log must be chronological')

    def test_archives_preserved_even_after_resealing(self):
        previous=copy.deepcopy(self.data)
        self.data['claims'][0]['statement']='New interpretation';self.repin()
        with self.assertRaisesRegex(ModelError,'Archived claims record changed'):
            self.check(previous)

    def test_removed_archive_rejected(self):
        previous=copy.deepcopy(self.data)
        self.data['fixtures'].pop()
        with self.assertRaisesRegex(ModelError,'Archived fixtures record changed or removed'):
            preserve_archives(self.data,previous)

    def test_review_prefix_cannot_be_rewritten(self):
        self.review_sources();previous=copy.deepcopy(self.data)
        self.data['reviews'][0]['reason']='New reason'
        with self.assertRaisesRegex(ModelError,'Archived review log must remain a prefix'):
            preserve_archives(self.data,previous)

    def test_duplicate_ids(self):
        self.data['claims'].append(copy.deepcopy(self.data['claims'][0]))
        self.reject('Duplicate claim ID')

    def test_package_missing_cases_and_wrong_year_report(self):
        p=self.data['packages'][0];p['fixture_ids']=[self.data['fixtures'][0]['id']];p['tax_year']=2026
        report=self.check()['packages'][p['id']]
        self.assertIn('missing_reference_cases:standard.dependent.2025.v1',report['blockers'])
        self.assertIn('claim_year_mismatch:standard.base.2025.v1',report['blockers'])

    def test_revised_claim_requires_explicit_supersession(self):
        c=copy.deepcopy(self.data['claims'][0]);self.time+=timedelta(seconds=1)
        c.update(id=c['logical_id']+'.v2',version=2,previous_id=self.data['claims'][0]['id'],recorded_at=self.time.strftime('%Y-%m-%dT%H:%M:%SZ'))
        c['sha256']=seal(c);self.data['claims'].append(c)
        self.reject('Predecessor must be explicitly superseded')
        self.event('claim',self.data['claims'][0],'supersede',successor=c['id'])
        self.check()

    def test_superseded_claim_cannot_be_revived(self):
        old=self.data['claims'][0];c=copy.deepcopy(old);self.time+=timedelta(seconds=1)
        c.update(id=c['logical_id']+'.v2',version=2,previous_id=old['id'],recorded_at=self.time.strftime('%Y-%m-%dT%H:%M:%SZ'));c['sha256']=seal(c)
        self.data['claims'].append(c);self.event('claim',old,'supersede',successor=c['id']);self.event('claim',old,'submit')
        self.reject('Superseded subject cannot be revived')


if __name__=='__main__':
    unittest.main()
