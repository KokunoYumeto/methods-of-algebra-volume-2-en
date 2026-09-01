"""Create a deterministic reader-first nine-file English release payload."""

from datetime import datetime, timezone
import csv, hashlib, json
from pathlib import Path, PurePosixPath
import shutil, sys, zipfile

TOOLS=Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0,str(TOOLS))
from release_visual_gates import validate_html_browser_gate, validate_pdf_visual_gate


ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/"release"/"staging"
PAYLOAD=STAGE/"payload"
RECEIPT=STAGE/"PACKAGE_RECEIPT.json"
RECEIPT_TMP=STAGE/"PACKAGE_RECEIPT.json.tmp"
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
BACKEND_ARTIFACTS=("units.jsonl","segments.jsonl","terms.csv","figure-alt-text-en.csv","bridges.jsonl")


def sha(path):
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_link(path):
    return path.is_symlink() or (hasattr(path,"is_junction") and path.is_junction())


def safe_path(path, must_exist=False):
    path=Path(path)
    lexical=path.absolute()
    try:
        relative=lexical.relative_to(ROOT)
    except ValueError as exc:
        raise RuntimeError(f"Path is outside English lane: {lexical}") from exc
    current=ROOT
    for part in relative.parts:
        current=current/part
        if is_link(current):
            raise RuntimeError(f"Symlink/junction input is forbidden: {current}")
    if must_exist and not path.exists():
        raise RuntimeError(f"Required path is missing: {path}")
    resolved=path.resolve(strict=must_exist)
    if resolved!=ROOT and ROOT not in resolved.parents:
        raise RuntimeError(f"Resolved path is outside English lane: {resolved}")
    return path


def require_dir(path):
    path=safe_path(path,must_exist=True)
    if not path.is_dir():
        raise RuntimeError(f"Required directory is not a directory: {path}")
    return path


def fingerprint(path):
    path=safe_path(path,must_exist=True)
    if not path.is_file():
        raise RuntimeError(f"Required input is not a regular file: {path}")
    size=path.stat().st_size
    if size<=0:
        raise RuntimeError(f"Required input is empty: {path}")
    return {"bytes":size,"sha256":sha(path)}


def bind_file(path, expected_bytes, expected_sha256, label):
    if type(expected_bytes) is not int or expected_bytes<=0:
        raise RuntimeError(f"{label} receipt has invalid byte count")
    if (not isinstance(expected_sha256,str) or len(expected_sha256)!=64
            or expected_sha256!=expected_sha256.lower()
            or any(c not in "0123456789abcdef" for c in expected_sha256)):
        raise RuntimeError(f"{label} receipt has invalid SHA-256")
    current=fingerprint(path)
    expected={"bytes":expected_bytes,"sha256":expected_sha256}
    if current!=expected:
        raise RuntimeError(f"{label} no longer matches its PASS receipt: expected {expected}, got {current}")
    return current


