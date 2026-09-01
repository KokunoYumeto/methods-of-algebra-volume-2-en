"""Shared fail-closed bindings for release visual-QA receipts.

Packaging and publication must call these validators before they mutate release
state.  Keeping the byte bindings here prevents the two entry points from
silently drifting apart.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


PDF_BUILD_SCHEMA = "o014-english-pdf-build-v1"
PDF_VISUAL_SCHEMA = "o014-english-pdf-visual-qa-v2"
HTML_BUILD_SCHEMA = "o014-english-html-build-v1"
HTML_BROWSER_SCHEMA = "o014-english-html-browser-qa-v2"
CANONICAL_PDF = "output/pdf/methods-of-algebra-volume-2-independent-english-edition.pdf"
CANONICAL_HTML = "reader/dist/index.html"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_file(root: Path, rel: str, label: str) -> Path:
    if not isinstance(rel, str) or not rel or "\\" in rel or Path(rel).is_absolute():
        raise RuntimeError(f"{label} has an invalid repository-relative path: {rel!r}")
    root = root.resolve()
    path = (root / rel).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"{label} escapes the release lane: {rel}") from exc
    if not path.is_file():
        raise RuntimeError(f"Required {label} is missing: {rel}")
    return path


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _fingerprint(path: Path) -> dict[str, object]:
    return {"bytes": path.stat().st_size, "sha256": _sha256(path)}


def _require_identity(
    root: Path, rel: str, expected_bytes: object, expected_sha256: object, label: str
) -> dict[str, object]:
    if type(expected_bytes) is not int or expected_bytes <= 0:
        raise RuntimeError(f"{label} has an invalid recorded byte count")
    if not _valid_sha256(expected_sha256):
        raise RuntimeError(f"{label} has an invalid recorded SHA-256")
    path = _repo_file(root, rel, label)
    actual = _fingerprint(path)
    expected = {"bytes": expected_bytes, "sha256": expected_sha256}
    if actual != expected:
        raise RuntimeError(
            f"{label} is stale: expected {expected}, current bytes are {actual}"
        )
    return {"path": rel, **actual}


def _require_pass(receipt: dict, schema: str, label: str) -> None:
    if not isinstance(receipt, dict) or receipt.get("schema") != schema:
        raise RuntimeError(f"{label} must use schema {schema}")
    if receipt.get("result") != "PASS":
        raise RuntimeError(f"{label} must record result PASS")


def _receipt_binding(root: Path, rel: str) -> dict[str, object]:
    return {"path": rel, **_fingerprint(_repo_file(root, rel, "QA receipt"))}


def validate_pdf_visual_gate(
    root: Path, pdf_build: dict, pdf_visual: dict
) -> dict[str, object]:
    """Bind the all-page visual PASS to the exact PDF build and current PDF."""

    _require_pass(pdf_build, PDF_BUILD_SCHEMA, "PDF build receipt")
    _require_pass(pdf_visual, PDF_VISUAL_SCHEMA, "PDF visual-QA receipt")
    if pdf_build.get("pdf") != CANONICAL_PDF or pdf_visual.get("pdf") != CANONICAL_PDF:
        raise RuntimeError("PDF build and visual QA must name the canonical release PDF")
    build_identity = (pdf_build.get("pdf_bytes"), pdf_build.get("pdf_sha256"))
    visual_identity = (pdf_visual.get("pdf_bytes"), pdf_visual.get("pdf_sha256"))
    if build_identity != visual_identity:
        raise RuntimeError("PDF visual QA is not bound to the current PDF build receipt")
    artifact = _require_identity(
        root, CANONICAL_PDF, pdf_visual.get("pdf_bytes"), pdf_visual.get("pdf_sha256"),
        "PDF visual-QA artifact",
    )

    pages = pdf_visual.get("pages")
    inspection = pdf_visual.get("inspection", {})
    checks = pdf_visual.get("checks", {})
    if type(pages) is not int or pages <= 0:
        raise RuntimeError("PDF visual QA has an invalid page count")
    pdfinfo = pdf_build.get("pdfinfo", {})
    match = re.search(r"(?m)^Pages:\s+(\d+)\s*$", str(pdfinfo.get("stdout_tail", "")))
    if not match or int(match.group(1)) != pages:
        raise RuntimeError("PDF visual-QA page count differs from the PDF build evidence")
    if (
        inspection.get("rendered_page_count") != pages
        or inspection.get("all_pages_visually_inspected") is not True
        or inspection.get("material_defects_found") != 0
        or not isinstance(checks, dict)
        or not checks
        or any(value is not True for value in checks.values())
    ):
        raise RuntimeError("PDF all-page visual-QA coverage is incomplete or defective")
    text = pdf_visual.get("text_extraction", {})
    if text.get("full_document_checked") is not True or text.get("forbidden_hit_total") != 0:
        raise RuntimeError("PDF visual-QA text-residue gate is incomplete or defective")

    durable = pdf_visual.get("durable_evidence", {})
    manifest = _require_identity(
        root, durable.get("page_manifest"), durable.get("page_manifest_bytes"),
        durable.get("page_manifest_sha256"), "PDF all-page manifest",
    )
    metrics = _require_identity(
        root, durable.get("all_page_metrics"), durable.get("all_page_metrics_bytes"),
        durable.get("all_page_metrics_sha256"), "PDF all-page metrics",
    )
    return {
        "receipt": _receipt_binding(root, "qa/PDF_VISUAL_QA.json"),
        "artifact": artifact,
        "pages": pages,
        "page_manifest": manifest,
        "all_page_metrics": metrics,
    }


def validate_html_browser_gate(
    root: Path, html_build: dict, html_browser: dict
) -> dict[str, object]:
    """Bind browser QA to the exact reader index, build receipt, and build report."""

    _require_pass(html_build, HTML_BUILD_SCHEMA, "HTML build receipt")
    _require_pass(html_browser, HTML_BROWSER_SCHEMA, "HTML browser-QA receipt")
    if html_browser.get("target") != CANONICAL_HTML:
        raise RuntimeError("HTML browser QA must target the canonical reader index")
    build_identity = (html_build.get("index_bytes"), html_build.get("index_sha256"))
    browser_identity = (html_browser.get("target_bytes"), html_browser.get("target_sha256"))
    if build_identity != browser_identity:
        raise RuntimeError("HTML browser QA is not bound to the current HTML build receipt")
    index = _require_identity(
        root, CANONICAL_HTML, html_browser.get("target_bytes"), html_browser.get("target_sha256"),
        "HTML browser-QA target",
    )

    build_receipt = html_browser.get("build_receipt", {})
    if build_receipt.get("path") != "qa/HTML_BUILD_RECEIPT.json":
        raise RuntimeError("HTML browser QA does not name the canonical build receipt")
    build_receipt_binding = _require_identity(
        root, build_receipt.get("path"), build_receipt.get("bytes"),
        build_receipt.get("sha256"), "HTML browser-QA build receipt",
    )
    build_report = _require_identity(
        root, "reader/build/reader-build-report.json",
        _repo_file(root, "reader/build/reader-build-report.json", "reader build report").stat().st_size,
        html_build.get("reader_build_report_sha256"), "HTML reader build report",
    )

    assets = html_browser.get("local_links_and_assets", {})
    if assets.get("manifest_path") != "reader/dist/SHA256SUMS.txt":
        raise RuntimeError("HTML browser QA does not name the canonical reader manifest")
    manifest = _require_identity(
        root, assets.get("manifest_path"), assets.get("manifest_bytes"),
        assets.get("manifest_sha256"), "HTML browser-QA manifest",
    )
    static = html_browser.get("static_validation", {})
    if static.get("path") != "reader/dist/validation-report.json":
        raise RuntimeError("HTML browser QA does not name the canonical static validation")
    validation = _require_identity(
        root, static.get("path"), static.get("bytes"), static.get("sha256"),
        "HTML browser-QA static validation",
    )
    try:
        validation_report = json.loads(
            _repo_file(root, static["path"], "static validation").read_text(encoding="utf-8-sig")
        )
        reader_report = json.loads(
            _repo_file(root, "reader/build/reader-build-report.json", "reader build report")
            .read_text(encoding="utf-8-sig")
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Reader build evidence contains invalid JSON") from exc
    if validation_report != html_build.get("validation"):
        raise RuntimeError("HTML browser QA is not bound to the current static validation content")
    if validation_report.get("status") != "pass" or validation_report.get("errors"):
        raise RuntimeError("HTML static validation is not a clean pass")

    coverage = html_browser.get("coverage", {})
    if (
        coverage.get("logical_sections") != validation_report.get("logical_sections")
        or coverage.get("source_units", 0) + coverage.get("mastery_bridges", 0)
        != validation_report.get("units_and_bridges")
        or coverage.get("diagram_fallbacks") != validation_report.get("ledger_diagrams")
        or coverage.get("diagram_captions") != validation_report.get("ledger_diagrams")
        or reader_report.get("logical_sections") != validation_report.get("logical_sections")
        or reader_report.get("units_and_bridges") != validation_report.get("units_and_bridges")
        or reader_report.get("ledger_diagrams") != validation_report.get("ledger_diagrams")
    ):
        raise RuntimeError("HTML browser-QA coverage differs from the current reader build")
    if (
        assets.get("manifest_files_http_read_back") != html_build.get("dist_files")
        or assets.get("manifest_files_http_read_back_bytes") != html_build.get("dist_bytes")
        or any(
            assets.get(key) != 0
            for key in (
                "http_failures", "byte_or_sha256_mismatches", "browser_console_warnings_or_errors"
            )
        )
        or static.get("errors") != 0
    ):
        raise RuntimeError("HTML browser-QA readback contains defects or stale totals")
    for viewport_name in ("desktop", "mobile"):
        viewport = html_browser.get(viewport_name, {})
        if (
            viewport.get("mjx_merror_nodes") != 0
            or viewport.get("visible_raw_tex_command_tokens") != 0
            or viewport.get("visible_hypertarget_tokens") != 0
            or viewport.get("visible_ensuremath_tokens") != 0
            or viewport.get("diagram_captions_with_raw_tex_commands") != 0
            or viewport.get("known_indonesian_caption_residue") != 0
            or viewport.get("page_level_horizontal_overflow") is not False
            or viewport.get("wide_candidates_without_local_scroller") != 0
            or not str(viewport.get("visual_inspection", "")).startswith("PASS:")
        ):
            raise RuntimeError(f"HTML {viewport_name} browser-QA evidence is incomplete or defective")

    return {
        "receipt": _receipt_binding(root, "qa/HTML_BROWSER_QA.json"),
        "index": index,
        "html_build_receipt": build_receipt_binding,
        "reader_build_report": build_report,
        "manifest": manifest,
        "static_validation": validation,
    }
