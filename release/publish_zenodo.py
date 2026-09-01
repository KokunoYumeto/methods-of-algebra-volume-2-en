"""Publish or resume the complete English edition on Zenodo, then read it back.

This is deliberately stateful and non-duplicating. It performs no implicit
retry loop and never prints or persists credential material.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import quote

import requests


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "release" / "staging" / "payload"
PACKAGE = ROOT / "release" / "staging" / "PACKAGE_RECEIPT.json"
STATE = ROOT / "release" / "ZENODO_TRANSACTION_STATE.json"
RECEIPT = ROOT / "release" / "ZENODO_PUBLICATION_RECEIPT.json"
README = ROOT / "README.md"
TOKEN_PATH = Path(r"C:\Users\Floris\Documents\Obsidian notes\New zenodo token.md")
API = "https://zenodo.org/api"
TITLE = "Methods of Algebra, Volume 2: Linear Algebra - Independent English Edition"
VERSION = "complete-independent-english-edition-2026-09-01"
DATE = "2026-09-01"
PAYLOAD_NAMES = (
    "00_methods-of-algebra-volume-2-independent-english-edition.pdf",
    "01_complete-xelatex-source.zip",
    "02_semantic-backend.zip",
    "03_offline-html-reader.zip",
    "04_provenance-and-reproducibility.zip",
    "LICENSE", "README.txt", "MANIFEST.csv", "SHA256SUMS.txt",
)


def sha(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def sha_file(path: Path) -> str: return sha(path.read_bytes())


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def save_state(**values) -> None:
    current = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    current.update({"schema": "o014-english-zenodo-state-v1", "credential_material_present": False,
                    "updated_at_utc": datetime.now(timezone.utc).isoformat(), **values})
    write_json(STATE, current)


def require(response, codes, phase):
    if response.status_code not in codes:
        raise RuntimeError(f"{phase}: HTTP {response.status_code}: {response.text[:700]}")
    return response


def anonymous_session():
    session = requests.Session(); session.trust_env = False
    session.headers.update({"Accept": "application/json", "Accept-Encoding": "identity",
                            "Cache-Control": "no-cache", "User-Agent": "O014-English-public-verifier/1.0"})
    return session


def auth_session(token):
    session = requests.Session(); session.trust_env = False
    session.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json",
                            "User-Agent": "O014-English-Zenodo-publisher/1.0"})
    return session


def expected_inventory():
    package = json.loads(PACKAGE.read_text(encoding="utf-8-sig"))
    rows = package.get("files", [])
    if package.get("result") != "PASS" or len(rows) != len(PAYLOAD_NAMES):
        raise RuntimeError("Release package is not an exact nine-file PASS boundary")
    receipt_names = [row.get("filename") for row in rows]
    if len(set(receipt_names)) != len(receipt_names) or set(receipt_names) != set(PAYLOAD_NAMES):
        raise RuntimeError(f"Package receipt inventory is non-canonical: {receipt_names}")
    expected = {row["filename"]: {"bytes": int(row["bytes"]), "sha256": row["sha256"].lower()}
                for row in rows}
    entries = sorted(PAYLOAD.iterdir(), key=lambda path: path.name)
    names = [path.name for path in entries]
    if names != sorted(PAYLOAD_NAMES) or not all(path.is_file() for path in entries):
        raise RuntimeError(f"Payload inventory drift: {names}")
    for name,row in expected.items():
        path=PAYLOAD/name
        if len(row["sha256"]) != 64 or any(ch not in "0123456789abcdef" for ch in row["sha256"]):
            raise RuntimeError(f"Invalid package checksum: {name}")
        if path.stat().st_size != row["bytes"] or sha_file(path) != row["sha256"]:
            raise RuntimeError(f"Payload hash drift: {name}")
    return expected, package


def metadata():
    description = (
        "<p>Complete independent English-access derivative of Wen-Wei Li's 2024 Chinese textbook "
        "<em>Methods of Algebra</em>, Volume 2: Linear Algebra. This release contains all 146 mapped "
        "source units, including exercises and hints, plus two separately attributed mastery bridges "
        "with full solutions.</p>"
        "<p>The reader-first payload includes a PDF, complete editable XeLaTeX source, a locale-linked "
        "semantic backend, an accessible reflowable offline HTML reader with local MathJax, and compact "
        "provenance/reproducibility evidence. The frozen official source is commit "
        "<code>9a5803ff77dd3257484cb177f851a73770a59dd3</code>, tree "
        "<code>23bd05c2fb8434278df4fdfb636559a6a2b0d2ff</code>.</p>"
        "<p>English translation, terminology reconciliation, reader configuration, metadata, and the "
        "modular backend were produced with <strong>OpenAI Codex gpt-5.6-sol, Ultra</strong>, acting on "
        "instructions of the user. This disclosure does not displace the source author or other human "
        "and component credits. This independent edition is not endorsed by Wen-Wei Li or Higher "
        "Education Press.</p>"
    )
    if "ttp" in TITLE.casefold() or "ttp" in description.casefold():
        raise RuntimeError("Organization label is forbidden in title/description")
    return {"upload_type": "publication", "publication_type": "book", "title": TITLE,
            "creators": [{"name": "Li, Wen-Wei"}],
            "contributors": [{"name": "TTP", "type": "Other"}],
            "description": description,
            "access_right": "open", "license": "cc-by-4.0", "language": "eng",
            "publication_date": DATE, "version": VERSION,
            "keywords": ["linear algebra", "homological algebra", "category theory", "English translation", "open textbook"],
            "related_identifiers": [{"identifier": "https://github.com/wenweili/AlJabr-2/tree/9a5803ff77dd3257484cb177f851a73770a59dd3",
                                      "relation": "isDerivedFrom", "scheme": "url"}]}


def metadata_defects(md):
    defects=[];license_value=md.get("license",{})
    description=md.get("description","");plain_description=html.unescape(description)
    if md.get("title")!=TITLE:defects.append("title")
    if md.get("access_right")!="open":defects.append("access_right")
    if (license_value.get("id") if isinstance(license_value,dict) else license_value)!="cc-by-4.0":defects.append("license")
    if md.get("language")!="eng":defects.append("language")
    if md.get("version")!=VERSION:defects.append("version")
    creators=md.get("creators",[])
    if len(creators)!=1 or creators[0].get("name")!="Li, Wen-Wei":defects.append("creators")
    contributors=md.get("contributors",[])
    if len(contributors)>1 or (contributors and (contributors[0].get("name")!="TTP" or contributors[0].get("type")!="Other")):
        defects.append("organization_contributor")
    if "ttp" in md.get("title","").casefold() or "ttp" in description.casefold():defects.append("organization_label")
    if "not endorsed by Wen-Wei Li or Higher Education Press" not in plain_description:defects.append("nonendorsement")
    if "9a5803ff77dd3257484cb177f851a73770a59dd3" not in plain_description or "23bd05c2fb8434278df4fdfb636559a6a2b0d2ff" not in plain_description:
        defects.append("frozen_source_identity")
    if "OpenAI Codex gpt-5.6-sol, Ultra" not in plain_description:defects.append("production_provenance")
    related=md.get("related_identifiers",[])
    source_url="https://github.com/wenweili/AlJabr-2/tree/9a5803ff77dd3257484cb177f851a73770a59dd3"
    if not any(row.get("identifier")==source_url and row.get("relation")=="isDerivedFrom" for row in related):
        defects.append("source_provenance")
    return defects


def public_matches(session, record, expected):
    if metadata_defects(record.get("metadata", {})): return False, []
    files = {row["key"]: row for row in record.get("files", [])}
    if set(files) != set(expected): return False, []
    reads=[]
    for name in sorted(expected):
        response=require(session.get(files[name]["links"]["self"], timeout=(20,180)), {200}, f"anonymous download {name}")
        data=response.content; row=expected[name]
        passed=len(data)==row["bytes"] and sha(data)==row["sha256"]
        reads.append({"filename":name,"url":response.url,"http_status":response.status_code,
                      "expected_bytes":row["bytes"],"bytes":len(data),"expected_sha256":row["sha256"],
                      "sha256":sha(data),"pass":passed})
        if not passed:return False,reads
    return True,reads


def main():
    expected, package = expected_inventory()
    anon=anonymous_session()
    state=json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    published_id=str(state.get("published_record_id", ""))
    if published_id:
        record=require(anon.get(f"{API}/records/{published_id}",timeout=60),{200},"read recorded public record").json()
        matched,reads=public_matches(anon,record,expected)
        if matched:
            finish(record,reads,package,already_published=True);return

    # Bounded anonymous duplicate check before creating or modifying a draft.
    query=require(anon.get(f"{API}/records",params={"q":f'metadata.title:\"{TITLE}\"',"size":100},timeout=60),{200},"duplicate check").json()
    hits=query.get("hits",{});candidates=hits.get("hits",[]);total=hits.get("total",0)
    if isinstance(total,dict):total=total.get("value",0)
    if int(total)>len(candidates):raise RuntimeError("Duplicate check was truncated; refusing a potentially duplicate concept")
    exact=[row for row in candidates if row.get("metadata",{}).get("title")==TITLE]
    for record in exact:
        matched,reads=public_matches(anon,record,expected)
        if matched:
            save_state(phase="existing_public_record_matched",published_record_id=str(record["id"]),published=True)
            finish(record,reads,package,already_published=True);return
    concepts={str(row.get("conceptrecid") or row.get("id")) for row in exact}
    if len(concepts)>1:raise RuntimeError("Multiple public concepts have the exact release title; refusing duplication")

    if not TOKEN_PATH.is_file():raise RuntimeError("Zenodo runtime credential is unavailable")
    token=TOKEN_PATH.read_text(encoding="utf-8").strip()
    if len(token)<40 or any(ch.isspace() for ch in token):raise RuntimeError("Zenodo credential format is invalid")
    auth=auth_session(token)
    draft_id="" if published_id else str(state.get("draft_id", ""))
    if draft_id:
        draft=require(auth.get(f"{API}/deposit/depositions/{draft_id}",timeout=60),{200},"recover draft").json()
        if draft.get("submitted") is not False:raise RuntimeError("Recorded draft has already been submitted without a public record ID")
        draft_title=draft.get("metadata",{}).get("title")
        if draft_title and draft_title!=TITLE:raise RuntimeError("Recorded draft belongs to a different release")
    else:
        owned=require(auth.get(f"{API}/deposit/depositions",params={"q":f'title:\"{TITLE}\"',"size":100},timeout=60),{200},"list matching deposits").json()
        drafts=[row for row in owned if row.get("submitted") is False and row.get("metadata",{}).get("title")==TITLE]
        if len(drafts)>1:raise RuntimeError("Multiple matching drafts exist; refusing duplication")
        if drafts:
            draft=drafts[0];draft_id=str(draft["id"]);save_state(phase="recovered_matching_draft",draft_id=draft_id,published=False)
        elif exact:
            latest=max(exact,key=lambda row:row.get("created",""))
            response=require(auth.post(f"{API}/deposit/depositions/{latest['id']}/actions/newversion",timeout=60),{201,202},"create corrected version")
            draft=require(auth.get(response.json()["links"]["latest_draft"],timeout=60),{200},"read new version draft").json()
            draft_id=str(draft["id"]);save_state(phase="created_new_version",draft_id=draft_id,parent_record_id=str(latest["id"]),published=False)
        else:
            draft=require(auth.post(f"{API}/deposit/depositions",json={},timeout=60),{201},"create deposition").json()
            draft_id=str(draft["id"]);save_state(phase="created_new_concept_draft",draft_id=draft_id,published=False)

    # Replace the complete inherited/draft inventory, never affecting a public parent.
    for item in list(draft.get("files", [])):
        require(auth.delete(f"{API}/deposit/depositions/{draft_id}/files/{item['id']}",timeout=60),{204},f"delete draft file {item.get('filename')}")
    draft=require(auth.get(f"{API}/deposit/depositions/{draft_id}",timeout=60),{200},"read empty draft").json()
    bucket=draft.get("links",{}).get("bucket")
    if not bucket:raise RuntimeError("Draft has no upload bucket")
    save_state(phase="uploading_payload",draft_id=draft_id,published=False)
    for name in sorted(expected):
        with (PAYLOAD/name).open("rb") as stream:
            require(auth.put(f"{bucket.rstrip('/')}/{quote(name,safe='')}",data=stream,
                             headers={"Content-Type":"application/octet-stream"},timeout=300),{200,201},f"upload {name}")
    draft=require(auth.get(f"{API}/deposit/depositions/{draft_id}",timeout=60),{200},"read uploaded draft").json()
    files={row.get("filename") or row.get("key"):row for row in draft.get("files",[])}
    if set(files)!=set(expected):raise RuntimeError("Uploaded draft inventory mismatch")
    for name,row in expected.items():
        if int(files[name].get("filesize",files[name].get("size",-1)))!=row["bytes"]:raise RuntimeError(f"Uploaded size mismatch: {name}")
    draft=require(auth.put(f"{API}/deposit/depositions/{draft_id}",json={"metadata":metadata()},timeout=60),{200},"write metadata").json()
    md=draft.get("metadata",{})
    defects=metadata_defects(md)
    if defects:raise RuntimeError(f"Final draft metadata gate failed: {defects}")
    save_state(phase="validated_pending_publish",draft_id=draft_id,published=False)
    published=require(auth.post(f"{API}/deposit/depositions/{draft_id}/actions/publish",timeout=90),{202},"publish").json()
    record_id=str(published.get("id", ""))
    if not record_id:raise RuntimeError("Publish response did not contain a record ID")
    save_state(phase="published_pending_anonymous_readback",draft_id=draft_id,published_record_id=record_id,published=True)
    auth.headers.pop("Authorization",None);token=""
    record=require(anon.get(f"{API}/records/{record_id}",timeout=60),{200},"anonymous public record readback").json()
    matched,reads=public_matches(anon,record,expected)
    if not matched:raise RuntimeError("Fresh public byte readback failed")
    finish(record,reads,package,already_published=False)


def finish(record, reads, package, already_published):
    md=record.get("metadata",{});defects=metadata_defects(md)
    if len(reads)!=9 or not all(row["pass"] for row in reads):defects.append("public_files")
    if defects:raise RuntimeError(f"Public verification defects: {defects}")
    rid=str(record["id"]);concept=str(record["conceptrecid"])
    receipt={"schema":"o014-english-zenodo-publication-v1","verified_at_utc":datetime.now(timezone.utc).isoformat(),
             "result":"PASS","already_published_when_invoked":already_published,"record_id":rid,"concept_record_id":concept,
             "doi":f"10.5281/zenodo.{rid}","concept_doi":f"10.5281/zenodo.{concept}",
             "public_url":f"https://zenodo.org/records/{rid}","metadata":{"title":TITLE,"version":VERSION,"language":"eng",
             "access_right":"open","license":"cc-by-4.0","creator_count":len(md.get("creators",[])),
             "contributor_count":len(md.get("contributors",[])),"defects":[]},
             "public_files":reads,"total_files":9,"total_bytes":sum(row["bytes"] for row in reads),
             "package_receipt_sha256":sha_file(PACKAGE),"source_commit":"9a5803ff77dd3257484cb177f851a73770a59dd3",
             "source_tree":"23bd05c2fb8434278df4fdfb636559a6a2b0d2ff","credential_material_present":False}
    write_json(RECEIPT,receipt)
    readme = README.read_text(encoding="utf-8")
    doi_line = f"- Archival DOI: <https://doi.org/{receipt['doi']}>"
    updated, count = re.subn(
        r"(?m)^- Archival DOI:.*$", doi_line, readme, count=1
    )
    if count != 1:
        raise RuntimeError("README archival DOI line is missing or ambiguous")
    README.write_text(updated, encoding="utf-8")
    save_state(phase="published_and_anonymous_readback_passed",published_record_id=rid,concept_record_id=concept,
               doi=receipt["doi"],published=True,result="PASS")
    print(json.dumps({"result":"PASS","record_id":rid,"concept_record_id":concept,"doi":receipt["doi"],
                      "files":9,"bytes":receipt["total_bytes"],"receipt_sha256":sha_file(RECEIPT)}))


if __name__ == "__main__": main()
