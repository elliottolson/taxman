"""Validate evidence/interpretation contracts and release preflight, not tax law."""
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import subprocess

from validate_model import check_schema, require
from validate_interactions import digest, seal, instant, index


def read_ledger(root):
    return json.loads((root / 'model/claim-ledger.json').read_text())


def previous_ledger(root, ref):
    require(re.fullmatch(r'HEAD\^?|[a-f0-9]{40}', ref) is not None, 'Unsupported baseline Git reference')
    listing = subprocess.run(['git', '-C', str(root), 'ls-tree', '--name-only', ref, '--', 'model/claim-ledger.json'], capture_output=True, text=True)
    require(listing.returncode == 0, 'Cannot inspect claim baseline')
    if not listing.stdout.strip():
        return None  # First migration from a commit predating the ledger.
    blob = subprocess.run(['git', '-C', str(root), 'show', '--no-ext-diff', f'{ref}:model/claim-ledger.json'], capture_output=True, text=True)
    require(blob.returncode == 0, 'Cannot read claim baseline')
    return json.loads(blob.stdout)


def preserve_archives(data, previous):
    if previous is None:
        return
    require(data['reviews'][:len(previous['reviews'])] == previous['reviews'], 'Archived review log must remain a prefix')
    for section in ['sources', 'claims', 'fixtures', 'reviews']:
        current = index(data[section], section)
        for record in previous[section]:
            require(record['id'] in current and current[record['id']] == record,
                    f'Archived {section} record changed or removed: {record["id"]}')


def replay_reviews(data, as_of=None):
    subjects = {(kind, r['id']): r for kind, section in
                [('source', 'sources'), ('claim', 'claims'), ('fixture', 'fixtures')] for r in data[section]}
    reviewers = {r['id']: r for r in data['reviewers']}
    states = {key: 'drafted' for key in subjects}
    last_time = {}
    log_time = None
    for event in data['reviews']:
        key = event['subject_kind'], event['subject_id']
        require(key in subjects, 'Unknown review subject')
        subject = subjects[key]
        require(event['subject_sha256'] == subject['sha256'], 'Review content hash mismatch')
        time = instant(event['at'])
        require(log_time is None or time >= log_time, 'Review log must be chronological')
        log_time = time
        recorded = instant(subject.get('recorded_at', subject.get('retrieved_at')))
        require(time >= recorded and time >= last_time.get(key, recorded), 'Review chronology mismatch')
        last_time[key] = time
        # Validate all events in full replay; historical replay uses the same valid log.
        if as_of is not None and time > instant(as_of):
            continue
        action, state = event['action'], states[key]
        require(state != 'superseded', 'Superseded subject cannot be revived')
        if action == 'submit':
            require(state == 'drafted' and event['actor_id'] == subject['author_id'], 'Invalid review submission')
            states[key] = 'in_review'
        elif action in {'approve', 'dispute'}:
            reviewer = reviewers.get(event['actor_id'])
            require(reviewer is not None and reviewer['enabled'], 'Reviewer is not enabled')
            authors = {subject['author_id']}
            if key[0] == 'fixture':
                authors.add(subjects[('claim', subject['claim_id'])]['author_id'])
            require(event['actor_id'] not in authors, 'Independent reviewer required')
            if action == 'approve':
                require(state == 'in_review', 'Approval requires submitted undisputed content')
                if key[0] == 'claim':
                    require(not subject['open_questions'], 'Open claim questions block approval')
                    require(not any(e['relationship'] == 'disagrees' for e in subject['evidence']), 'Conflicting evidence blocks approval')
                    require(all(states[('source', e['source_id'])] == 'reviewed' for e in subject['evidence']), 'Evidence sources must be reviewed before claim approval')
                if key[0] == 'fixture':
                    require(states[('claim', subject['claim_id'])] == 'reviewed', 'Claim must be reviewed before fixture approval')
                    require(all(states[('source', e['source_id'])] == 'reviewed' for e in subject['evidence']), 'Fixture sources must be reviewed before approval')
                states[key] = 'reviewed'
            else:
                require(state in {'drafted', 'in_review', 'reviewed'}, 'Invalid dispute transition')
                states[key] = 'disputed'
        else:
            require(key[0] == 'claim' and event['actor_id'] == subject['author_id'], 'Only the author can supersede a claim')
            successor = subjects.get(('claim', event['successor_id']))
            require(successor is not None and successor['previous_id'] == subject['id'], 'Supersession needs linked successor')
            require(instant(successor['recorded_at']) <= time, 'Successor not yet recorded')
            states[key] = 'superseded'
        require((action == 'supersede') == (event['successor_id'] is not None), 'Unexpected review successor')
    return states


