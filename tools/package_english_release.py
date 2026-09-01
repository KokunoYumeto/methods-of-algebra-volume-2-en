"""Create a deterministic reader-first nine-file English release payload."""

from datetime import datetime, timezone
import csv, hashlib, json
from pathlib import Path
import shutil, zipfile


ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/"release"/"staging"
PAYLOAD=STAGE/"payload"
FIXED=(2024,9,1,0,0,0)
PAYLOAD_ROLES=(
    ("00_methods-of-algebra-volume-2-independent-english-edition.pdf","primary reader PDF"),
    ("01_complete-xelatex-source.zip","complete editable XeLaTeX source"),
    ("02_semantic-backend.zip","locale-linked semantic backend"),
    ("03_offline-html-reader.zip","accessible reflowable offline HTML reader"),
    ("04_provenance-and-reproducibility.zip","authority, workflow, QA, hashes, and build tools"),
    ("LICENSE","CC BY 4.0 license text"),
    ("README.txt","reader-first scope and use note"),
)
PAYLOAD_NAMES=tuple(name for name,_ in PAYLOAD_ROLES)+("MANIFEST.csv","SHA256SUMS.txt")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def zip_files(out, entries):
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path,arc in sorted(entries,key=lambda x:x[1]):
            info=zipfile.ZipInfo(arc,FIXED);info.create_system=3;info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,path.read_bytes())
    with zipfile.ZipFile(out) as z:
        bad=z.testzip(); count=len(z.infolist()); total=sum(i.file_size for i in z.infolist())
    if bad:raise RuntimeError(f"bad ZIP entry: {bad}")
    return {"entries":count,"uncompressed_bytes":total,"bytes":out.stat().st_size,"sha256":sha(out)}
def gather(base, predicate=lambda p:True):
    return [(p,p.relative_to(base).as_posix()) for p in base.rglob("*") if p.is_file() and predicate(p)]
def reset_payload():
    resolved_root=ROOT.resolve();resolved=PAYLOAD.resolve()
    if resolved_root!=resolved and resolved_root not in resolved.parents:
        raise RuntimeError(f"Refusing to reset path outside English lane: {resolved}")
    if PAYLOAD.exists():shutil.rmtree(PAYLOAD)
    PAYLOAD.mkdir(parents=True,exist_ok=False)
def main():
    required=[ROOT/"qa"/"PDF_BUILD_RECEIPT.json",ROOT/"qa"/"HTML_BUILD_RECEIPT.json",ROOT/"backend"/"BACKEND_VALIDATION.json"]
    reports=[json.loads(p.read_text(encoding="utf-8-sig")) for p in required]
    if not all(r.get("result")=="PASS" for r in reports):raise SystemExit("Build/backend receipts must all PASS")
    reset_payload()
    pdf=ROOT/"output"/"pdf"/"methods-of-algebra-volume-2-independent-english-edition.pdf"
    shutil.copy2(pdf,PAYLOAD/"00_methods-of-algebra-volume-2-independent-english-edition.pdf")
    source_entries=gather(ROOT/"source"/"en")
    zips={}
    zips["01_complete-xelatex-source.zip"]=zip_files(PAYLOAD/"01_complete-xelatex-source.zip",source_entries)
    backend_entries=gather(ROOT/"backend")
    zips["02_semantic-backend.zip"]=zip_files(PAYLOAD/"02_semantic-backend.zip",backend_entries)
    reader_entries=gather(ROOT/"reader"/"dist")
    zips["03_offline-html-reader.zip"]=zip_files(PAYLOAD/"03_offline-html-reader.zip",reader_entries)
    provenance=[]
    for folder in [ROOT/"controls",ROOT/"qa"]:
        provenance += [(p,f"{folder.name}/{p.relative_to(folder).as_posix()}") for p in folder.rglob("*") if p.is_file()]
    provenance += [(p,f"tools/{p.name}") for p in sorted((ROOT/"tools").glob("*.py"))]
    zips["04_provenance-and-reproducibility.zip"]=zip_files(PAYLOAD/"04_provenance-and-reproducibility.zip",provenance)
    shutil.copy2(ROOT/"source"/"en"/"LICENSE",PAYLOAD/"LICENSE")
    readme='''Methods of Algebra, Volume 2: Linear Algebra — Independent English Edition

Complete English-access derivative of Wen-Wei Li's 2024 Chinese corpus,
including 146 source units and two separately attributed mastery bridges.
Source authority: official commit 9a5803ff77dd3257484cb177f851a73770a59dd3,
tree 23bd05c2fb8434278df4fdfb636559a6a2b0d2ff. License: CC BY 4.0.

Start with 00_methods-of-algebra-volume-2-independent-english-edition.pdf.
For a reflowable offline reader, extract 03_offline-html-reader.zip and open
index.html. The reader bundles MathJax locally and needs no network connection.
The source, locale-linked backend, and reproducibility evidence are supplied in
the remaining ZIP archives.

This is an independent translation. Wen-Wei Li and Higher Education Press do
not endorse it. English translation, reader configuration, terminology
reconciliation, metadata, and backend production used OpenAI Codex
gpt-5.6-sol, Ultra, acting on instructions of the user; that disclosure does
not displace source authorship or other human/component credits.
'''
    (PAYLOAD/"README.txt").write_bytes(readme.encode("utf-8"))
    roles=dict(PAYLOAD_ROLES)
    rows=[]
    for name,role in roles.items():
        p=PAYLOAD/name;rows.append({"filename":name,"bytes":p.stat().st_size,"sha256":sha(p),"role":role})
    with (PAYLOAD/"MANIFEST.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys(),lineterminator="\n");w.writeheader();w.writerows(rows)
    checks=rows+[{"filename":"MANIFEST.csv","bytes":(PAYLOAD/"MANIFEST.csv").stat().st_size,"sha256":sha(PAYLOAD/"MANIFEST.csv"),"role":"payload inventory"}]
    sums="".join(f'{r["sha256"]}  {r["filename"]}\n' for r in checks)
    (PAYLOAD/"SHA256SUMS.txt").write_bytes(sums.encode("utf-8"))
    actual=sorted(p.name for p in PAYLOAD.iterdir())
    if actual!=sorted(PAYLOAD_NAMES):raise RuntimeError(f"Non-canonical payload inventory: {actual}")
    public=[PAYLOAD/name for name in PAYLOAD_NAMES]
    receipt={"schema":"o014-english-release-package-v1","created_at_utc":datetime.now(timezone.utc).isoformat(),"result":"PASS",
      "files":[{"filename":p.name,"bytes":p.stat().st_size,"sha256":sha(p)} for p in public],
      "total_bytes":sum(p.stat().st_size for p in public),"zips":zips,"source_units":146,"mastery_bridges":2,
      "source_commit":"9a5803ff77dd3257484cb177f851a73770a59dd3","source_tree":"23bd05c2fb8434278df4fdfb636559a6a2b0d2ff","license":"CC-BY-4.0"}
    (STAGE/"PACKAGE_RECEIPT.json").write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"result":"PASS","files":9,"total_bytes":receipt["total_bytes"],"receipt_sha256":sha(STAGE/"PACKAGE_RECEIPT.json")}))
if __name__=="__main__":main()
