"""Write a deterministic, network-free preflight for release visual gates."""

from __future__ import annotations

from copy import deepcopy
import ast
import hashlib
import json
from pathlib import Path

from release_visual_gates import validate_html_browser_gate, validate_pdf_visual_gate


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "qa" / "RELEASE_TOOL_PREFLIGHT.json"
TOOL_PATHS = (
    "tools/release_visual_gates.py",
    "tools/preflight_release_visual_gates.py",
    "tools/package_english_release.py",
    "release/publish_github.py",
    "release/publish_zenodo.py",
    "release/verify_github_public.py",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(rel: str) -> dict[str, object]:
    path = ROOT / rel
    if not path.is_file():
        raise RuntimeError(f"Missing preflight input: {rel}")
    return {"path": rel, "bytes": path.stat().st_size, "sha256": sha256(path)}


def load(rel: str) -> dict:
    value = json.loads((ROOT / rel).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Preflight JSON is not an object: {rel}")
    return value


def current_browser_candidate(html: dict, browser: dict) -> dict:
    """Create an in-memory exact-current candidate; never write a QA PASS."""

    candidate = deepcopy(browser)
    for rel, parent, prefix in (
        ("reader/dist/index.html", candidate, "target"),
        ("qa/HTML_BUILD_RECEIPT.json", candidate["build_receipt"], None),
        ("reader/dist/SHA256SUMS.txt", candidate["local_links_and_assets"], "manifest"),
        ("reader/dist/validation-report.json", candidate["static_validation"], None),
    ):
        item = fingerprint(rel)
        if prefix == "target":
            parent["target_bytes"], parent["target_sha256"] = item["bytes"], item["sha256"]
        elif prefix == "manifest":
            parent["manifest_bytes"], parent["manifest_sha256"] = item["bytes"], item["sha256"]
        else:
            parent["bytes"], parent["sha256"] = item["bytes"], item["sha256"]
    validation = html["validation"]
    coverage = candidate["coverage"]
    coverage["logical_sections"] = validation["logical_sections"]
    coverage["source_units"] = 146
    coverage["mastery_bridges"] = validation["units_and_bridges"] - 146
    coverage["diagram_fallbacks"] = validation["ledger_diagrams"]
    coverage["diagram_captions"] = validation["ledger_diagrams"]
    assets = candidate["local_links_and_assets"]
    assets["manifest_files_http_read_back"] = html["dist_files"]
    assets["manifest_files_http_read_back_bytes"] = html["dist_bytes"]
    assets["http_failures"] = 0
    assets["byte_or_sha256_mismatches"] = 0
    assets["browser_console_warnings_or_errors"] = 0
    candidate["static_validation"]["local_references_checked"] = validation["local_references_checked"]
    candidate["static_validation"]["errors"] = 0
    return candidate


def expect_rejected(call, label: str) -> str:
    try:
        call()
    except RuntimeError as exc:
        return str(exc)
    raise RuntimeError(f"Fail-closed test was accepted: {label}")


def main() -> None:
    pdf_build = load("qa/PDF_BUILD_RECEIPT.json")
    pdf_visual = load("qa/PDF_VISUAL_QA.json")
    html_build = load("qa/HTML_BUILD_RECEIPT.json")
    html_browser = load("qa/HTML_BROWSER_QA.json")

    pdf_binding = validate_pdf_visual_gate(ROOT, pdf_build, pdf_visual)
    candidate = current_browser_candidate(html_build, html_browser)
    html_binding = validate_html_browser_gate(ROOT, html_build, candidate)

    bad_pdf = deepcopy(pdf_visual)
    bad_pdf["pdf_sha256"] = "0" * 64
    bad_html = deepcopy(candidate)
    bad_html["target_sha256"] = "0" * 64
    bad_build = deepcopy(candidate)
    bad_build["build_receipt"]["sha256"] = "0" * 64
    fail_closed = {
        "stale_pdf_artifact": expect_rejected(
            lambda: validate_pdf_visual_gate(ROOT, pdf_build, bad_pdf), "stale PDF artifact"
        ),
        "stale_html_index": expect_rejected(
            lambda: validate_html_browser_gate(ROOT, html_build, bad_html), "stale HTML index"
        ),
        "stale_html_build_receipt": expect_rejected(
            lambda: validate_html_browser_gate(ROOT, html_build, bad_build), "stale HTML build receipt"
        ),
    }

    try:
        validate_html_browser_gate(ROOT, html_build, html_browser)
    except RuntimeError as exc:
        live_browser_gate = {"status": "REJECTED_CURRENT_RECEIPT", "reason": str(exc)}
    else:
        live_browser_gate = {"status": "PASS_CURRENT_RECEIPT"}

    sources = {rel: (ROOT / rel).read_text(encoding="utf-8") for rel in TOOL_PATHS}
    for rel, source in sources.items():
        ast.parse(source, filename=rel)
    integration = {
        "package_imports_shared_gate": "from release_visual_gates import" in sources["tools/package_english_release.py"],
        "package_calls_pdf_gate": "validate_pdf_visual_gate(" in sources["tools/package_english_release.py"],
        "package_calls_html_gate": "validate_html_browser_gate(" in sources["tools/package_english_release.py"],
        "github_imports_shared_gate": "from release_visual_gates import" in sources["release/publish_github.py"],
        "github_calls_pdf_gate": "validate_pdf_visual_gate(" in sources["release/publish_github.py"],
        "github_calls_html_gate": "validate_html_browser_gate(" in sources["release/publish_github.py"],
        "github_requires_pdf_visual_receipt": '"qa/PDF_VISUAL_QA.json"' in sources["release/publish_github.py"],
        "github_binds_package_visual_gates": 'package.get("validated_inputs", {}).get("visual_qa")' in sources["release/publish_github.py"],
    }
    if any(value is not True for value in integration.values()):
        raise RuntimeError("A release entry point is not wired to every shared visual gate")

    receipt = {
        "schema": "o014-english-release-tool-preflight-v2",
        "result": "PASS",
        "scope": {
            "network_used": False,
            "credentials_used": False,
            "git_used": False,
            "package_created": False,
            "publication_executed": False,
            "qa_pass_receipts_modified": False,
        },
        "tool_identities": [fingerprint(rel) for rel in TOOL_PATHS],
        "static_checks": {
            "python_ast_parse_all_tools": True,
            "entry_point_integration": integration,
            "current_pdf_visual_gate": "PASS",
            "current_pdf_binding": pdf_binding,
            "synthetic_exact_current_html_gate": "PASS",
            "synthetic_exact_current_html_binding": html_binding,
            "live_html_browser_gate": live_browser_gate,
            "fail_closed_rejections": fail_closed,
        },
        "interpretation": (
            "The in-memory HTML candidate proves the validator accepts an exactly bound receipt; "
            "it is not a browser-QA result and was not written to qa/HTML_BROWSER_QA.json. "
            "A current stale browser receipt remains a hard release stop until browser QA is rerun."
        ),
    }
    encoded = (json.dumps(receipt, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    temporary = RECEIPT.with_suffix(".json.tmp")
    temporary.write_bytes(encoded)
    temporary.replace(RECEIPT)
    print(json.dumps({"result": "PASS", **fingerprint("qa/RELEASE_TOOL_PREFLIGHT.json")}))


if __name__ == "__main__":
    main()