def package_preflight(package, data, model):
    """Necessary gates only. Full executable closure and verification are future work."""
    claims = index(data['claims'], 'claim')
    fixtures = index(data['fixtures'], 'fixture')
    sources = index(data['sources'], 'source')
    states = replay_reviews(data, package['known_at'])
    targets = {f'{kind}:{r["id"]}': r for kind, section in
               [('rule', 'rules'), ('parameter', 'parameters'), ('decision', 'decisions'), ('module', 'modules')]
               for r in model[section]}
    blockers = set()
    for id in package['claim_ids']:
        c = claims[id]
        if instant(c['recorded_at']) > instant(package['known_at']):
            blockers.add('claim_not_yet_recorded:' + id)
        if not c['applicability']['start'] <= package['tax_year'] < c['applicability']['end_exclusive']:
            blockers.add('claim_year_mismatch:' + id)
        if states[('claim', id)] != 'reviewed':
            blockers.add('claim_not_reviewed:' + id)
        for e in c['evidence']:
            source = sources[e['source_id']]
            if states[('source', source['id'])] != 'reviewed':
                blockers.add('source_not_reviewed:' + source['id'])
        cases = [fixtures[f] for f in package['fixture_ids'] if fixtures[f]['claim_id'] == id]
        if not cases:
            blockers.add('missing_reference_cases:' + id)
        for consumer in c['consumers']:
            target = targets[consumer['target']]
            if consumer['target_sha256'] != digest(target):
                blockers.add('stale_consumer:' + consumer['target'])
            if target['status'] != 'reviewed':
                blockers.add('consumer_not_reviewed:' + consumer['target'])
            if consumer['target'].startswith('parameter:') and target['value_status'] == 'unpopulated':
                blockers.add('parameter_unpopulated:' + consumer['target'])
            if consumer['target'].startswith('module:') and target['implementation_status'] == 'interface_only':
                blockers.add('module_unimplemented:' + consumer['target'])
    for id in package['fixture_ids']:
        f = fixtures[id]
        if f['claim_id'] not in package['claim_ids']:
            blockers.add('fixture_claim_outside_package:' + id)
        if f['tax_year'] != package['tax_year']:
            blockers.add('fixture_year_mismatch:' + id)
        if instant(f['recorded_at']) > instant(package['known_at']):
            blockers.add('fixture_not_yet_recorded:' + id)
        if states[('fixture', id)] != 'reviewed':
            blockers.add('fixture_not_reviewed:' + id)
        for e in f['evidence']:
            if states[('source', e['source_id'])] != 'reviewed':
                blockers.add('source_not_reviewed:' + e['source_id'])
    # There is intentionally no shortcut from reviewed prose to a released engine.
    blockers.add('execution_verification_not_implemented')
    blockers.add('compiled_dependency_coverage_not_implemented')
    return {'release_eligible': False, 'blockers': sorted(blockers)}


