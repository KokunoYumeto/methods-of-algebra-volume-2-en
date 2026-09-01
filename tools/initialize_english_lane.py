from pathlib import Path
import hashlib
import json
import re
import shutil

LANE = Path(__file__).resolve().parents[1]
ID = LANE.parents[1] / 'id' / 'methods-of-algebra-volume-2-id'
UP = ID / 'authority/upstream/AlJabr-2-9a5803ff77dd3257484cb177f851a73770a59dd3'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

for rel in ('source/en', 'backend', 'reader/tools', 'controls/ranges', 'qa', 'output/pdf', 'release'):
    (LANE / rel).mkdir(parents=True, exist_ok=True)
records = [json.loads(line) for line in (ID / 'backend/units.jsonl').read_text(encoding='utf-8-sig').splitlines() if line.strip()]
master = (ID / 'source/id-ID/Al-jabr-2-id-complete-draft.tex').read_text(encoding='utf-8')
stems = re.findall(r'\\input\{((?:prelude-unit-\d{3}|chapter\d+-unit-\d{3}|appendix\d+-unit-\d{3}|mastery-bridge-[^}]+))\}', master)
assert len(records) == 146 and len(stems) == 148
mapping = []
for record, stem in zip(records, stems[:146]):
    entry = dict(record)
    entry.update(locale='en', status='not_started', target_path=f'source/en/{stem}.tex',
                 id_reference_path=str(ID / f'source/id-ID/{stem}.tex'),
                 chinese_source_path=str(UP / record['source_path']))
    entry.pop('target_sha256', None)
    entry['id_reference_sha256'] = sha(Path(entry['id_reference_path']))
    mapping.append(entry)
payload = {'schema':'o014-english-source-map-v1','units':mapping,'bridge_stems':stems[146:],
           'chinese_root':str(UP),'indonesian_root':str(ID),'upstream_readme_sha256':sha(UP/'README.md'),
           'upstream_license_sha256':sha(UP/'LICENSE')}
(LANE/'controls/SOURCE_UNIT_MAP.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for name in ('AJbook2.cls','mycommand.sty','myarrows.sty','Al-jabr.bib','LICENSE','ccby.png','Lanzhou.png'):
    source = UP/name
    target = LANE/'source/en'/name
    if not target.exists():
        shutil.copy2(source,target)
state = {'schema':'o014-english-current-state-v1','scope':'complete 146-unit English edition plus two mastery bridges',
         'indonesian_edition_unchanged':True,'translated_units':0,'admitted_units':0,'next_sequence':1,
         'status':'production_started','build_status':'not_yet_built','published':False,
         'source_map':'controls/SOURCE_UNIT_MAP.json','workflow':'controls/ENGLISH_EDITION_SCOPE.md'}
(LANE/'controls/CURRENT_STATE.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'units':len(mapping),'bridges':len(stems[146:]),'source_map':str(LANE/'controls/SOURCE_UNIT_MAP.json')}))
