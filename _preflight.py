#!/usr/bin/env python3
"""Recheck dated source evidence; no network needed to reproduce assertions."""
from pathlib import Path
import json, hashlib, datetime, xml.etree.ElementTree as ET, collections
W = Path(__file__).resolve().parent
S = W / 'sources'
meta = json.loads((W / 'meta.json').read_text())
decisive = meta['decisive_date']
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
manifest_path = S / 'preflight-20261020-manifest.xml'
xml_path = S / 'preflight-20261020-current.xml'
wti_path = S / 'preflight-20261020-wti.xml'
m = ET.parse(manifest_path).getroot()
r = ET.parse(xml_path).getroot()
wti = ET.parse(wti_path).getroot()
assert m.tag == 'work' and m.get('label') == 'BWBR0001854'
assert r.tag == 'toestand' and r.get('bwb-id') == 'BWBR0001854'
assert wti.tag == 'wetstechnische-informatie' and wti.get('bwb-id') == 'BWBR0001854'
expressions = []
for e in m.findall('expression'):
    expressions.append({'label': e.get('label'),
                        'effective_from': e.findtext('metadata/datum_inwerkingtreding'),
                        'effective_to': e.findtext('metadata/einddatum'),
                        'visible_from': e.findtext('metadata/zichtdatum_start'),
                        'visible_to': e.findtext('metadata/zichtdatum_eind')})
selected = [e for e in expressions if e['effective_from'] <= decisive <= e['effective_to'] and
            e['visible_from'] <= decisive <= e['visible_to']]
assert len(selected) == 1 and selected[0]['label'] == meta['effective_version']
chosen = m.find("expression[@label='" + meta['effective_version'] + "']")
sha512 = chosen.findtext("manifestation[@label='xml']/metadata/hashcode")
assert hashlib.sha512(xml_path.read_bytes()).hexdigest() == sha512
assert xml_path.read_bytes() == (S / 'intake-version.xml').read_bytes()
assert r.get('inwerkingtreding') == selected[0]['effective_from']
assert m.get('_latestItem').startswith(meta['effective_version'] + '/')
changes = []
for e in wti.findall('wijzigingen/regeling/datum'):
    date = e.get('waarde')
    changes.append({'commencement_date': date, 'disposition': 'undated_or_pending' if not date else
                    'future_excluded' if date > decisive else 'effective_on_or_before_decisive_date',
                    'details': [{'kind': a.findtext('betreft'),
                                 'sources': [{'type': b.get('type'), 'year': b.findtext('bekendmaking/publicatiejaar'),
                                              'number': b.findtext('bekendmaking/publicatienummer'), 'dossier': b.findtext('dossiernummer')}
                                             for b in a.findall('ontstaansbron/bron')]}
                                for a in e.findall('details')]})
effective = sorted(c['commencement_date'] for c in changes if c['commencement_date'] and c['commencement_date'] <= decisive)
assert effective[-1] == selected[0]['effective_from']
coverage = json.loads((W / 'coverage-evidence.json').read_text())
assert coverage['ok']
# Manifest metadata inventories historical states without merging their article bodies.
version = {'manifest': {'path': str(manifest_path.relative_to(W)), 'sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                        'generated': m.get('gegenereerd'), 'latest_item': m.get('_latestItem'),
                        'expressions_checked': expressions, 'selected': selected[0]},
           'wti': {'path': str(wti_path.relative_to(W)), 'sha256': hashlib.sha256(wti_path.read_bytes()).hexdigest(),
                   'root': wti.tag, 'generated': wti.find('wijzigingen').get('gegenereerd'),
                   'latest_effective_change': effective[-1],
                   'changes_after_intake_date': [c for c in changes if c['commencement_date'] and '2026-10-01' < c['commencement_date'] <= decisive],
                   'future_and_undated_changes': [c for c in changes if c['disposition'] != 'effective_on_or_before_decisive_date']},
           'statutory_xml': {'path': str(xml_path.relative_to(W)), 'sha256': hashlib.sha256(xml_path.read_bytes()).hexdigest(),
                             'manifest_sha512': sha512, 'sha512_matches': True, 'identical_to_preserved_canonical_raw_source': True},
           'selection_reason': 'Effective and visibility intervals in official manifest contain the original authoring date; fresh WTI independently lists latest commenced code change as 2026-07-01. Retrieval timestamp and consolidated label are not used as proof of effectiveness.'}
