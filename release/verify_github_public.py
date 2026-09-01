"""Anonymously verify the exact public main and GitHub Pages boundaries."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import time
from urllib.parse import quote

import requests


ROOT = Path(__file__).resolve().parents[1]
OWNER = "KokunoYumeto"
REPO = "methods-of-algebra-volume-2-en"
SLUG = f"{OWNER}/{REPO}"
API = f"https://api.github.com/repos/{SLUG}"
RAW = f"https://raw.githubusercontent.com/{SLUG}"
BASE = f"https://{OWNER.lower()}.github.io/{REPO}/"
PUBLISH = ROOT / "release" / "GITHUB_PUBLICATION_RECEIPT.json"
OUT = ROOT / "release" / "GITHUB_PUBLIC_READBACK.json"
OUT_TMP = ROOT / "release" / "GITHUB_PUBLIC_READBACK.json.tmp"
USER_AGENT = "O014-English-public-verifier/2.0"
MAX_POLL_ATTEMPTS = 12
MAX_FILE_ATTEMPTS = 4


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(ROOT), *args], text=True, encoding="utf-8",
        errors="replace", capture_output=True,
    )
    if completed.returncode:
        raise RuntimeError(f"Narrow local Git read failed: {completed.stderr[-1000:]}")
    return completed.stdout.strip()


def valid_path(value) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and path.as_posix() == value and all(
        part not in ("", ".", "..") for part in path.parts
    )


def load_publication() -> dict:
    try:
        value = json.loads(PUBLISH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read the publication receipt: {exc}") from exc
    if (not isinstance(value, dict)
            or value.get("schema") != "o014-english-github-publication-v2"
            or value.get("result") != "PUSHED_PENDING_ANONYMOUS_READBACK"):
        raise RuntimeError("GitHub publication receipt is not the expected pending v2 boundary")
    return value


def expected_inventory(rows, label: str) -> dict[str, dict]:
    expected = {}
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"{label} inventory is empty or malformed")
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError(f"{label} inventory row is not an object")
        path = row.get("path")
        digest = str(row.get("sha256", "")).lower()
        try:
            size = int(row.get("bytes"))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{label} has an invalid byte count for {path!r}") from exc
        if (not valid_path(path) or path in expected or size <= 0
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None):
            raise RuntimeError(f"{label} has an unsafe, duplicate, empty, or unhashed row: {path!r}")
        expected[path] = {"bytes": size, "sha256": digest}
    return expected


def session() -> requests.Session:
    value = requests.Session()
    value.trust_env = False
    value.headers["User-Agent"] = USER_AGENT
    value.headers["Accept"] = "application/vnd.github+json"
    return value


def retry_delay(response, attempt: int) -> float:
    header = response.headers.get("Retry-After", "") if response is not None else ""
    try:
        requested = float(header)
    except ValueError:
        requested = 0.0
    return min(15.0, max(requested, min(2.0 * (1.6 ** attempt), 15.0)))


def poll_json(url: str, predicate, label: str) -> dict:
    last = "no response"
    with session() as client:
        for attempt in range(MAX_POLL_ATTEMPTS):
            try:
                response = client.get(url, timeout=(20, 90))
                if response.status_code == 200:
                    value = response.json()
                    if predicate(value):
                        return value
                    last = f"HTTP 200 with not-yet-current {label}"
                elif response.status_code in (404, 408, 409, 425, 429) or 500 <= response.status_code < 600:
                    last = f"HTTP {response.status_code}"
                else:
                    response.raise_for_status()
            except (requests.RequestException, ValueError) as exc:
                last = f"{type(exc).__name__}: {exc}"
                response = None
            if attempt + 1 < MAX_POLL_ATTEMPTS:
                time.sleep(retry_delay(response, attempt))
    raise RuntimeError(f"Timed out waiting for {label}: {last}")


def tree_inventory(commit: str, expected_paths: set[str], label: str) -> dict:
    value = poll_json(
        f"{API}/git/trees/{commit}?recursive=1",
        lambda item: isinstance(item, dict) and item.get("truncated") is False
        and {row.get("path") for row in item.get("tree", []) if row.get("type") == "blob"} == expected_paths,
        f"exact {label} tree",
    )
    blobs = {row["path"]: {"git_blob_sha1": row.get("sha"), "bytes": row.get("size")}
             for row in value["tree"] if row.get("type") == "blob"}
    if set(blobs) != expected_paths:
        raise RuntimeError(f"{label} public tree inventory changed during verification")
    return {"tree_sha1": value.get("sha"), "files": len(blobs),
            "git_blob_inventory": blobs}


def fetch_exact(url: str, path: str, expected: dict) -> dict:
    last = None
    with session() as client:
        for attempt in range(MAX_FILE_ATTEMPTS):
            try:
                response = client.get(url, timeout=(20, 120))
                if response.status_code == 200:
                    digest = sha_bytes(response.content)
                    passed = len(response.content) == expected["bytes"] and digest == expected["sha256"]
                    if passed:
                        return {"path": path, "url": response.url, "http_status": 200,
                                "expected_bytes": expected["bytes"], "bytes": len(response.content),
                                "expected_sha256": expected["sha256"], "sha256": digest, "pass": True}
                    last = f"stale bytes={len(response.content)} sha256={digest}"
                elif response.status_code in (404, 408, 409, 425, 429) or 500 <= response.status_code < 600:
                    last = f"HTTP {response.status_code}"
                else:
                    response.raise_for_status()
            except requests.RequestException as exc:
                last = f"{type(exc).__name__}: {exc}"
                response = None
            if attempt + 1 < MAX_FILE_ATTEMPTS:
                time.sleep(retry_delay(response, attempt))
    raise RuntimeError(f"Public byte readback failed for {path}: {last}")


def read_inventory(base: str, expected: dict[str, dict], immutable_ref: str | None = None) -> tuple[list, list]:
    rows = []
    errors = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {}
        for path, identity in expected.items():
            if immutable_ref is None:
                url = base + quote(path, safe="/")
            else:
                url = f"{base}/{immutable_ref}/{quote(path, safe='/')}"
            futures[pool.submit(fetch_exact, url, path, identity)] = path
        for future in as_completed(futures):
            try:
                rows.append(future.result())
            except Exception as exc:  # Persist a sanitized failure receipt.
                errors.append({"path": futures[future], "type": type(exc).__name__, "message": str(exc)})
    rows.sort(key=lambda row: row["path"])
    errors.sort(key=lambda row: row["path"])
    return rows, errors


def atomic_write(value: dict) -> None:
    OUT_TMP.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT_TMP.replace(OUT)


def main() -> None:
    started = datetime.now(timezone.utc).isoformat()
    publication = None
    try:
        publication = load_publication()
        main_head = git("rev-parse", "HEAD")
        main_parent = git("rev-parse", "HEAD^")
        main_tree = git("rev-parse", "HEAD^{tree}")
        if main_parent != publication.get("main_content_commit"):
            raise RuntimeError("Local final main commit is not the receipt commit over the recorded content boundary")

        main_expected = expected_inventory(
            publication.get("main_inventory_excluding_this_receipt"), "main")
        main_receipt_path = "release/GITHUB_PUBLICATION_RECEIPT.json"
        main_expected[main_receipt_path] = {
            "bytes": PUBLISH.stat().st_size, "sha256": sha_file(PUBLISH)}
        pages_expected = expected_inventory(publication.get("pages_inventory"), "Pages")

        repo = poll_json(
            API,
            lambda item: item.get("full_name") == SLUG and item.get("private") is False
            and item.get("default_branch") == "main",
            "public repository metadata",
        )
        main_commit = poll_json(
            f"{API}/commits/main", lambda item: item.get("sha") == main_head,
            "public main tip",
        )
        pages_commit = poll_json(
            f"{API}/commits/gh-pages",
            lambda item: item.get("sha") == publication.get("pages_commit"),
            "public gh-pages tip",
        )
        if main_commit.get("commit", {}).get("tree", {}).get("sha") != main_tree:
            raise RuntimeError("Public main commit has an unexpected tree")

        main_tree_record = tree_inventory(main_head, set(main_expected), "main")
        pages_tree_record = tree_inventory(publication["pages_commit"], set(pages_expected), "gh-pages")

        # Wait for the mutable Pages CDN root to expose the exact new index before
        # reading the remaining files concurrently.
        fetch_exact(BASE + "index.html", "index.html", pages_expected["index.html"])
        main_rows, main_errors = read_inventory(RAW, main_expected, immutable_ref=main_head)
        pages_rows, pages_errors = read_inventory(BASE, pages_expected)

        stable_main = poll_json(
            f"{API}/commits/main", lambda item: item.get("sha") == main_head,
            "stable public main tip",
        )
        stable_pages = poll_json(
            f"{API}/commits/gh-pages",
            lambda item: item.get("sha") == publication.get("pages_commit"),
            "stable public gh-pages tip",
        )
        checks = {
            "publication_boundary": True,
            "repository_public": repo.get("private") is False,
            "repository_exact": repo.get("full_name") == SLUG,
            "main_default_branch": repo.get("default_branch") == "main",
            "main_commit_exact_and_stable": stable_main.get("sha") == main_head,
            "main_tree_exact": main_tree_record["tree_sha1"] == main_tree,
            "main_inventory_exact": len(main_rows) == len(main_expected),
            "main_bytes_exact": not main_errors and all(row["pass"] for row in main_rows),
            "pages_commit_exact_and_stable": stable_pages.get("sha") == publication.get("pages_commit"),
            "pages_tree_exact": pages_tree_record["tree_sha1"]
            == pages_commit.get("commit", {}).get("tree", {}).get("sha"),
            "pages_inventory_exact": len(pages_rows) == len(pages_expected),
            "pages_bytes_exact": not pages_errors and all(row["pass"] for row in pages_rows),
            "root_present": "index.html" in pages_expected,
        }
        errors = main_errors + pages_errors
        result = "PASS" if not errors and all(checks.values()) else "FAIL"
        output = {
            "schema": "o014-english-github-public-readback-v2",
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
            "started_at_utc": started,
            "result": result,
            "repository": f"https://github.com/{SLUG}",
            "pages_url": BASE,
            "main_commit": main_head,
            "main_tree": main_tree,
            "pages_commit": publication["pages_commit"],
            "checks": checks,
            "main_tree_record": main_tree_record,
            "pages_tree_record": pages_tree_record,
            "main_files": main_rows,
            "pages_files": pages_rows,
            "main_file_count": len(main_rows),
            "pages_file_count": len(pages_rows),
            "main_total_bytes": sum(row["bytes"] for row in main_rows),
            "pages_total_bytes": sum(row["bytes"] for row in pages_rows),
            "errors": errors,
            "credentials_used": False,
        }
    except Exception as exc:
        result = "FAIL"
        output = {
            "schema": "o014-english-github-public-readback-v2",
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
            "started_at_utc": started,
            "result": result,
            "repository": f"https://github.com/{SLUG}",
            "pages_url": BASE,
            "checks": {},
            "errors": [{"type": type(exc).__name__, "message": str(exc)}],
            "credentials_used": False,
        }
    atomic_write(output)
    print(json.dumps({"result": result,
                      "main_files": output.get("main_file_count", 0),
                      "pages_files": output.get("pages_file_count", 0),
                      "receipt_sha256": sha_file(OUT),
                      "errors": output.get("errors", [])}))
    if result != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
