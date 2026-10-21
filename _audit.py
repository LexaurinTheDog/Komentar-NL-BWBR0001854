#!/usr/bin/env python3
"""Technical checks; deliberately never equates length or extraction to legal approval."""
from pathlib import Path
from xml.dom import minidom
import json,re,hashlib,unicodedata,collections,sys
W=Path(__file__).resolve().parent
sys.path.insert(0,'/Volumes/LaCie/open-commentary/_tools')
from build_repo import load_commentary,load_units
u=load_units(str(W));c=load_commentary(str(W));d=minidom.parse(str(W/'sources/intake-version.xml'))
def tx(n):
 if n.nodeType==n.TEXT_NODE:return n.data
 if n.nodeType!=n.ELEMENT_NODE:return ''
 if n.tagName in {'kop','meta-data','opmerkingen-inhoud'}:return ''
 if n.tagName=='redactie' and n.getAttribute('type')=='extra':return ''
 return ''.join(tx(x) for x in n.childNodes)
def key(s):return re.sub(r'\s+','',unicodedata.normalize('NFKC',s))
raw={}
for a in d.getElementsByTagName('artikel'):
 n=a.getElementsByTagName('kop')[0].getElementsByTagName('nr')[0]
 number=''.join(x.data for x in n.childNodes if x.nodeType==x.TEXT_NODE).strip();raw['a'+number]=tx(a)
for tag in ['aanhef','wetsluiting']:raw[tag]=tx(d.getElementsByTagName(tag)[0])
bad=[a['id'] for a in u if key(a['text'])!=key(raw[a['id']])]
missing=[a['id'] for a in u if a['id'] not in c]
short=[a['id'] for a in u if a['id'] in c and len(c[a['id']])<(120 if len(a['text'])<160 else 400)]
paragraphs=collections.defaultdict(list)
for ident,body in c.items():
 for p in re.split(r'\n\s*\n',body):
  if len(p)>150:paragraphs[p].append(ident)
repeats=[{'ids':ids,'text':p} for p,ids in paragraphs.items() if len(ids)>1]
r={'raw_xml_compared_units':len(u),'raw_xml_agreement':not bad,'raw_xml_disagreements':bad,'statutory_text_agreement_ratio':(len(u)-len(bad))/len(u),'commented_units':len(c),'commentary_chars':sum(map(len,c.values())),'missing_commentary_ids':missing,'missing_commentary_count':len(missing),'short_existing_commentary':short,'exact_repeated_paragraphs':repeats,'official_editorial_annotations':len(d.getElementsByTagName('opmerkingen-inhoud')),'separate_extra_redaction_notes':sum(n.getAttribute('type')=='extra' for n in d.getElementsByTagName('redactie')),'limitations':['The XML comparison ignores whitespace and excludes identified editorial material; labels and annotations are inventoried separately.','Exact repetition detection does not detect all generic prose. Repealed-slot notes share a documentary purpose and are short.','This technical audit does not establish an independent legal second pass; see the separate bounded review report. All units are assembled; substantive review is documented separately in the batch ledger.']}
(W/'audit-report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:r[k] for k in ['raw_xml_compared_units','raw_xml_agreement','raw_xml_disagreements','commented_units','commentary_chars','missing_commentary_count','short_existing_commentary','exact_repeated_paragraphs']}))
