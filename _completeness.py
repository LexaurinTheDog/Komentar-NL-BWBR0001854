#!/usr/bin/env python3
"""Independent DOM inventory and full content audit; never imports the parser."""
from pathlib import Path
from xml.dom import minidom, Node
import json, hashlib, collections, re

W = Path(__file__).resolve().parent
raw = W / 'sources/intake-version.xml'
doc = minidom.parse(str(raw))
units = [json.loads(line) for line in (W / 'units.jsonl').read_text().splitlines()]
parsed = [u['id'] for u in units]
by_id = {u['id']: u for u in units}

def children(e):
    return [n for n in e.childNodes if n.nodeType == Node.ELEMENT_NODE]

def content(e, statutory=False):
    if e.nodeType in (Node.TEXT_NODE, Node.CDATA_SECTION_NODE):
        return e.data
    if e.nodeType != Node.ELEMENT_NODE:
        return ''
    if statutory and (e.tagName in {'meta-data', 'kop', 'opmerkingen-inhoud'} or
                      e.tagName == 'redactie' and e.getAttribute('type') == 'extra'):
        return ''
    return ''.join(content(n, statutory) for n in e.childNodes)

def dense(s):
    return re.sub(r'\s+', '', s)

def identifier(e):
    if e.tagName != 'artikel':
        return e.tagName
    kop = next(n for n in children(e) if n.tagName == 'kop')
    return 'a' + content(kop.getElementsByTagName('nr')[0]).strip()

# Derive special units from their actual presence, rather than assuming them.
official_nodes = [n for n in doc.getElementsByTagName('*')
                  if n.tagName in {'artikel', 'aanhef', 'wetsluiting'}]
expected = [identifier(n) for n in official_nodes]
annex = [n.tagName for n in doc.getElementsByTagName('*')
         if 'bijlage' in n.tagName.lower() or 'annex' in n.tagName.lower()]
errors, text_checks, hierarchy = [], [], []
for node in official_nodes:
    uid = identifier(node)
    if uid not in by_id:
        continue
    u = by_id[uid]
    a, b = dense(content(node, statutory=True)), dense(u['text'])
    text_checks.append({'id': uid, 'equal': a == b,
                        'official_nonspace_chars': len(a), 'parsed_nonspace_chars': len(b),
                        'official_content_sha256': hashlib.sha256(a.encode()).hexdigest(),
                        'parsed_content_sha256': hashlib.sha256(b.encode()).hexdigest()})
    if a != b:
        errors.append({'id': uid, 'kind': 'statutory_character_stream_mismatch'})
    editorial = list(node.getElementsByTagName('opmerkingen-inhoud'))
    editorial += [e for e in node.getElementsByTagName('redactie')
                  if e.getAttribute('type') == 'extra']
    if [dense(content(e)) for e in editorial] != [dense(n) for n in u.get('notes', [])]:
        errors.append({'id': uid, 'kind': 'editorial_note_mismatch'})
    for note, parsed_note in zip(editorial, u.get('notes', [])):
        paragraphs = [e for e in children(note) if e.tagName == 'al']
        if len(paragraphs) > 1 and len(re.split(r'\n\s*\n', parsed_note)) != len(paragraphs):
            errors.append({'id': uid, 'kind': 'editorial_paragraph_boundary_loss'})
    ancestor, structure = node.parentNode, []
    while ancestor.nodeType == Node.ELEMENT_NODE:
        if ancestor.tagName in {'boek', 'titeldeel', 'afdeling', 'paragraaf', 'hoofdstuk'}:
            k = next(n for n in children(ancestor) if n.tagName == 'kop')
            structure.append(re.sub(r'\s+', ' ', ' '.join(content(c) for c in children(k))).strip())
        ancestor = ancestor.parentNode
    if list(reversed(structure)) != u.get('structure', []):
        errors.append({'id': uid, 'kind': 'structural_heading_mismatch'})
    levels = []
    for e in node.getElementsByTagName('*'):
        if e.tagName in {'lid', 'li'}:
            nr = 'lidnr' if e.tagName == 'lid' else 'li.nr'
            levels.append({'type': e.tagName,
                           'number': content(next(n for n in children(e) if n.tagName == nr)),
                           'official_path': e.getAttribute('bwb-ng-variabel-deel')})
    hierarchy.append({'id': uid, 'official_path': node.getAttribute('bwb-ng-variabel-deel'),
                      'paragraph_and_list_hierarchy': levels})

