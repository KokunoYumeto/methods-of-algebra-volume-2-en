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
import time
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
VERSION = "complete-independent-english-edition-2026-09-01-r2"
DATE = "2026-09-01"
EXPECTED_CONCEPT_RECORD_ID = "22229883"
EXPECTED_PARENT_RECORD_ID = "22229884"
PAYLOAD_NAMES = (
    "00_methods-of-algebra-volume-2-independent-english-edition.pdf",
    "01_complete-xelatex-source.zip",
    "02_semantic-backend.zip",
    "03_offline-html-reader.zip",
    "04_provenance-and-reproducibility.zip",
    "LICENSE", "README.txt", "MANIFEST.csv", "SHA256SUMS.txt",
)
POLL_DELAYS_SECONDS = (0, 1, 2, 4, 8, 16, 30)
TRANSIENT_HTTP_STATUSES = {202, 404, 408, 409, 425, 429, 500, 502, 503, 504}
README_DOI_RE = re.compile(r"(?m)^- Archival DOI:[^\r\n]*(?=\r?$)")


def sha(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def sha_file(path: Path) -> str: return sha(path.read_bytes())


def file_checksums(path: Path):
    sha256_hash = hashlib.sha256()
    try:
        md5_hash = hashlib.md5(usedforsecurity=False)
    except TypeError:  # Python builds predating the usedforsecurity keyword.
        md5_hash = hashlib.md5()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha256_hash.update(chunk);md5_hash.update(chunk)
    return {"sha256": sha256_hash.hexdigest(), "md5": md5_hash.hexdigest()}


def write_json(path: Path, value) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def save_state(**values) -> None:
    current = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    current.update({"schema": "o014-english-zenodo-state-v1", "credential_material_present": False,
                    "updated_at_utc": datetime.now(timezone.utc).isoformat(), **values})
    write_json(STATE, current)


def require(response, codes, phase):
    if response.status_code not in codes:
        raise RuntimeError(f"{phase}: HTTP {response.status_code}: {response.text[:700]}")
    return response


def record_id(value, label, required=False):
    if value is None or value == "":
        if required: raise RuntimeError(f"{label} is missing")
        return ""
    text = str(value).strip()
    if not re.fullmatch(r"[1-9][0-9]*", text):
        raise RuntimeError(f"{label} is not a canonical positive record ID")
    return text


def draft_file_id(value, label):
    text = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", text):
        raise RuntimeError(f"{label} is not a safe draft-file ID")
    return text


def response_object(response, phase):
    try: value = response.json()
    except ValueError as exc: raise RuntimeError(f"{phase}: response was not JSON") from exc
    if not isinstance(value, dict): raise RuntimeError(f"{phase}: response was not a JSON object")
    return value


def preflight_readme_marker(expected_sha256=None):
    raw = README.read_bytes()
    try: text = raw.decode("utf-8")
    except UnicodeDecodeError as exc: raise RuntimeError("README is not valid UTF-8") from exc
    matches = list(README_DOI_RE.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(f"README must contain exactly one archival DOI marker; found {len(matches)}")
    digest = sha(raw)
    if expected_sha256 is not None and digest != expected_sha256:
        raise RuntimeError("README changed after publication preflight; refusing the irreversible publish action")
    return text, digest


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
    for name, row in expected.items():
        path = PAYLOAD / name
        if len(row["sha256"]) != 64 or any(ch not in "0123456789abcdef" for ch in row["sha256"]):
            raise RuntimeError(f"Invalid package checksum: {name}")
        checksums = file_checksums(path)
        if path.stat().st_size != row["bytes"] or checksums["sha256"] != row["sha256"]:
            raise RuntimeError(f"Payload hash drift: {name}")
        row["md5"] = checksums["md5"]
    return expected, package


def metadata(inherited=None):
    if inherited is None:
        merged = {}
    elif isinstance(inherited, dict):
        # A Zenodo new-version draft inherits its parent's metadata.  Start
        # from that complete object so fields not owned by this release lane
        # (including structured subjects and future Zenodo fields) survive.
        merged = dict(inherited)
    else:
        raise RuntimeError("Inherited draft metadata is not a JSON object")
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
    # The legacy deposition API expresses resource type through upload_type
    # and publication_type.  These are the only inherited fields deliberately
    # replaced, together with the other release-owned values below.  In
    # particular, an inherited subjects field is retained because this release
    # does not declare a replacement for it.
    merged.update({
        "upload_type": "publication",
        "publication_type": "book",
        "title": TITLE,
        "creators": [{"name": "Li, Wen-Wei"}],
        "contributors": [{"name": "TTP", "type": "Other"}],
        "description": description,
        "access_right": "open",
        "license": "cc-by-4.0",
        "language": "eng",
        "publication_date": DATE,
        "version": VERSION,
        "keywords": ["linear algebra", "homological algebra", "category theory", "English translation", "open textbook"],
        "related_identifiers": [{
            "identifier": "https://github.com/wenweili/AlJabr-2/tree/9a5803ff77dd3257484cb177f851a73770a59dd3",
            "relation": "isDerivedFrom",
            "scheme": "url",
        }],
    })
    return merged


def metadata_defects(md):
    defects=[];license_value=md.get("license",{})
    description=md.get("description","");plain_description=html.unescape(description)
    if md.get("title")!=TITLE:defects.append("title")
    if md.get("access_right")!="open":defects.append("access_right")
    if (license_value.get("id") if isinstance(license_value,dict) else license_value)!="cc-by-4.0":defects.append("license")
    if md.get("language")!="eng":defects.append("language")
    if md.get("version")!=VERSION:defects.append("version")
    if md.get("publication_date")!=DATE:defects.append("publication_date")
    creators=md.get("creators",[])
    if len(creators)!=1 or creators[0].get("name")!="Li, Wen-Wei":defects.append("creators")
    contributors=md.get("contributors",[])
    if len(contributors)!=1 or contributors[0].get("name")!="TTP" or contributors[0].get("type")!="Other":
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


def row_name(row):
    value = row.get("filename") or row.get("key")
    return value if isinstance(value, str) else ""


def row_size(row):
    for key in ("filesize", "size"):
        if key in row:
            try: return int(row[key])
            except (TypeError, ValueError): return -1
    return -1


def parse_checksum(value):
    raw = str(value or "").strip().lower()
    if ":" in raw:
        algorithm, digest = raw.split(":", 1)
        algorithm = algorithm.replace("-", "")
    elif len(raw) == 32:
        algorithm, digest = "md5", raw
    elif len(raw) == 64:
        algorithm, digest = "sha256", raw
    else:
        return "", ""
    if algorithm not in {"md5", "sha256"} or not re.fullmatch(r"[0-9a-f]+", digest):
        return "", ""
    expected_length = 32 if algorithm == "md5" else 64
    return (algorithm, digest) if len(digest) == expected_length else ("", "")


def draft_file_matches(row, wanted):
    algorithm, digest = parse_checksum(row.get("checksum"))
    return row_size(row) == wanted["bytes"] and algorithm in {"md5", "sha256"} and digest == wanted[algorithm]


def draft_inventory_defects(draft, expected):
    rows = draft.get("files", [])
    if not isinstance(rows, list): return ["files_not_a_list"]
    names = [row_name(row) for row in rows]
    defects=[]
    if len(rows) != len(expected): defects.append("file_count")
    if len(set(names)) != len(names): defects.append("duplicate_filenames")
    if set(names) != set(expected): defects.append("filenames")
    for row in rows:
        name = row_name(row)
        if name in expected and not draft_file_matches(row, expected[name]):
            defects.append(f"checksum_or_size:{name}")
    return defects


def reconcile_draft_inventory(auth, draft_id_value, draft, expected):
    bucket = draft.get("links", {}).get("bucket")
    if not bucket: raise RuntimeError("Draft has no upload bucket")
    keep=set();to_delete=[]
    for item in draft.get("files", []):
        name = row_name(item)
        if name in expected and name not in keep and draft_file_matches(item, expected[name]):
            keep.add(name)
        else:
            item_id = draft_file_id(item.get("id"), f"draft file ID for {name or '<unnamed>'}")
            to_delete.append((item_id, name or "<unnamed>"))
    save_state(phase="reconciling_payload", draft_id=draft_id_value, published=False)
    for item_id, name in to_delete:
        require(auth.delete(f"{API}/deposit/depositions/{draft_id_value}/files/{quote(item_id, safe='')}", timeout=60),
                {204}, f"delete mismatched draft file {name}")
    for name in sorted(set(expected) - keep):
        with (PAYLOAD / name).open("rb") as stream:
            require(auth.put(f"{bucket.rstrip('/')}/{quote(name, safe='')}", data=stream,
                             headers={"Content-Type": "application/octet-stream"}, timeout=300),
                    {200, 201}, f"upload {name}")
    return wait_for_verified_draft_inventory(auth, draft_id_value, expected)


def wait_for_verified_draft_inventory(auth, draft_id_value, expected):
    last = "no request attempted"
    for delay in POLL_DELAYS_SECONDS:
        if delay: time.sleep(delay)
        try:
            response = auth.get(f"{API}/deposit/depositions/{draft_id_value}", timeout=(20, 60))
        except requests.RequestException as exc:
            last = f"transport {type(exc).__name__}";continue
        if response.status_code == 200:
            verified = response_object(response, "read checksum-verified draft")
            defects = draft_inventory_defects(verified, expected)
            if not defects: return verified
            last = str(defects);continue
        if response.status_code not in TRANSIENT_HTTP_STATUSES:
            require(response, {200}, "read checksum-verified draft")
        last = f"HTTP {response.status_code}"
    raise RuntimeError(f"Uploaded draft checksum/size gate failed after bounded polling: {last}")


def record_concept_id(record):
    return record_id(record.get("conceptrecid") or record.get("concept_id"), "concept record ID")


def id_from_record_url(value):
    match = re.search(r"/(?:records|depositions)/([1-9][0-9]*)(?:/|$|[?#])", str(value or ""))
    return match.group(1) if match else ""


def public_file_url(row):
    links = row.get("links", {})
    return links.get("self") or links.get("download") or ""


def public_record_defects(record, expected):
    defects = metadata_defects(record.get("metadata", {}))
    rows = record.get("files", [])
    if not isinstance(rows, list): return defects + ["files_not_a_list"]
    names = [row_name(row) for row in rows]
    if len(rows) != len(expected): defects.append("file_count")
    if len(set(names)) != len(names): defects.append("duplicate_filenames")
    if set(names) != set(expected): defects.append("filenames")
    for row in rows:
        if row_name(row) in expected and not public_file_url(row): defects.append(f"download_link:{row_name(row)}")
    return defects


def wait_for_public_record(session, record_id_value, expected, phase, concept_id=""):
    record_id_value = record_id(record_id_value, f"{phase} record ID", required=True)
    last = "no request attempted"
    for delay in POLL_DELAYS_SECONDS:
        if delay: time.sleep(delay)
        try:
            response = session.get(f"{API}/records/{record_id_value}", timeout=(20, 60))
        except requests.RequestException as exc:
            last = f"transport {type(exc).__name__}"
            continue
        if response.status_code == 200:
            try: candidate = response_object(response, phase)
            except RuntimeError as exc:
                last = str(exc);continue
            try:
                returned_id = record_id(candidate.get("id"), "returned public record ID", required=True)
                candidate_concept = record_concept_id(candidate)
            except RuntimeError as exc:
                last = str(exc);continue
            if returned_id != record_id_value: raise RuntimeError(f"{phase}: Zenodo returned a different record ID")
            defects = public_record_defects(candidate, expected)
            if concept_id and candidate_concept != concept_id: defects.append("concept_lineage")
            if not defects: return candidate
            last = f"public representation incomplete or invalid: {defects}"
            continue
        if response.status_code not in TRANSIENT_HTTP_STATUSES:
            require(response, {200}, phase)
        last = f"HTTP {response.status_code}"
    raise RuntimeError(f"{phase}: bounded same-record propagation wait exhausted ({last})")


def resolve_latest_record(session, records, concept_id_value):
    signals=set()
    for candidate in records:
        if record_concept_id(candidate) != concept_id_value: continue
        if candidate.get("is_latest") is True:
            signals.add(record_id(candidate.get("id"), "latest record ID", required=True))
        latest_link = candidate.get("links", {}).get("latest")
        linked_id = id_from_record_url(latest_link)
        if linked_id: signals.add(linked_id)
    if not signals and len(records) == 1:
        signals.add(record_id(records[0].get("id"), "sole record ID", required=True))
    if len(signals) != 1:
        raise RuntimeError(f"Could not prove one latest public record for concept {concept_id_value}")
    latest_id = signals.pop()
    response = require(session.get(f"{API}/records/{latest_id}", timeout=60), {200}, "read latest concept version")
    latest = response_object(response, "read latest concept version")
    if record_concept_id(latest) != concept_id_value:
        raise RuntimeError("Latest-version link crossed concept lineage")
    if latest.get("metadata", {}).get("title") != TITLE:
        raise RuntimeError("Latest record in the intended concept has a different title")
    return latest


def public_matches(session, record, expected, propagating=False):
    if public_record_defects(record, expected): return False, []
    rows = record.get("files", [])
    files = {row_name(row): row for row in rows}
    reads=[]
    delays = POLL_DELAYS_SECONDS if propagating else (0,)
    for name in sorted(expected):
        wanted = expected[name];remote = files[name]
        remote_bytes = row_size(remote)
        algorithm, digest = parse_checksum(remote.get("checksum"))
        if remote_bytes >= 0 and remote_bytes != wanted["bytes"]: return False, reads
        if algorithm and digest != wanted[algorithm]: return False, reads
        last_read=None;last_error="no request attempted"
        for delay in delays:
            if delay: time.sleep(delay)
            try:
                response = session.get(public_file_url(remote), timeout=(20, 180))
            except requests.RequestException as exc:
                last_error = f"transport {type(exc).__name__}";continue
            if response.status_code == 200:
                data=response.content;actual_sha=sha(data)
                passed=len(data)==wanted["bytes"] and actual_sha==wanted["sha256"]
                last_read={"filename":name,"url":response.url,"http_status":response.status_code,
                           "expected_bytes":wanted["bytes"],"bytes":len(data),"expected_sha256":wanted["sha256"],
                           "sha256":actual_sha,"pass":passed}
                if passed: break
                last_error = "byte count or SHA-256 mismatch"
                if not propagating: return False, reads + [last_read]
                continue
            if response.status_code not in TRANSIENT_HTTP_STATUSES:
                require(response, {200}, f"anonymous download {name}")
            last_error = f"HTTP {response.status_code}"
        if not last_read or not last_read["pass"]:
            if propagating:
                raise RuntimeError(f"anonymous download {name}: bounded readback wait exhausted ({last_error})")
            return False, reads
        reads.append(last_read)
    return True,reads


def validate_state(state):
    if not isinstance(state, dict): raise RuntimeError("Zenodo transaction state is not a JSON object")
    schema = state.get("schema")
    if schema not in (None, "o014-english-zenodo-state-v1"):
        raise RuntimeError(f"Unsupported Zenodo transaction state schema: {schema}")
    for key in ("draft_id", "published_record_id", "parent_record_id", "concept_record_id"):
        record_id(state.get(key), f"state {key}")
    target_version = state.get("target_version")
    if target_version not in (None, VERSION):
        raise RuntimeError("Recorded draft cursor targets a different release version")


def fetch_draft(auth, draft_id_value, phase="read recorded draft"):
    response = require(auth.get(f"{API}/deposit/depositions/{draft_id_value}", timeout=60), {200}, phase)
    draft = response_object(response, phase)
    if record_id(draft.get("id"), "returned draft ID", required=True) != draft_id_value:
        raise RuntimeError(f"{phase}: Zenodo returned a different draft ID")
    return draft


def published_id_from_draft(draft, fallback):
    for key in ("record", "record_html", "latest", "latest_html"):
        found = id_from_record_url(draft.get("links", {}).get(key))
        if found: return found
    explicit = record_id(draft.get("record_id"), "draft public record ID")
    return explicit or record_id(fallback, "draft fallback public record ID", required=True)


def wait_for_submitted_or_public(auth, anon, draft_id_value, expected, concept_id_value):
    last = "no request attempted"
    for delay in POLL_DELAYS_SECONDS:
        if delay: time.sleep(delay)
        try:
            response = auth.get(f"{API}/deposit/depositions/{draft_id_value}", timeout=(20, 60))
        except requests.RequestException as exc:
            last = f"draft transport {type(exc).__name__}"
        else:
            if response.status_code == 200:
                draft = response_object(response, "recover in-flight publish")
                try: returned_draft_id = record_id(draft.get("id"), "returned draft ID", required=True)
                except RuntimeError as exc:
                    last = str(exc);continue
                if returned_draft_id != draft_id_value:
                    raise RuntimeError("In-flight publish recovery returned a different draft")
                if draft.get("submitted") is True: return "submitted", draft
                if draft.get("submitted") is not False:
                    raise RuntimeError("In-flight draft has an indeterminate submitted flag")
                last = "draft is still unsubmitted"
            elif response.status_code not in TRANSIENT_HTTP_STATUSES:
                require(response, {200}, "recover in-flight publish")
            else:
                last = f"draft HTTP {response.status_code}"
        try:
            public_response = anon.get(f"{API}/records/{draft_id_value}", timeout=(20, 60))
        except requests.RequestException as exc:
            last += f"; public transport {type(exc).__name__}"
            continue
        if public_response.status_code == 200:
            candidate = response_object(public_response, "recover in-flight public record")
            try: returned_public_id = record_id(candidate.get("id"), "returned public record ID", required=True)
            except RuntimeError as exc:
                last += f"; {exc}";continue
            if returned_public_id != draft_id_value:
                raise RuntimeError("In-flight recovery returned a different public record")
            defects = public_record_defects(candidate, expected)
            if concept_id_value and record_concept_id(candidate) != concept_id_value:
                defects.append("concept_lineage")
            if not defects: return "public", candidate
            last += f"; public representation incomplete: {defects}"
        elif public_response.status_code not in TRANSIENT_HTTP_STATUSES:
            require(public_response, {200}, "recover in-flight public record")
        else:
            last += f"; public HTTP {public_response.status_code}"
    raise RuntimeError(
        "Recorded publish request remains ambiguous after bounded same-record polling; "
        f"refusing to repeat publish ({last})"
    )


def validate_draft_cursor(draft, draft_id_value, state, existing_concept, latest):
    if draft.get("submitted") is not False: raise RuntimeError("Recorded draft is not editable")
    draft_title = draft.get("metadata", {}).get("title")
    state_phase = str(state.get("phase", ""))
    parent_id = record_id(state.get("parent_record_id"), "state parent record ID")
    state_concept = record_id(state.get("concept_record_id"), "state concept record ID")
    draft_concept = record_concept_id(draft)
    if draft_title and draft_title != TITLE: raise RuntimeError("Recorded draft belongs to a different release")
    if not draft_title:
        recoverable_blank = (
            not existing_concept and not parent_id and state_phase in {
                "created_new_concept_draft", "uploading_payload", "reconciling_payload"
            }
        )
        if not recoverable_blank:
            raise RuntimeError("Recorded blank-title draft cannot be proven to belong to this release")
    if state_concept and draft_concept and state_concept != draft_concept:
        raise RuntimeError("Recorded draft concept conflicts with the durable cursor")
    if existing_concept:
        latest_id = record_id(latest.get("id"), "latest parent record ID", required=True)
        recorded_parent_version = str(state.get("parent_version") or "").strip()
        actual_parent_version = str(latest.get("metadata", {}).get("version") or "").strip()
        if state_concept and state_concept != existing_concept:
            raise RuntimeError("Recorded cursor would cross the intended public concept")
        if draft_concept and draft_concept != existing_concept:
            raise RuntimeError("Recorded draft would cross the intended public concept")
        if parent_id and parent_id != latest_id:
            raise RuntimeError("Recorded correction draft is stale because the public concept advanced")
        if recorded_parent_version and recorded_parent_version != actual_parent_version:
            raise RuntimeError("Recorded correction parent version conflicts with the live public parent")
        if state_phase == "created_new_version" and not parent_id:
            raise RuntimeError("Recorded new-version draft lacks its public parent cursor")
        if not draft_concept and not parent_id and state_concept != existing_concept:
            raise RuntimeError("Recorded draft lacks proof of the intended existing-concept lineage")
    elif parent_id:
        raise RuntimeError("Recorded correction parent is absent from the public title lineage")
    return not bool(draft_title)


def require_distinct_target_version(parent):
    parent_version = str(parent.get("metadata", {}).get("version") or "").strip()
    if not parent_version:
        raise RuntimeError("Latest public parent has no version; correction metadata cannot be made truthful")
    if parent_version == VERSION:
        raise RuntimeError(
            f"Latest public parent already advertises target version {VERSION}; "
            "refusing an indistinguishable correction version"
        )
    return parent_version


def wait_for_new_version_draft(auth, parent_id, action_response):
    try: candidate = response_object(action_response, "create corrected version")
    except RuntimeError: candidate = {}
    last = "new-version response omitted latest_draft"
    for delay in POLL_DELAYS_SECONDS:
        latest_draft = candidate.get("links", {}).get("latest_draft")
        draft_id_value = id_from_record_url(latest_draft)
        if draft_id_value: return fetch_draft(auth, draft_id_value, "read new-version draft")
        if delay: time.sleep(delay)
        response = auth.get(f"{API}/deposit/depositions/{parent_id}", timeout=(20, 60))
        if response.status_code == 200:
            candidate = response_object(response, "observe new-version draft")
            last = "parent deposition still omits latest_draft"
            continue
        if response.status_code not in TRANSIENT_HTTP_STATUSES:
            require(response, {200}, "observe new-version draft")
        last = f"HTTP {response.status_code}"
    raise RuntimeError(
        "New-version action was accepted but its draft cursor did not propagate; "
        f"refusing to repeat the action ({last})"
    )


def main():
    expected, package = expected_inventory()
    _, readme_preflight_sha256 = preflight_readme_marker()
    anon=anonymous_session()
    state=json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    validate_state(state)
    published_id=record_id(state.get("published_record_id"), "state published record ID")
    draft_id=record_id(state.get("draft_id"), "state draft ID")
    state_concept=record_id(state.get("concept_record_id"), "state concept record ID")
    if state_concept != EXPECTED_CONCEPT_RECORD_ID:
        raise RuntimeError(
            f"V2 durable cursor must name concept {EXPECTED_CONCEPT_RECORD_ID}; "
            f"found {state_concept or '<missing>'}"
        )
    if published_id:
        record=wait_for_public_record(anon,published_id,expected,"read recorded public record",state_concept)
        matched,reads=public_matches(anon,record,expected,propagating=True)
        if not matched: raise RuntimeError("Recorded public record failed anonymous byte identity")
        finish(record,reads,package,already_published=True,readme_preflight_sha256=readme_preflight_sha256);return

    # Bounded anonymous duplicate check before creating or modifying a draft.
    query=response_object(require(anon.get(f"{API}/records",params={"q":f'metadata.title:\"{TITLE}\"',"size":25},timeout=60),
                                  {200},"duplicate check"), "duplicate check")
    hits=query.get("hits",{});candidates=hits.get("hits",[]);total=hits.get("total",0)
    if isinstance(total,dict):total=total.get("value",0)
    if int(total)>len(candidates):raise RuntimeError("Duplicate check was truncated; refusing a potentially duplicate concept")
    exact=[row for row in candidates if row.get("metadata",{}).get("title")==TITLE]
    concepts={record_concept_id(row) for row in exact}
    if "" in concepts: raise RuntimeError("A matching public record lacks a concept ID")
    if len(concepts)>1:raise RuntimeError("Multiple public concepts have the exact release title; refusing duplication")
    existing_concept=next(iter(concepts), "")
    if existing_concept != EXPECTED_CONCEPT_RECORD_ID:
        raise RuntimeError(
            f"Exact-title duplicate check did not prove intended concept {EXPECTED_CONCEPT_RECORD_ID}"
        )
    if state_concept and existing_concept and state_concept != existing_concept:
        raise RuntimeError("Durable cursor conflicts with the existing public concept")
    if state_concept and not existing_concept and not draft_id:
        raise RuntimeError("Durable cursor names a public concept that the exact-title preflight could not find")
    latest=resolve_latest_record(anon,exact,existing_concept) if existing_concept else None
    if latest:
        latest_id=record_id(latest.get("id"), "latest record ID", required=True)
        propagating = bool(draft_id and draft_id == latest_id and str(state.get("phase", "")).startswith("publish"))
        if propagating:
            latest=wait_for_public_record(anon,latest_id,expected,"resume public propagation",existing_concept)
        matched,reads=public_matches(anon,latest,expected,propagating=propagating)
        if matched:
            save_state(phase="existing_public_record_matched",published_record_id=latest_id,
                       concept_record_id=existing_concept,published=True)
            finish(latest,reads,package,already_published=True,
                   readme_preflight_sha256=readme_preflight_sha256);return
        if propagating:
            raise RuntimeError("Propagated public record does not match the intended release bytes")

    if not TOKEN_PATH.is_file():raise RuntimeError("Zenodo runtime credential is unavailable")
    token=TOKEN_PATH.read_text(encoding="utf-8").strip()
    if len(token)<40 or any(ch.isspace() for ch in token):raise RuntimeError("Zenodo credential format is invalid")
    auth=auth_session(token)
    if draft_id:
        state_phase = str(state.get("phase", ""))
        if state_phase == "publish_request_in_flight":
            kind, recovered = wait_for_submitted_or_public(auth, anon, draft_id, expected, existing_concept)
            if kind == "public":
                record=recovered
                record_concept=record_concept_id(record)
                save_state(phase="published_pending_anonymous_readback",published_record_id=draft_id,
                           concept_record_id=record_concept,published=True)
                matched,reads=public_matches(anon,record,expected,propagating=True)
                if not matched:raise RuntimeError("Recovered public record failed anonymous byte identity")
                token="";auth.headers.pop("Authorization",None)
                finish(record,reads,package,already_published=False,
                       readme_preflight_sha256=readme_preflight_sha256);return
            draft=recovered
        else:
            draft=fetch_draft(auth,draft_id)
        if draft.get("submitted") is True:
            recovered_id=published_id_from_draft(draft,draft_id)
            save_state(phase="published_pending_anonymous_readback",draft_id=draft_id,
                       published_record_id=recovered_id,published=True)
            record=wait_for_public_record(anon,recovered_id,expected,"recover submitted draft",existing_concept)
            matched,reads=public_matches(anon,record,expected,propagating=True)
            if not matched:raise RuntimeError("Recovered submitted draft failed anonymous byte identity")
            token="";auth.headers.pop("Authorization",None)
            finish(record,reads,package,already_published=False,
                   readme_preflight_sha256=readme_preflight_sha256);return
        needs_identity_metadata = validate_draft_cursor(draft,draft_id,state,existing_concept,latest)
        if latest: parent_version=require_distinct_target_version(latest)
        else: parent_version=""
        if needs_identity_metadata:
            draft=response_object(require(auth.put(f"{API}/deposit/depositions/{draft_id}",
                                                   json={"metadata":metadata(draft.get("metadata"))},timeout=60),
                                          {200},"identify recovered blank draft"), "identify recovered blank draft")
    else:
        owned_response=require(auth.get(f"{API}/deposit/depositions",params={"q":f'title:\"{TITLE}\"',"size":100},timeout=60),
                               {200},"list matching deposits")
        try: owned=owned_response.json()
        except ValueError as exc: raise RuntimeError("Matching-deposit response was not JSON") from exc
        if not isinstance(owned,list):raise RuntimeError("Matching-deposit response was not a list")
        drafts=[row for row in owned if row.get("submitted") is False and row.get("metadata",{}).get("title")==TITLE]
        wrong_lineage=[row for row in drafts if existing_concept and record_concept_id(row)!=existing_concept]
        if wrong_lineage:raise RuntimeError("A matching draft exists outside the intended public concept")
        drafts=[row for row in drafts if not existing_concept or record_concept_id(row)==existing_concept]
        if len(drafts)>1:raise RuntimeError("Multiple matching drafts exist; refusing duplication")
        if drafts:
            draft=drafts[0];draft_id=record_id(draft.get("id"),"recovered matching draft ID",required=True)
            save_state(phase="recovered_matching_draft",draft_id=draft_id,
                       concept_record_id=record_concept_id(draft) or None,target_version=VERSION,published=False)
        elif latest:
            parent_id=record_id(latest.get("id"),"latest parent record ID",required=True)
            recorded_parent_id=record_id(state.get("parent_record_id"),
                                         "state parent record ID",required=True)
            if recorded_parent_id != EXPECTED_PARENT_RECORD_ID:
                raise RuntimeError(
                    f"V2 durable cursor must name parent {EXPECTED_PARENT_RECORD_ID}; "
                    f"found {recorded_parent_id}"
                )
            if parent_id != recorded_parent_id:
                raise RuntimeError(
                    f"Live latest record {parent_id} does not equal recorded parent {recorded_parent_id}; "
                    "refusing to create a new-version draft"
                )
            parent_version=require_distinct_target_version(latest)
            response=require(auth.post(f"{API}/deposit/depositions/{parent_id}/actions/newversion",timeout=60),
                             {201,202},"create corrected version")
            draft=wait_for_new_version_draft(auth,parent_id,response)
            draft_id=record_id(draft.get("id"),"new-version draft ID",required=True)
            save_state(phase="created_new_version",draft_id=draft_id,parent_record_id=parent_id,
                       parent_version=parent_version,concept_record_id=existing_concept,
                       target_version=VERSION,published=False)
        else:
            draft=response_object(require(auth.post(f"{API}/deposit/depositions",json={"metadata":metadata()},timeout=60),
                                          {201},"create deposition"), "create deposition")
            draft_id=record_id(draft.get("id"),"new-concept draft ID",required=True)
            save_state(phase="created_new_concept_draft",draft_id=draft_id,parent_record_id=None,
                       parent_version=None,concept_record_id=record_concept_id(draft) or None,
                       target_version=VERSION,published=False)
        validate_draft_cursor(draft,draft_id,{**state,"phase":"recovered_matching_draft",
                                             "concept_record_id":record_concept_id(draft) or existing_concept},
                              existing_concept,latest)
        if latest: parent_version=require_distinct_target_version(latest)
        else: parent_version=""

    draft=reconcile_draft_inventory(auth,draft_id,draft,expected)
    draft=response_object(require(auth.put(f"{API}/deposit/depositions/{draft_id}",
                                           json={"metadata":metadata(draft.get("metadata"))},timeout=60),
                                  {200},"write metadata"), "write metadata")
    draft=wait_for_verified_draft_inventory(auth,draft_id,expected)
    md=draft.get("metadata",{})
    defects=metadata_defects(md)
    if defects:raise RuntimeError(f"Final draft metadata gate failed: {defects}")
    inventory_defects=draft_inventory_defects(draft,expected)
    if inventory_defects:raise RuntimeError(f"Final draft checksum/size gate failed: {inventory_defects}")
    final_concept=record_concept_id(draft)
    if existing_concept and final_concept!=existing_concept:
        raise RuntimeError("Final draft crossed the intended existing-concept lineage")
    preflight_readme_marker(readme_preflight_sha256)
    save_state(phase="validated_pending_publish",draft_id=draft_id,parent_version=parent_version or None,
               concept_record_id=existing_concept or final_concept or None,target_version=VERSION,published=False)
    save_state(phase="publish_request_in_flight",draft_id=draft_id,published=False)
    publish_response=require(auth.post(f"{API}/deposit/depositions/{draft_id}/actions/publish",timeout=90),{202},"publish")
    try: published=publish_response.json()
    except ValueError: published={}
    if not isinstance(published,dict):published={}
    returned_id=published.get("record_id") or published.get("id")
    published_record_id=record_id(returned_id,"publish response record ID") if returned_id else draft_id
    save_state(phase="published_pending_anonymous_readback",draft_id=draft_id,
               published_record_id=published_record_id,concept_record_id=existing_concept or final_concept or None,
               published=True)
    auth.headers.pop("Authorization",None);token=""
    record=wait_for_public_record(anon,published_record_id,expected,"anonymous public record readback",existing_concept)
    matched,reads=public_matches(anon,record,expected,propagating=True)
    if not matched:raise RuntimeError("Fresh public byte readback failed")
    finish(record,reads,package,already_published=False,readme_preflight_sha256=readme_preflight_sha256)


def finish(record, reads, package, already_published, readme_preflight_sha256):
    md=record.get("metadata",{});defects=metadata_defects(md)
    if len(reads)!=9 or not all(row["pass"] for row in reads):defects.append("public_files")
    if defects:raise RuntimeError(f"Public verification defects: {defects}")
    readme,_=preflight_readme_marker(readme_preflight_sha256)
    rid=record_id(record.get("id"),"final public record ID",required=True)
    concept=record_concept_id(record)
    if not concept:raise RuntimeError("Final public record lacks a concept ID")
    receipt={"schema":"o014-english-zenodo-publication-v1","verified_at_utc":datetime.now(timezone.utc).isoformat(),
             "result":"PASS","already_published_when_invoked":already_published,"record_id":rid,"concept_record_id":concept,
             "doi":f"10.5281/zenodo.{rid}","concept_doi":f"10.5281/zenodo.{concept}",
             "public_url":f"https://zenodo.org/records/{rid}","metadata":{"title":TITLE,"version":VERSION,"language":"eng",
             "access_right":"open","license":"cc-by-4.0","creator_count":len(md.get("creators",[])),
             "contributor_count":len(md.get("contributors",[])),"defects":[]},
             "public_files":reads,"total_files":9,"total_bytes":sum(row["bytes"] for row in reads),
             "package_receipt_sha256":sha_file(PACKAGE),"source_commit":"9a5803ff77dd3257484cb177f851a73770a59dd3",
             "source_tree":"23bd05c2fb8434278df4fdfb636559a6a2b0d2ff","credential_material_present":False}
    doi_line = f"- Archival DOI: <https://doi.org/{receipt['doi']}>"
    updated,count=README_DOI_RE.subn(doi_line,readme,count=1)
    if count != 1:
        raise RuntimeError("README archival DOI line is missing or ambiguous")
    README.write_bytes(updated.encode("utf-8"))
    write_json(RECEIPT,receipt)
    save_state(phase="published_and_anonymous_readback_passed",published_record_id=rid,concept_record_id=concept,
               doi=receipt["doi"],published=True,result="PASS")
    print(json.dumps({"result":"PASS","record_id":rid,"concept_record_id":concept,"doi":receipt["doi"],
                      "files":9,"bytes":receipt["total_bytes"],"receipt_sha256":sha_file(RECEIPT)}))


if __name__ == "__main__": main()