def load_pass_receipt(path, schema):
    receipt_file=fingerprint(path)
    try:
        report=json.loads(path.read_text(encoding="utf-8-sig"))
    except (UnicodeError,json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid JSON receipt: {path}") from exc
    if not isinstance(report,dict) or report.get("schema")!=schema or report.get("result")!="PASS":
        raise RuntimeError(f"Receipt must be {schema} with result PASS: {path}")
    return report,receipt_file


def gather(base, predicate=lambda path:True, recursive=True):
    base=require_dir(base)
    entries=[]
    pending=[base]
    while pending:
        folder=pending.pop()
        for path in sorted(folder.iterdir(),key=lambda item:item.name):
            safe_path(path,must_exist=True)
            if path.is_dir():
                if recursive:
                    pending.append(path)
            elif path.is_file():
                if predicate(path):
                    fingerprint(path)
                    entries.append((path,path.relative_to(base).as_posix()))
            else:
                raise RuntimeError(f"Unsupported input type: {path}")
    if not entries:
        raise RuntimeError(f"No required input files found under {base}")
    return sorted(entries,key=lambda item:item[1])


def zip_files(out, entries):
    if not entries:
        raise RuntimeError(f"Refusing to create empty archive: {out}")
    safe_path(out)
    require_dir(out.parent)
    if out.exists() or is_link(out):
        raise RuntimeError(f"Archive output already exists: {out}")
    validated=[]
    seen=set()
    for path,arc in entries:
        fingerprint(path)
        archive_path=PurePosixPath(arc)
        if (not arc or "\\" in arc or archive_path.is_absolute()
                or archive_path.as_posix()!=arc or any(part in ("",".","..") for part in archive_path.parts)):
            raise RuntimeError(f"Unsafe archive member name: {arc!r}")
        if arc in seen:
            raise RuntimeError(f"Duplicate archive member name: {arc}")
        seen.add(arc)
        validated.append((path,arc))
    with zipfile.ZipFile(out,"x",zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path,arc in sorted(validated,key=lambda item:item[1]):
            info=zipfile.ZipInfo(arc,FIXED)
            info.create_system=3
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            archive.writestr(info,path.read_bytes())
    with zipfile.ZipFile(out) as archive:
        bad=archive.testzip()
        count=len(archive.infolist())
        total=sum(info.file_size for info in archive.infolist())
    if bad:
        raise RuntimeError(f"Bad ZIP entry: {bad}")
    if count!=len(validated) or total<=0:
        raise RuntimeError(f"Incomplete or empty ZIP output: {out}")
    return {"entries":count,"uncompressed_bytes":total,**fingerprint(out)}


def validate_html_distribution(report, entries):
    by_name={arc:path for path,arc in entries}
    observed_files=len(entries)
    observed_bytes=sum(fingerprint(path)["bytes"] for path,_ in entries)
    if type(report.get("dist_files")) is not int or type(report.get("dist_bytes")) is not int:
        raise RuntimeError("HTML PASS receipt has invalid distribution totals")
    if (observed_files,observed_bytes)!=(report["dist_files"],report["dist_bytes"]):
        raise RuntimeError("HTML distribution totals no longer match its PASS receipt")
    index=ROOT/"reader"/"dist"/"index.html"
    index_record=bind_file(index,report.get("index_bytes"),report.get("index_sha256"),"HTML index")
    validation_path=ROOT/"reader"/"dist"/"validation-report.json"
    try:
        current_validation=json.loads(validation_path.read_text(encoding="utf-8-sig"))
    except (UnicodeError,json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid HTML validation report: {validation_path}") from exc
    if (not isinstance(current_validation,dict) or current_validation!=report.get("validation")
            or current_validation.get("status")!="pass"):
        raise RuntimeError("HTML validation report no longer matches its PASS receipt")
    build_report=ROOT/"reader"/"build"/"reader-build-report.json"
    build_record=fingerprint(build_report)
    if build_record["sha256"]!=report.get("reader_build_report_sha256"):
        raise RuntimeError("HTML reader build report no longer matches its PASS receipt")
    sums_path=ROOT/"reader"/"dist"/"SHA256SUMS.txt"
    sums_record=fingerprint(sums_path)
    listed={}
    for line in sums_path.read_text(encoding="utf-8-sig").splitlines():
        digest,separator,name=line.partition("  ")
        member=PurePosixPath(name)
        if (not separator or len(digest)!=64 or digest!=digest.lower()
                or any(c not in "0123456789abcdef" for c in digest)
                or not name or "\\" in name or member.is_absolute()
                or member.as_posix()!=name or any(part in ("",".","..") for part in member.parts)
                or name in listed):
            raise RuntimeError(f"Invalid HTML checksum entry: {line!r}")
        listed[name]=digest
    expected_names=set(by_name)-{"SHA256SUMS.txt"}
    if set(listed)!=expected_names:
        raise RuntimeError("HTML checksum inventory is not exact")
    for name,digest in listed.items():
        if sha(by_name[name])!=digest:
            raise RuntimeError(f"HTML file fails its checksum inventory: {name}")
    return {"index":{"path":"reader/dist/index.html",**index_record},
            "distribution":{"files":observed_files,"bytes":observed_bytes,
                            "sha256s":{"path":"reader/dist/SHA256SUMS.txt",**sums_record}},
            "reader_build_report":{"path":"reader/build/reader-build-report.json",**build_record}}


def validate_inputs():
    receipt_specs=(
        ("pdf",ROOT/"qa"/"PDF_BUILD_RECEIPT.json","o014-english-pdf-build-v1"),
        ("pdf_visual",ROOT/"qa"/"PDF_VISUAL_QA.json","o014-english-pdf-visual-qa-v2"),
        ("html",ROOT/"qa"/"HTML_BUILD_RECEIPT.json","o014-english-html-build-v1"),
        ("html_browser",ROOT/"qa"/"HTML_BROWSER_QA.json","o014-english-html-browser-qa-v2"),
        ("backend",ROOT/"backend"/"BACKEND_VALIDATION.json","o014-english-backend-validation-v1"),
    )
    reports={}
    receipt_records={}
    for key,path,schema in receipt_specs:
        reports[key],record=load_pass_receipt(path,schema)
        receipt_records[key]={"path":path.relative_to(ROOT).as_posix(),**record}

    pdf=ROOT/"output"/"pdf"/"methods-of-algebra-volume-2-independent-english-edition.pdf"
    pdf_relative=pdf.relative_to(ROOT).as_posix()
    if reports["pdf"].get("pdf")!=pdf_relative:
        raise RuntimeError("PDF PASS receipt names a non-canonical artifact")
    pdf_record=bind_file(pdf,reports["pdf"].get("pdf_bytes"),reports["pdf"].get("pdf_sha256"),"PDF")
    pdf_visual_binding=validate_pdf_visual_gate(ROOT,reports["pdf"],reports["pdf_visual"])

    source_entries=gather(ROOT/"source"/"en")
    backend_entries=gather(ROOT/"backend")
    reader_entries=gather(ROOT/"reader"/"dist")
    html_binding=validate_html_distribution(reports["html"],reader_entries)
    html_browser_binding=validate_html_browser_gate(ROOT,reports["html"],reports["html_browser"])

    backend_report=reports["backend"]
    artifacts=backend_report.get("artifacts")
    if not isinstance(artifacts,dict) or set(artifacts)!=set(BACKEND_ARTIFACTS):
        raise RuntimeError("Backend PASS receipt has a non-canonical artifact inventory")
    backend_binding={}
    for name in BACKEND_ARTIFACTS:
        expected=artifacts[name]
        if not isinstance(expected,dict):
            raise RuntimeError(f"Backend PASS receipt has an invalid entry for {name}")
        current=bind_file(ROOT/"backend"/name,expected.get("bytes"),expected.get("sha256"),f"Backend {name}")
        backend_binding[name]={"path":f"backend/{name}",**current}
    override=backend_report.get("term_override_input")
    override_path=ROOT/"backend"/"term-overrides-en.csv"
    if not isinstance(override,dict) or override.get("path")!="backend/term-overrides-en.csv":
        raise RuntimeError("Backend PASS receipt names a non-canonical terminology override")
    override_record=bind_file(override_path,override.get("bytes"),override.get("sha256"),"Backend terminology override")
    backend_binding[override_path.name]={"path":"backend/term-overrides-en.csv",**override_record}

    provenance=[]
    for folder in (ROOT/"controls",ROOT/"qa"):
        provenance += [(path,f"{folder.name}/{arc}") for path,arc in gather(folder)]
    provenance += [(path,f"tools/{arc}") for path,arc in gather(ROOT/"tools",lambda path:path.suffix==".py",recursive=False)]
    license_path=ROOT/"source"/"en"/"LICENSE"
    fingerprint(license_path)
    return {"pdf":pdf,"source_entries":source_entries,"backend_entries":backend_entries,
            "reader_entries":reader_entries,"provenance":provenance,"license":license_path,
            "bindings":{"receipts":receipt_records,
                        "pdf":{"path":pdf_relative,**pdf_record},
                        "html":html_binding,"backend":backend_binding,
                        "visual_qa":{"pdf":pdf_visual_binding,"html":html_browser_binding}}}


def audit_tree(base):
    base=require_dir(base)
    pending=[base]
    while pending:
        folder=pending.pop()
        for path in folder.iterdir():
            safe_path(path,must_exist=True)
            if path.is_dir():
                pending.append(path)


def reset_payload():
    safe_path(STAGE)
    if STAGE.exists():
        require_dir(STAGE)
    else:
        require_dir(STAGE.parent)
        STAGE.mkdir(exist_ok=False)
    for stale in (RECEIPT,RECEIPT_TMP):
        safe_path(stale)
        if stale.exists():
            if not stale.is_file():
                raise RuntimeError(f"Refusing to remove non-file stale receipt: {stale}")
            stale.unlink()
    safe_path(PAYLOAD)
    if PAYLOAD.exists():
        audit_tree(PAYLOAD)
        shutil.rmtree(PAYLOAD)
    PAYLOAD.mkdir(exist_ok=False)


def validate_payload():
    if len(PAYLOAD_NAMES)!=9 or len(set(PAYLOAD_NAMES))!=9:
        raise RuntimeError("Release allowlist must contain exactly nine unique names")
    entries=list(PAYLOAD.iterdir())
    actual={path.name for path in entries}
    if len(entries)!=9 or actual!=set(PAYLOAD_NAMES):
        raise RuntimeError(f"Non-canonical payload inventory: {sorted(actual)}")
    for path in entries:
        fingerprint(path)
    return [{"filename":name,**fingerprint(PAYLOAD/name)} for name in PAYLOAD_NAMES]


def main():
    inputs=validate_inputs()
    reset_payload()
    shutil.copy2(inputs["pdf"],PAYLOAD/"00_methods-of-algebra-volume-2-independent-english-edition.pdf")
    zips={}
    zips["01_complete-xelatex-source.zip"]=zip_files(PAYLOAD/"01_complete-xelatex-source.zip",inputs["source_entries"])
    zips["02_semantic-backend.zip"]=zip_files(PAYLOAD/"02_semantic-backend.zip",inputs["backend_entries"])
    zips["03_offline-html-reader.zip"]=zip_files(PAYLOAD/"03_offline-html-reader.zip",inputs["reader_entries"])
    zips["04_provenance-and-reproducibility.zip"]=zip_files(PAYLOAD/"04_provenance-and-reproducibility.zip",inputs["provenance"])
    shutil.copy2(inputs["license"],PAYLOAD/"LICENSE")
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
        path=PAYLOAD/name
        rows.append({"filename":name,**fingerprint(path),"role":role})
    with (PAYLOAD/"MANIFEST.csv").open("x",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=rows[0].keys(),lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    manifest_record=fingerprint(PAYLOAD/"MANIFEST.csv")
    checks=rows+[{"filename":"MANIFEST.csv",**manifest_record,"role":"payload inventory"}]
    sums="".join(f'{row["sha256"]}  {row["filename"]}\n' for row in checks)
    (PAYLOAD/"SHA256SUMS.txt").write_bytes(sums.encode("utf-8"))
    packaged_files=validate_payload()
    receipt={"schema":"o014-english-release-package-v1","created_at_utc":datetime.now(timezone.utc).isoformat(),"result":"PASS",
      "files":packaged_files,"total_bytes":sum(record["bytes"] for record in packaged_files),"zips":zips,
      "validated_inputs":inputs["bindings"],"source_units":146,"mastery_bridges":2,
      "source_commit":"9a5803ff77dd3257484cb177f851a73770a59dd3","source_tree":"23bd05c2fb8434278df4fdfb636559a6a2b0d2ff","license":"CC-BY-4.0"}
    RECEIPT_TMP.write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    fingerprint(RECEIPT_TMP)
    RECEIPT_TMP.replace(RECEIPT)
    print(json.dumps({"result":"PASS","files":9,"total_bytes":receipt["total_bytes"],"receipt_sha256":sha(RECEIPT)}))


if __name__=="__main__":main()
