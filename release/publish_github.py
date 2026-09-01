"""Publish the final verified English corpus and Pages reader to one public repo.

All Git commands are scoped to this small English lane.  The final boundary is
an exact allowlist, and ``release/staging`` is never admitted to the Git tree.
The gh-pages update uses an exact force-with-lease.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
OWNER = "KokunoYumeto"
REPO = "methods-of-algebra-volume-2-en"
SLUG = f"{OWNER}/{REPO}"
RECEIPT_REL = "release/GITHUB_PUBLICATION_RECEIPT.json"
RECEIPT = ROOT / RECEIPT_REL
PDF_REL = "output/pdf/methods-of-algebra-volume-2-independent-english-edition.pdf"
SOURCE_COMMIT = "9a5803ff77dd3257484cb177f851a73770a59dd3"
SOURCE_TREE = "23bd05c2fb8434278df4fdfb636559a6a2b0d2ff"

GATE_PATHS = (
    "qa/PDF_BUILD_RECEIPT.json",
    "qa/HTML_BUILD_RECEIPT.json",
    "qa/HTML_BROWSER_QA.json",
    "backend/BACKEND_VALIDATION.json",
    "release/staging/PACKAGE_RECEIPT.json",
    "release/ZENODO_PUBLICATION_RECEIPT.json",
)
PAYLOAD_NAMES = (
    "00_methods-of-algebra-volume-2-independent-english-edition.pdf",
    "01_complete-xelatex-source.zip",
    "02_semantic-backend.zip",
    "03_offline-html-reader.zip",
    "04_provenance-and-reproducibility.zip",
    "LICENSE",
    "README.txt",
    "MANIFEST.csv",
    "SHA256SUMS.txt",
)

# These directory roots, plus the individually named release files, are the
# complete intended main-branch boundary.  In particular, release/staging and
# the private Zenodo transaction state are outside it.
PUBLISH_ROOTS = ("backend", "controls", "qa", "reader", "source/en", "tools")
PUBLISH_FILES = (
    ".gitattributes",
    ".gitignore",
    "README.md",
    PDF_REL,
    "release/publish_github.py",
    "release/publish_zenodo.py",
    "release/verify_github_public.py",
    "release/ZENODO_PUBLICATION_RECEIPT.json",
    RECEIPT_REL,
    "release/GITHUB_PUBLIC_READBACK_CHECKPOINT_HTML_ONLY.json",
    # Optional at publication time.  If an older generic receipt is tracked
    # but absent locally, scoped `git add --all` removes it from the final tree;
    # the final verifier writes a fresh local generic receipt after publication.
    "release/GITHUB_PUBLIC_READBACK.json",
)
FORBIDDEN_PREFIXES = ("release/staging/", "reader/build/")
FORBIDDEN_DIRECTORY_NAMES = {"__pycache__"}
README_PENDING = (
    "Public release status: complete HTML reader, editable source, and modular\n"
    "backend checkpoint; the PDF and Zenodo archive are pending the serialized TeX\n"
    "build."
)
README_FINAL = (
    "Public release status: complete PDF and HTML readers, editable source,\n"
    "modular backend, and published Zenodo archive."
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, check=True):
    process = subprocess.run(
        args, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True
    )
    if check and process.returncode:
        detail = (process.stderr or process.stdout)[-1000:]
        raise RuntimeError(f"{args[0]} {args[1] if len(args) > 1 else ''}: {detail}")
    return process


def git(*args) -> str:
    return run(["git", "-C", str(ROOT), *args]).stdout.strip()


def split_nul(value: str) -> list[str]:
    return [part for part in value.split("\0") if part]


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def repo_file(rel: str, label: str = "file") -> Path:
    if not isinstance(rel, str) or not rel or "\\" in rel or Path(rel).is_absolute():
        raise RuntimeError(f"Invalid repository-relative {label} path: {rel!r}")
    path = (ROOT / rel).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise RuntimeError(f"{label} escapes the repository: {rel}") from exc
    if not path.is_file():
        raise RuntimeError(f"Required {label} is missing: {rel}")
    return path


def load_json(rel: str) -> dict:
    path = repo_file(rel, "JSON receipt")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read JSON receipt {rel}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON receipt is not an object: {rel}")
    return value


def valid_sha256(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value.lower()) is not None


def require_identity(rel, expected_bytes, expected_sha256, label):
    path = repo_file(rel, label)
    if not valid_sha256(expected_sha256):
        raise RuntimeError(f"{label} has an invalid recorded SHA-256: {rel}")
    try:
        size = int(expected_bytes)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{label} has an invalid recorded byte count: {rel}") from exc
    actual = (path.stat().st_size, sha(path))
    expected = (size, expected_sha256.lower())
    if actual != expected:
        raise RuntimeError(f"Current {label} bytes do not match its receipt: {rel}")
    return path


def validate_html_dist(html: dict) -> dict[str, tuple[int, str]]:
    dist = ROOT / "reader" / "dist"
    manifest = repo_file("reader/dist/SHA256SUMS.txt", "HTML manifest")
    claimed = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\\]+)", line)
        if not match or match.group(2) in claimed:
            raise RuntimeError("HTML SHA256SUMS.txt is malformed or contains duplicates")
        rel = match.group(2)
        path = (dist / rel).resolve()
        try:
            path.relative_to(dist.resolve())
        except ValueError as exc:
            raise RuntimeError(f"HTML manifest path escapes dist: {rel}") from exc
        if not path.is_file() or sha(path) != match.group(1):
            raise RuntimeError(f"HTML manifest does not match current bytes: {rel}")
        claimed[rel] = (path.stat().st_size, match.group(1))
    current = sorted(path for path in dist.rglob("*") if path.is_file())
    names = {path.relative_to(dist).as_posix() for path in current}
    if names != set(claimed) | {"SHA256SUMS.txt"}:
        raise RuntimeError("Current HTML dist inventory differs from SHA256SUMS.txt")
    if len(current) != int(html.get("dist_files", -1)):
        raise RuntimeError("Current HTML dist file count differs from its PASS receipt")
    if sum(path.stat().st_size for path in current) != int(html.get("dist_bytes", -1)):
        raise RuntimeError("Current HTML dist byte count differs from its PASS receipt")
    return claimed


def validate_publication_boundary(gates: dict[str, dict]) -> dict[str, dict]:
    pdf = gates["qa/PDF_BUILD_RECEIPT.json"]
    html = gates["qa/HTML_BUILD_RECEIPT.json"]
    browser = gates["qa/HTML_BROWSER_QA.json"]
    backend = gates["backend/BACKEND_VALIDATION.json"]
    package = gates["release/staging/PACKAGE_RECEIPT.json"]
    zenodo = gates["release/ZENODO_PUBLICATION_RECEIPT.json"]

    if any(gate.get("result") != "PASS" for gate in gates.values()):
        raise RuntimeError("Every PDF/HTML/browser/backend/package/Zenodo gate must be PASS")
    source_ids = {(pdf.get("source_commit"), pdf.get("source_tree")),
                  (html.get("source_commit"), html.get("source_tree"))}
    if source_ids != {(SOURCE_COMMIT, SOURCE_TREE)}:
        raise RuntimeError("Build receipts do not share the frozen source identity")

    if pdf.get("pdf") != PDF_REL:
        raise RuntimeError("PDF receipt names an unexpected output")
    require_identity(PDF_REL, pdf.get("pdf_bytes"), pdf.get("pdf_sha256"), "PDF")
    master = repo_file(pdf.get("master"), "PDF master")
    require_identity(pdf.get("master"), master.stat().st_size, pdf.get("master_sha256"), "PDF master")

    if html.get("validation", {}).get("status") != "pass" or html.get("validation", {}).get("errors"):
        raise RuntimeError("HTML static validation is not a clean pass")
    require_identity("reader/dist/index.html", html.get("index_bytes"), html.get("index_sha256"), "HTML index")
    validate_html_dist(html)

    if browser.get("target") != "reader/dist/index.html":
        raise RuntimeError("Browser QA targets an unexpected reader")
    require_identity(browser["target"], browser.get("target_bytes"), browser.get("target_sha256"), "browser-QA target")
    build_receipt = browser.get("build_receipt", {})
    if build_receipt.get("path") != "qa/HTML_BUILD_RECEIPT.json":
        raise RuntimeError("Browser QA does not bind the canonical HTML receipt")
    require_identity(build_receipt["path"], build_receipt.get("bytes"), build_receipt.get("sha256"),
                     "browser-QA HTML receipt")
    assets = browser.get("local_links_and_assets", {})
    if assets.get("manifest_path") != "reader/dist/SHA256SUMS.txt":
        raise RuntimeError("Browser QA does not bind the canonical HTML manifest")
    require_identity(assets["manifest_path"], assets.get("manifest_bytes"), assets.get("manifest_sha256"),
                     "browser-QA HTML manifest")
    static = browser.get("static_validation", {})
    require_identity(static.get("path"), static.get("bytes"), static.get("sha256"),
                     "browser-QA static validation")
    if any(int(assets.get(key, -1)) != 0 for key in
           ("http_failures", "byte_or_sha256_mismatches", "browser_console_warnings_or_errors")):
        raise RuntimeError("Browser QA contains HTTP, byte, or console defects")

    expected_backend = {
        "units.jsonl", "segments.jsonl", "terms.csv", "figure-alt-text-en.csv", "bridges.jsonl"
    }
    artifacts = backend.get("artifacts", {})
    if set(artifacts) != expected_backend or not all(value is True for value in backend.get("checks", {}).values()):
        raise RuntimeError("Backend PASS receipt has a non-canonical inventory or failed check")
    for name, row in artifacts.items():
        require_identity(f"backend/{name}", row.get("bytes"), row.get("sha256"), "backend artifact")
    if int(backend.get("term_unresolved_count", -1)) != 0 or backend.get("index_alignment_mismatches"):
        raise RuntimeError("Backend receipt contains unresolved terms or index mismatches")

    package_rows = package.get("files", [])
    if len(package_rows) != len(PAYLOAD_NAMES):
        raise RuntimeError("Package receipt is not an exact nine-file boundary")
    expected = {}
    for row in package_rows:
        name = row.get("filename")
        if name in expected or name not in PAYLOAD_NAMES:
            raise RuntimeError(f"Package receipt has a duplicate or unexpected file: {name!r}")
        require_identity(f"release/staging/payload/{name}", row.get("bytes"), row.get("sha256"),
                         "package payload")
        expected[name] = (int(row["bytes"]), row["sha256"].lower())
    if set(expected) != set(PAYLOAD_NAMES):
        raise RuntimeError("Package receipt inventory is non-canonical")

    package_path = repo_file("release/staging/PACKAGE_RECEIPT.json", "package receipt")
    if zenodo.get("package_receipt_sha256") != sha(package_path):
        raise RuntimeError("Zenodo receipt does not bind the current package receipt")
    public_rows = zenodo.get("public_files", [])
    public = {}
    for row in public_rows:
        name = row.get("filename")
        if row.get("pass") is not True or name in public:
            raise RuntimeError("Zenodo public-file receipt contains a failure or duplicate")
        public[name] = (int(row.get("bytes", -1)), str(row.get("sha256", "")).lower())
    if public != expected or int(zenodo.get("total_files", -1)) != len(PAYLOAD_NAMES):
        raise RuntimeError("Zenodo public-byte receipt does not match the current package")
    if int(zenodo.get("total_bytes", -1)) != sum(size for size, _ in expected.values()):
        raise RuntimeError("Zenodo public-byte total does not match the current package")
    metadata = zenodo.get("metadata", {})
    if metadata.get("access_right") != "open" or metadata.get("license") != "cc-by-4.0" or metadata.get("defects"):
        raise RuntimeError("Zenodo metadata is not an open, defect-free CC BY 4.0 boundary")
    if zenodo.get("credential_material_present") is not False:
        raise RuntimeError("Zenodo receipt does not explicitly exclude credential material")

    return {
        rel: {"bytes": repo_file(rel, "gate receipt").stat().st_size,
              "sha256": sha(repo_file(rel, "gate receipt")), "result": gate["result"]}
        for rel, gate in gates.items()
    }


def update_readme_marker() -> None:
    readme = repo_file("README.md", "README")
    text = readme.read_text(encoding="utf-8")
    pending_count = text.count(README_PENDING)
    final_count = text.count(README_FINAL)
    if pending_count == 1 and final_count == 0:
        readme.write_text(text.replace(README_PENDING, README_FINAL, 1), encoding="utf-8")
    elif pending_count == 0 and final_count == 1:
        return
    else:
        raise RuntimeError("README release-status marker is missing, conflicting, or ambiguous")


def is_forbidden_path(rel: str) -> bool:
    return (
        any(rel.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)
        or any(part in FORBIDDEN_DIRECTORY_NAMES for part in Path(rel).parts)
        or rel.endswith(".pyc")
    )


def is_allowed_path(rel: str) -> bool:
    return (rel in PUBLISH_FILES or
            any(rel == root or rel.startswith(root + "/") for root in PUBLISH_ROOTS)) and not is_forbidden_path(rel)


def local_allowlist() -> set[str]:
    files = set()
    required = set(PUBLISH_FILES) - {RECEIPT_REL, "release/GITHUB_PUBLIC_READBACK.json"}
    for rel in PUBLISH_FILES:
        path = ROOT / rel
        if path.exists():
            if path.is_symlink() or not path.is_file():
                raise RuntimeError(f"Intended repository file is not a regular file: {rel}")
            files.add(rel)
    missing = sorted(rel for rel in required if rel not in files)
    if missing:
        raise RuntimeError(f"Required publication files are missing: {missing}")
    for root in PUBLISH_ROOTS:
        directory = ROOT / root
        if not directory.is_dir():
            raise RuntimeError(f"Required publication directory is missing: {root}")
        for path in directory.rglob("*"):
            rel = relative(path)
            if is_forbidden_path(rel):
                continue
            if path.is_symlink():
                raise RuntimeError(f"Symlinks are not admitted to the publication boundary: {rel}")
            if path.is_file():
                files.add(rel)
    forbidden = sorted(rel for rel in files if not is_allowed_path(rel))
    if forbidden:
        raise RuntimeError(f"Publication allowlist admitted forbidden paths: {forbidden}")
    return files


def ensure_git_repository() -> None:
    if not (ROOT / ".git").exists():
        run(["git", "init", "-b", "main", str(ROOT)])
        git("config", "user.name", "OpenAI Codex")
        git("config", "user.email", "codex@openai.com")
    top = Path(git("rev-parse", "--show-toplevel")).resolve()
    if top != ROOT.resolve():
        raise RuntimeError(f"Refusing Git repository rooted outside this release lane: {top}")
    branch = git("symbolic-ref", "--quiet", "--short", "HEAD")
    if branch != "main":
        raise RuntimeError(f"Refusing detached or unexpected publication branch: {branch!r}")


def tracked_allowlisted() -> set[str]:
    specs = [*PUBLISH_ROOTS, *PUBLISH_FILES]
    values = split_nul(git("ls-files", "-z", "--", *specs))
    if any(not is_allowed_path(rel) for rel in values):
        raise RuntimeError("Git returned a path outside the explicit publication allowlist")
    return set(values)


def staged_paths() -> set[str]:
    return set(split_nul(git("diff", "--cached", "--name-only", "--no-renames", "-z")))


def stage_content() -> set[str]:
    clean = run(["git", "-C", str(ROOT), "diff", "--cached", "--quiet"], check=False)
    if clean.returncode not in (0, 1):
        raise RuntimeError(f"Cannot inspect the Git index: {clean.stderr[-1000:]}")
    if clean.returncode == 1:
        raise RuntimeError("Refusing publication with pre-existing staged changes")
    allowed = local_allowlist()
    stage = sorted(allowed | tracked_allowlisted())
    for offset in range(0, len(stage), 75):
        git("add", "--all", "--", *stage[offset:offset + 75])
    staged = staged_paths()
    invalid = sorted(rel for rel in staged if not is_allowed_path(rel))
    if invalid or any(rel.startswith("release/staging/") for rel in staged):
        raise RuntimeError(f"Staged inventory escaped the publication allowlist: {invalid}")
    return allowed


def tree_paths(commit: str) -> set[str]:
    return set(split_nul(git("ls-tree", "-r", "--name-only", "-z", commit)))


def assert_tree(commit: str, expected: set[str]) -> None:
    actual = tree_paths(commit)
    if actual != expected:
        raise RuntimeError(
            f"Git tree inventory mismatch; missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )
    if any(rel.startswith("release/staging/") for rel in actual):
        raise RuntimeError("release/staging is forbidden in the published Git tree")


def git_blob_bytes(commit: str, rel: str) -> bytes:
    process = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{commit}:{rel}"],
        cwd=ROOT,
        capture_output=True,
    )
    if process.returncode:
        raise RuntimeError(f"Cannot read committed Git blob {commit}:{rel}")
    return process.stdout


def inventory(paths: set[str], commit: str | None = None) -> list[dict]:
    rows = []
    for rel in sorted(paths):
        if commit is None:
            path = repo_file(rel, "publication inventory file")
            data = path.read_bytes()
        else:
            data = git_blob_bytes(commit, rel)
        rows.append({"path": rel, "bytes": len(data),
                     "sha256": hashlib.sha256(data).hexdigest()})
    return rows


def api_is_404(process) -> bool:
    detail = f"{process.stdout}\n{process.stderr}"
    return re.search(r"(?i)(?:HTTP\s*404\b|\b404\s+Not Found\b|[\"']status[\"']\s*:\s*404\b)", detail) is not None


def gh_api_json(endpoint: str, missing_ok=False):
    process = run(["gh", "api", endpoint], check=False)
    if process.returncode:
        if missing_ok and api_is_404(process):
            return None
        raise RuntimeError(f"GitHub API failure for {endpoint}: {(process.stderr or process.stdout)[-1000:]}")
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"GitHub API returned invalid JSON for {endpoint}") from exc


def ensure_public_repository() -> None:
    repo = gh_api_json(f"repos/{SLUG}", missing_ok=True)
    if repo is None:
        run([
            "gh", "repo", "create", SLUG, "--public", "--source", str(ROOT), "--remote", "origin",
            "--description", "Independent English edition of Wen-Wei Li's Methods of Algebra, Volume 2 (CC BY 4.0)",
        ])
        repo = gh_api_json(f"repos/{SLUG}")
    if repo.get("full_name") != SLUG:
        raise RuntimeError("GitHub repository identity mismatch")
    if repo.get("private") is not False:
        run(["gh", "repo", "edit", SLUG, "--visibility", "public", "--accept-visibility-change-consequences"])
        repo = gh_api_json(f"repos/{SLUG}")
        if repo.get("private") is not False:
            raise RuntimeError("GitHub repository did not become public")


def validate_push_route() -> None:
    branch = git("symbolic-ref", "--quiet", "--short", "HEAD")
    if branch != "main":
        raise RuntimeError(f"Publication push is not on main: {branch!r}")
    remotes = git("remote").splitlines()
    if "origin" not in remotes:
        git("remote", "add", "origin", f"https://github.com/{SLUG}.git")
    allowed = {
        f"https://github.com/{SLUG}.git",
        f"https://github.com/{SLUG}",
        f"git@github.com:{SLUG}.git",
        f"git@github.com:{SLUG}",
        f"ssh://git@github.com/{SLUG}.git",
        f"ssh://git@github.com/{SLUG}",
    }
    fetch_urls = git("remote", "get-url", "--all", "origin").splitlines()
    push_urls = git("remote", "get-url", "--push", "--all", "origin").splitlines()
    if len(fetch_urls) != 1 or len(push_urls) != 1:
        raise RuntimeError("origin must have exactly one fetch URL and one push URL")
    if fetch_urls[0].rstrip("/") not in allowed or push_urls[0].rstrip("/") not in allowed:
        raise RuntimeError(f"Refusing unexpected origin route: fetch={fetch_urls}, push={push_urls}")


def configure_pages() -> None:
    current = gh_api_json(f"repos/{SLUG}/pages", missing_ok=True)
    method = "POST" if current is None else "PUT"
    configured = run([
        "gh", "api", "--method", method, f"repos/{SLUG}/pages", "-f", "build_type=legacy",
        "-f", "source[branch]=gh-pages", "-f", "source[path]=/",
    ], check=False)
    if configured.returncode:
        page = gh_api_json(f"repos/{SLUG}/pages")
        source = page.get("source", {})
        if not (page.get("public") is True and page.get("build_type") == "legacy" and
                source.get("branch") == "gh-pages" and source.get("path") == "/"):
            raise RuntimeError(f"GitHub Pages configuration failed: {configured.stderr[-1000:]}")


def main() -> None:
    gates = {rel: load_json(rel) for rel in GATE_PATHS}
    gate_receipts = validate_publication_boundary(gates)
    update_readme_marker()
    ensure_git_repository()

    allowed = stage_content()
    if staged_paths():
        git("commit", "-m", "Publish complete independent English edition")
    allowed = local_allowlist()
    assert_tree("HEAD", allowed)
    diff = run(["git", "-C", str(ROOT), "diff", "--quiet", "--", *PUBLISH_ROOTS, *PUBLISH_FILES],
               check=False)
    if diff.returncode not in (0, 1):
        raise RuntimeError(f"Cannot verify the publication worktree: {diff.stderr[-1000:]}")
    if diff.returncode != 0:
        raise RuntimeError("Publication files changed after the content commit")
    if validate_publication_boundary({rel: load_json(rel) for rel in GATE_PATHS}) != gate_receipts:
        raise RuntimeError("A release gate changed while preparing the GitHub publication")

    main_content_commit = git("rev-parse", "HEAD")
    main_content_tree = git("rev-parse", "HEAD^{tree}")
    # Bind public-source expectations to canonical committed blobs.  On
    # Windows, Git may normalize working-copy CRLF to LF; working-tree hashes
    # are therefore not valid identities for raw.githubusercontent.com.
    main_inventory = inventory(allowed - {RECEIPT_REL}, main_content_commit)
    page_paths = {relative(path) for path in (ROOT / "reader" / "dist").rglob("*") if path.is_file()}
    pages_inventory = inventory(page_paths)
    pages_inventory = [{**row, "path": row["path"].removeprefix("reader/dist/")} for row in pages_inventory]

    ensure_public_repository()
    validate_push_route()
    git("push", "--set-upstream", "origin", "HEAD:refs/heads/main")
    pages_commit = git("subtree", "split", "--prefix=reader/dist", "HEAD")
    if tree_paths(pages_commit) != {row["path"] for row in pages_inventory}:
        raise RuntimeError("Generated gh-pages tree is not the exact reader/dist inventory")
    old = git("ls-remote", "origin", "refs/heads/gh-pages")
    old_sha = old.split()[0] if old else ""
    git("push", f"--force-with-lease=refs/heads/gh-pages:{old_sha}", "origin",
        f"{pages_commit}:refs/heads/gh-pages")
    configure_pages()

    receipt = {
        "schema": "o014-english-github-publication-v2",
        "published_at_utc": datetime.now(timezone.utc).isoformat(),
        "result": "PUSHED_PENDING_ANONYMOUS_READBACK",
        "repository": f"https://github.com/{SLUG}",
        "pages_url": f"https://{OWNER.lower()}.github.io/{REPO}/",
        "visibility": "public",
        "publication_scope": "complete_pdf_html_source_backend_release",
        "main_content_commit": main_content_commit,
        "main_content_tree": main_content_tree,
        "pages_commit": pages_commit,
        "pages_previous_commit": old_sha or None,
        "source_commit": SOURCE_COMMIT,
        "source_tree": SOURCE_TREE,
        "gate_receipts": gate_receipts,
        "main_inventory_excluding_this_receipt": main_inventory,
        "pages_inventory": pages_inventory,
        "credentials_recorded": False,
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if staged_paths():
        raise RuntimeError("Unexpected staged changes before publication-receipt commit")
    git("add", "--all", "--", RECEIPT_REL)
    if staged_paths() != {RECEIPT_REL}:
        raise RuntimeError(f"Publication-receipt staged inventory is not exact: {sorted(staged_paths())}")
    git("commit", "-m", "Record final GitHub publication boundary")
    final_expected = {row["path"] for row in main_inventory} | {RECEIPT_REL}
    assert_tree("HEAD", final_expected)
    validate_push_route()
    git("push", "origin", "HEAD:refs/heads/main")
    main_head = git("rev-parse", "HEAD")
    print(json.dumps({
        "result": receipt["result"], "content_commit": main_content_commit,
        "pages_commit": pages_commit, "main_head": main_head,
        "receipt_sha256": sha(RECEIPT),
    }))


if __name__ == "__main__":
    main()