def validate_claims(data, schema, model, registry, root, previous=None):
    check_schema(data, schema)
    sources = index(data['sources'], 'source')
    claims = index(data['claims'], 'claim')
    fixtures = index(data['fixtures'], 'fixture')
    index(data['reviews'], 'review')
    index(data['reviewers'], 'reviewer')
    index(data['packages'], 'package')
    registry_sources = index(registry['sources'], 'registry source')
    targets = {f'{kind}:{r["id"]}' for kind, section in
               [('rule', 'rules'), ('parameter', 'parameters'), ('decision', 'decisions'), ('module', 'modules')]
               for r in model[section]}
    for section in ['sources', 'claims', 'fixtures']:
        for r in data[section]:
            require(seal(r) == r['sha256'], f'Content digest mismatch: {r["id"]}')
    paths = set()
    for source in sources.values():
        require(source['registry_id'] in registry_sources, 'Unknown source registry reference')
        candidate = registry_sources[source['registry_id']]
        require(source['authority_class'] == candidate['authority_class'], 'Source authority mismatch')
        require(set(source['tax_years']) <= set(candidate['candidate_tax_years']), 'Source year outside registry candidates')
        require(len(source['tax_years']) == len(set(source['tax_years'])), 'Duplicate source tax year')
        require(source['url'].startswith('https://www.irs.gov/pub/irs-prior/'), 'Source URL must be an IRS year archive')
        require(date.fromisoformat(source['published_on']) <= instant(source['retrieved_at']).date(), 'Source publication after retrieval')
        path = (root / source['path']).resolve()
        require(path.is_relative_to((root / 'evidence/irs').resolve()), 'Source path escapes evidence directory')
        require(source['path'] not in paths, 'Duplicate evidence path')
        paths.add(source['path'])
        raw = path.read_bytes()
        require(raw.startswith(b'%PDF-'), 'Evidence is not a PDF')
        require(hashlib.sha256(raw).hexdigest() == source['content_sha256'], 'Source bytes digest mismatch')
    def evidence(records, start, end, recorded):
        require(any(e['relationship'] == 'supports' for e in records), 'Supporting evidence required')
        for e in records:
            require(e['source_id'] in sources, 'Unknown evidence source')
            source = sources[e['source_id']]
            require(e['source_sha256'] == source['sha256'], 'Evidence source pin mismatch')
            require(e['pdf_page'] <= source['pdf_pages'], 'Evidence page outside source')
            require(set(range(start, end)) <= set(source['tax_years']), 'Evidence year mismatch')
            require(instant(recorded) >= instant(source['retrieved_at']), 'Evidence not yet retrieved')
    successors, roots = {}, set()
    for c in claims.values():
        years = c['applicability']
        require(years['start'] < years['end_exclusive'], 'Empty claim applicability')
        evidence(c['evidence'], years['start'], years['end_exclusive'], c['recorded_at'])
        require(len({(x['target'], x['facet']) for x in c['consumers']}) == len(c['consumers']), 'Duplicate claim consumer')
        require(all(x['target'] in targets for x in c['consumers']), 'Unknown claim consumer')
        # Consumer pins may refer to an older version: report staleness at preflight.
        if c['previous_id'] is None:
            require(c['version'] == 1 and c['logical_id'] not in roots, 'Invalid claim lineage root')
            roots.add(c['logical_id'])
        else:
            require(c['previous_id'] in claims, 'Unknown predecessor claim')
            old = claims[c['previous_id']]
            require(old['logical_id'] == c['logical_id'] and old['version'] + 1 == c['version'], 'Claim lineage mismatch')
            require(instant(old['recorded_at']) < instant(c['recorded_at']), 'Claim revision chronology')
            require(c['previous_id'] not in successors, 'Forked claim revisions')
            successors[c['previous_id']] = c['id']
    for f in fixtures.values():
        require(f['claim_id'] in claims, 'Unknown fixture claim')
        c = claims[f['claim_id']]
        require(f['claim_sha256'] == c['sha256'], 'Fixture claim pin mismatch')
        require(c['applicability']['start'] <= f['tax_year'] < c['applicability']['end_exclusive'], 'Fixture year outside claim')
        require(instant(f['recorded_at']) >= instant(c['recorded_at']), 'Fixture precedes claim')
        evidence(f['evidence'], f['tax_year'], f['tax_year'] + 1, f['recorded_at'])
        require(f['oracle']['method'] != 'irs_published_example' or f['kind'] == 'published_example', 'Published oracle requires published example')
        require(f['kind'] != 'published_example' or f['oracle']['method'] == 'irs_published_example', 'Published example requires IRS oracle')
        require(f['oracle']['method'] != 'product_unknown_policy' or f['expected']['status'] == 'blocked', 'Unknown policy must block')
        for fact in f['inputs'].values():
            require(fact['state'] not in {'missing', 'invalid', 'not_applicable'} or fact['data'] is None, 'Unusable fact must omit value')
            require(fact['state'] != 'confirmed' or fact['data'] is not None, 'Confirmed fact needs value')
    states = replay_reviews(data)
    for c in claims.values():
        if c['previous_id']:
            require(states[('claim', c['previous_id'])] == 'superseded', 'Predecessor must be explicitly superseded')
    reports = {}
    for package in data['packages']:
        require(len(set(package['claim_ids'])) == len(package['claim_ids']) and set(package['claim_ids']) <= set(claims), 'Invalid package claims')
        require(len(set(package['fixture_ids'])) == len(package['fixture_ids']) and set(package['fixture_ids']) <= set(fixtures), 'Invalid package fixtures')
        require(len({claims[c]['logical_id'] for c in package['claim_ids']}) == len(package['claim_ids']), 'Package selects competing claim revisions')
        report = package_preflight(package, data, model)
        reports[package['id']] = report
        require(package['stage'] != 'release_candidate' or report['release_eligible'], 'Release candidate blocked: ' + ', '.join(report['blockers']))
    preserve_archives(data, previous)
    return {'sources': len(sources), 'claims': len(claims), 'fixtures': len(fixtures),
            'review_states': {f'{kind}:{id}': state for (kind, id), state in states.items()}, 'packages': reports}