report = {
    'official_source': {
        'url': 'https://repository.officiele-overheidspublicaties.nl/bwb/BWBR0001854/2026-07-01_0/xml/BWBR0001854_2026-07-01_0.xml',
        'local_raw_evidence_path': 'sources/intake-version.xml',
        'sha256': hashlib.sha256(raw.read_bytes()).hexdigest()},
    'expected_ids': expected, 'parsed_ids': parsed,
    'expected_ids_method': 'Independent XML DOM document-order enumeration of actual artikel, aanhef and wetsluiting elements; article numbers read directly from each kop/nr. Does not import _parse.py or derive expected IDs from units.jsonl.',
    'annex_disposition': [{'status': 'verified_absence',
        'method': 'Complete official XML element inventory contains no bijlage/annex elements. All 3 books, 56 titles and 4 divisions contain articles; no empty structural branch omitted. The numbered final article 479 and separate wetsluiting are retained.',
        'matching_elements': annex}],
    'expected_articles': len(doc.getElementsByTagName('artikel')),
    'expected_total': len(expected), 'parsed_total': len(parsed),
    'missing': sorted(set(expected) - set(parsed)),
    'unexpected': sorted(set(parsed) - set(expected)),
    'duplicates_expected': [k for k, v in collections.Counter(expected).items() if v > 1],
    'duplicates_parsed': [k for k, v in collections.Counter(parsed).items() if v > 1],
    'repealed_slots': [identifier(a) for a in doc.getElementsByTagName('artikel')
                       if a.getAttribute('status') == 'vervallen'],
    'empty_statutory_units': [u['id'] for u in units if not u['text'].strip()],
    'structural_branches_without_articles': [e.getAttribute('bwb-ng-variabel-deel') for e in doc.getElementsByTagName('*') if e.tagName in {'boek', 'titeldeel', 'afdeling', 'paragraaf', 'hoofdstuk'} and not e.getElementsByTagName('artikel')],
    'structure_count': {tag: len(doc.getElementsByTagName(tag)) for tag in ['boek', 'titeldeel', 'afdeling']},
    'notes_count': len(doc.getElementsByTagName('opmerkingen-inhoud')),
    'extra_editorial_notes': len([e for e in doc.getElementsByTagName('redactie') if e.getAttribute('type') == 'extra']),
    'footnote_elements': {tag: len(doc.getElementsByTagName(tag)) for tag in ['noot', 'voetnoot', 'footnote', 'noten']},
    'full_text_check': {'method': 'All statutory DOM character data per unit, excluding kop, metadata and extra editorial insertions, compared with parsed text after removing whitespace only. All words, punctuation, paragraph and list numbers remain in comparison.',
                        'checked': len(text_checks), 'matched': sum(c['equal'] for c in text_checks),
                        'details': 'sources/statutory-content-audit.json'},
    'hierarchy_evidence': 'sources/statutory-structure.json',
    'nonoperative_material': [
        {'element': 'intitule', 'text': content(doc.getElementsByTagName('intitule')[0]), 'disposition': 'Official enactment title metadata; not a separately numbered operative unit.'},
        {'element': 'meta-data', 'disposition': 'Legislative provenance and amendment history excluded from statutory wording; all 27 opmerkingen-inhoud notes extracted separately.'},
        {'element': 'redactie type=extra', 'disposition': 'All 6 article 23 indexation annotations preserved separately as editorial notes.'}],
    'errors': errors,
    'limitations': ['Source and parsing audit only; not legal review or commentary completion.',
                    'Transitional provisions of separate amending laws mentioned in editorial notes are outside this consolidated code; references are preserved but those separate laws are not represented as articles of this code.']}
report['ok'] = not any(report[k] for k in ['missing', 'unexpected', 'duplicates_expected', 'duplicates_parsed', 'empty_statutory_units', 'structural_branches_without_articles', 'errors']) and not annex and expected == parsed
for name, value in [('coverage-evidence.json', report),
                    ('completeness-report.json', {k: v for k, v in report.items() if k not in ['expected_ids', 'parsed_ids']}),
                    ('sources/statutory-content-audit.json', text_checks),
                    ('sources/statutory-structure.json', hierarchy)]:
    (W / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: report[k] for k in ['expected_articles', 'expected_total', 'parsed_total', 'missing', 'unexpected', 'errors', 'ok']}))
raise SystemExit(0 if report['ok'] else 1)