(S / 'preflight-version-evidence.json').write_text(json.dumps(version, ensure_ascii=False, indent=2) + '\n')
fetches = json.loads((S / 'preflight-20261020-fetch-log.json').read_text())
# The official WTI root is named wetstechnische-informatie, not wti.
for c in fetches:
    if c.get('path') == 'sources/preflight-20261020-wti.xml':
        c['expected_format'] = 'wetstechnische-informatie'
        c['expected_format_valid'] = True
        c['validation'] = 'Parsed official wetstechnische-informatie XML, bwb-id BWBR0001854; current and prospective changes separately inventoried.'
(S / 'preflight-20261020-fetch-log.json').write_text(json.dumps(fetches, ensure_ascii=False, indent=2) + '\n')
v = json.loads((S / 'verification.json').read_text())
for i, c in enumerate(v['checks']):
    matching = next((f for f in fetches if f['url'] == c['url'] and f['accessed_at'] == c['accessed_at']), None)
    if matching:
        v['checks'][i] = matching
v['preflight_rechecked_at'] = now
v['tool_availability'] = {'checked_at': fetches[0]['accessed_at'], 'firecrawl': {'installed': True, 'authenticated': True, 'available_credits': 0, 'action': 'No scrape initiated; direct official XML used.'}}
v['preflight_version_evidence'] = 'sources/preflight-version-evidence.json'
v['version_evidence'] = list(dict.fromkeys(v['version_evidence'] + ['sources/preflight-20261020-manifest.xml', 'sources/preflight-20261020-wti.xml']))
for e in v.get('local_derivatives', []):
    e['sha256'] = hashlib.sha256((W / e['path']).read_bytes()).hexdigest()
(S / 'verification.json').write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
result = {'task': 'bounded_source_preflight', 'complete': True, 'decisive_date': decisive,
          'decisive_date_reason': 'Original authoring began 2026-10-19; this is a resumed preflight, not a new authoring start.',
          'official_url': 'https://wetten.overheid.nl/BWBR0001854/2026-07-01',
          'verified_at': now, 'effective_version': meta['effective_version'],
          'version_evidence': version,
          'historical_versions_checked': {'official_manifest_states': len(expressions),
              'method': 'All 126 manifestation intervals inspected; one effective state selected, not all historical article bodies fetched.',
              'rejected_historical_index': {'path': 'sources/official-index.xml', 'actual_effective_date': ET.parse(S / 'official-index.xml').getroot().get('inwerkingtreding'), 'disposition': 'Not an index or current source; excluded.'},
              'historical_articles_concatenated': False, 'duplicate_expected_ids': coverage['duplicates_expected']},
          'annexes_checked': coverage['annex_disposition'],
          'coverage': {'expected': coverage['expected_total'], 'parsed': coverage['parsed_total'],
              'repealed_slots': len(coverage['repealed_slots']), 'missing': coverage['missing'],
              'extra': coverage['unexpected'], 'full_statutory_content_checks': coverage['full_text_check'],
              'notes': coverage['notes_count'] + coverage['extra_editorial_notes'], 'report': 'coverage-evidence.json'},
          'repairs': [{'unit': 'a323', 'change': 'Preserved two editorial paragraphs separately; old inline concatenation joined nummering.De. Statutory wording and existing commentary unchanged.'}],
          'unresolved_blockers': [],
          'limitations': ['This completes only source preflight, not the manuscript or independent legal review.',
              'Direct wetten.overheid.nl HTML requests failed during recheck; fresh official repository XML, manifest and WTI succeeded with HTTP 200. Earlier official page extraction remains preserved.',
              'Firecrawl CLI reports zero available credits; no new paid scrape attempted.',
              'Future 2027-01-01 and undated/pending amendments are recorded, not merged into effective text.',
              '548 units still lack commentary, as recorded before this task.']}
(W / 'preflight-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'complete': True, 'decisive_date': decisive, 'effective_version': meta['effective_version'],
                  'historical_states_checked': len(expressions), 'full_content_units_matched': coverage['full_text_check']['matched'],
                  'unresolved_blockers': []}))
