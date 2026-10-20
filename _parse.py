#!/usr/bin/env python3
"""Reproducible extraction of ONE effective BWB toestand; no historical merge."""
from pathlib import Path
import xml.etree.ElementTree as ET
import json,re,hashlib,collections
W=Path(__file__).resolve().parent
RAW=W/'sources/intake-version.xml'
SKIP={'meta-data','opmerkingen-inhoud'}
BLOCK={'al','considerans.al','wij','afkondiging','slotformulering','gegeven','ondertekening','uitgifte','dagtekening','koning'}
def norm(s):return re.sub(r'\s+',' ',s).strip()
def inline(e):
    return (e.text or '')+''.join(('' if c.tag in SKIP or (c.tag=='redactie' and c.get('type')=='extra') else inline(c))+(c.tail or '') for c in e)
def render(e):
    if e.tag in SKIP or e.tag=='kop':return ''
    if e.tag in {'al','considerans.al','redactie','wij','afkondiging','koning'}:return norm(inline(e))
    if e.tag in {'lid','li'}:
        number=e.findtext('lidnr' if e.tag=='lid' else 'li.nr','').strip()
        body='\n\n'.join(filter(None,(render(c) for c in e if c.tag not in {'lidnr','li.nr'})))
        return (number+' '+body).strip()
    if e.tag=='lijst':return '\n\n'.join(filter(None,map(render,e)))
    if not list(e):return norm(e.text or '')
    return '\n\n'.join(filter(None,(render(c) for c in e)))
def heading(e):
    k=e.find('kop')
    return norm(' '.join(inline(c) for c in k)) if k is not None else e.tag
root=ET.parse(RAW).getroot()
assert root.tag=='toestand' and root.get('bwb-id')=='BWBR0001854' and root.get('inwerkingtreding')=='2026-07-01'
units=[];chapter_nodes=[];chapters=[];title_counts=collections.Counter()
def walk(e,structure=()):
    if e.tag in {'boek','titeldeel','afdeling','paragraaf','hoofdstuk'}:structure=structure+(heading(e),)
    if e.tag in {'artikel','aanhef','wetsluiting'}:
        if e.tag=='artikel':
            number=e.findtext('kop/nr').strip();assert number
            uid='a'+number; label='Artikel '+number
        else:uid=e.tag;label={'aanhef':'Aanhef','wetsluiting':'Slotformulier en ondertekening'}[uid]
        # Chapters hold 20 units while retaining full official hierarchy on each unit.
        n=len(units)//20+1
        if n>len(chapters):chapters.append({'n':n,'slug':f'deel-{n:02d}','title':''})
        # Preserve paragraph boundaries in multi-paragraph editorial notes.
        notes=['\n\n'.join(filter(None,(render(c) for c in x))) for x in e.findall('.//opmerkingen-inhoud')]
        notes += [norm(inline(x)) for x in e.findall(".//redactie[@type='extra']")]
        units.append({'id':uid,'label':label,'title':'','chapter':n,'structure':list(structure),'text':render(e),'notes':notes,'official_path':e.get('bwb-ng-variabel-deel'),'official_status':e.get('status','goed'),'effective_from':e.get('inwerking'),'source_xml_id':e.get('id')})
        return
    for c in e:
        if c.tag not in SKIP:walk(c,structure)
walk(root)
assert len([u for u in units if u['id'].startswith('a') and u['id']!='aanhef'])==810
assert len(units)==len({u['id'] for u in units})
for c in chapters:
    us=[u for u in units if u['chapter']==c['n']];c['title']=us[0]['label']+' – '+us[-1]['label']
(W/'units.jsonl').write_text(''.join(json.dumps(u,ensure_ascii=False)+'\n' for u in units))
canonical='# Wetboek van Strafrecht — officiële XML-toestand 2026-07-01\n\n'+'\n\n'.join('## '+u['label']+'\n\n'+u['text'] for u in units)+'\n'
(W/'sources/canonical.md').write_text(canonical)
meta={'cc':'nl','lang':'nl','repo':'Komentar-NL-BWBR0001854','repo_dir':'/Volumes/LaCie/open-commentary/nl/Komentar-NL-BWBR0001854','title':'Commentaar op het Wetboek van Strafrecht','source_path':str(W/'sources/canonical.md'),'intro_file':'00-inleiding.md','intro_desc':'Reikwijdte, leeswijzer en bronmethode','labels':{'text':'Wettekst','chapter':'Commentaardeel','notes':'Redactionele bronopmerking'},'chapters':chapters,'decisive_date':'2026-10-19','effective_version':'2026-07-01_0','raw_source_path':str(RAW),'raw_sha256':hashlib.sha256(RAW.read_bytes()).hexdigest()}
(W/'meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
# Compare the original intake to the freshly derived official article texts, independently of whitespace.
orig=(W/'sources/original-intake.md').read_text();parts=re.split(r'^#### Artikel (\S+)\s*$',orig,flags=re.M);old={parts[i]:parts[i+1].split('\n### ')[0].strip() for i in range(1,len(parts),2)}
changes=[]
for u in units:
    if u['id'] not in {'aanhef','wetsluiting'}:
        num=u['id'][1:];a=norm(old.get(num,''));b=norm(u['text'])
        if a!=b:changes.append({'id':u['id'],'intake_text':old.get(num),'official_text':u['text']})
(W/'sources/change-map.json').write_text(json.dumps({'original_sha256':hashlib.sha256((W/'sources/original-intake.md').read_bytes()).hexdigest(),'official_xml_sha256':meta['raw_sha256'],'compared_articles':810,'changed_or_rendering_differences':changes,'note':'Whitespace normalized; XML status redactie and source wrappers can differ from intake. No legislation since intake inferred from rendering differences.'},ensure_ascii=False,indent=2)+'\n')
print(f'{len(units)} units; {len(chapters)} chapters; {len(changes)} intake differences')
