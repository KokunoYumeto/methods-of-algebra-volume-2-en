"""Record the exact frozen authority and editable closure for this edition."""
from datetime import datetime, timezone
import hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
UP=Path(r"C:\Users\Floris\Documents\interlanguage\04_mirrors\id\methods-of-algebra-volume-2-id\authority\upstream\AlJabr-2-9a5803ff77dd3257484cb177f851a73770a59dd3")
names=["Al-jabr-2.tex","AJbook2.cls","Al-jabr.bib","prelude.tex",*[f"chapter{i}.tex" for i in range(1,10)],
       "appendix1.tex","appendix2.tex","coverpage.tex","pre-prelude.tex","font-setup-HEP.tex","font-setup-Noto.tex",
       "font-setup-open.tex","titles-setup.tex","mycommand.sty","myarrows.sty","README.md","LICENSE","ccby.png","Lanzhou.png"]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
files=[{"path":n,"bytes":(UP/n).stat().st_size,"sha256":sha(UP/n)} for n in names]
payload={"schema":"o014-english-source-freeze-v1","recorded_at_utc":datetime.now(timezone.utc).isoformat(),
 "author":"Wen-Wei Li","title_original":"代数学方法, 卷二, 线性代数","edition":"2024 Higher Education Press",
 "isbn":"978-7-04-062754-1","repository":"https://github.com/wenweili/AlJabr-2",
 "commit":"9a5803ff77dd3257484cb177f851a73770a59dd3","tree":"23bd05c2fb8434278df4fdfb636559a6a2b0d2ff",
 "license_id":"CC-BY-4.0","license_sha256":"48a83a6e39f7b2f166763b30776132c9a99aa816f17cb06f87ad5b8542a7b71f",
 "source_files":files,"source_unit_map":"controls/SOURCE_UNIT_MAP.json","mapped_units":146,
 "build_paths":["XeLaTeX/Biber/index PDF","Pandoc plus local MathJax offline HTML"],
 "official_reuse_check":{"result":"no_suitable_complete_english_edition_found_in_inspected_official_sources",
 "sources":["https://wwli.asia/docs/books/","https://github.com/wenweili/AlJabr-2/tree/9a5803ff77dd3257484cb177f851a73770a59dd3"],
 "scope_note":"Bounded official-source result, not a universal nonexistence claim."},
 "result":"PASS" if len(files)==27 and all(p["bytes"]>0 for p in files) else "FAIL"}
out=ROOT/"controls"/"SOURCE_FREEZE.json";out.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print(json.dumps({"result":payload["result"],"files":len(files),"bytes":sum(p["bytes"] for p in files),"sha256":sha(out)}))
if payload["result"]!="PASS":raise SystemExit(1)
