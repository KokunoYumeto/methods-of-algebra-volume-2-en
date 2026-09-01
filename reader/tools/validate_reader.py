#!/usr/bin/env python3
"""One deterministic offline-reader validation and hash manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from lxml import html


UNIT_RE = re.compile(
    r"\\input\{((?:prelude-unit-\d{3}|chapter\d+-unit-\d{3}|"
    r"appendix\d+-unit-\d{3}|mastery-bridge-[^}]+))\}"
)
EXPECTED_UNITS_AND_BRIDGES = 148
EXPECTED_LOGICAL_SECTIONS = 149
EXPECTED_DIAGRAMS = 907
LEDGER_FIELDS = {
    "diagram_id", "unit_filename", "local_order", "alt_text_en", "provenance"
}
REMOTE = {"http", "https", "mailto", "tel", "urn", "doi"}
UNSUPPORTED_MATH = {
    r"\setbox": "TeX box assignment",
    r"\pgfmathsetlengthmacro": "PGF length calculation",
    r"\tikz": "inline TikZ program",
    r"\draw": "TikZ draw command",
    r"\fill": "TikZ fill command",
    r"\path": "TikZ path command",
    r"\node": "TikZ node command",
    r"\matrix": "TikZ matrix command",
    r"\pgf": "PGF implementation token",
    r"\begin{tikz": "TikZ environment",
    r"\end{tikz": "TikZ environment",
    r"\textquotedblleft": "print-only opening quote macro",
    r"\textquotedblright": "print-only closing quote macro",
}
UNSUPPORTED_RAW = {
    r"\setbox": "TeX box assignment",
    r"\pgfmathsetlengthmacro": "PGF length calculation",
    r"\tikz": "TikZ implementation token",
    r"\draw": "TikZ draw command",
    r"\fill": "TikZ fill command",
    r"\path": "TikZ path command",
    r"\node": "TikZ node command",
    r"\matrix": "TikZ matrix command",
    r"\pgf": "PGF implementation token",
    r"\begin{tikz": "TikZ environment",
    r"\end{tikz": "TikZ environment",
    r"\begin{scope}": "TikZ scope environment",
    r"\end{scope}": "TikZ scope environment",
    r"\coordinate": "TikZ coordinate command",
    r"\textquotedblleft": "print-only opening quote macro",
    r"\textquotedblright": "print-only closing quote macro",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", required=True, type=Path)
    parser.add_argument("--master", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    args = parser.parse_args()

    script_reader = Path(__file__).resolve().parents[1]
    script_project = script_reader.parent
    expected_paths = {
        "dist": (script_reader / "dist").resolve(),
        "master": (script_project / "source" / "en" / "Al-jabr-2-en-complete-draft.tex").resolve(),
        "ledger": (script_project / "backend" / "figure-alt-text-en.csv").resolve(),
    }
    actual_paths = {
        "dist": args.dist.resolve(),
        "master": args.master.resolve(),
        "ledger": args.ledger.resolve(),
    }
    if actual_paths != expected_paths:
        raise SystemExit(
            "Reader validation paths must resolve to this script's dist, master, and ledger"
        )
    args.dist = actual_paths["dist"]
    args.master = actual_paths["master"]
    args.ledger = actual_paths["ledger"]

    expected = [f"{stem}.tex" for stem in UNIT_RE.findall(args.master.read_text(encoding="utf-8"))]
    if len(expected) != EXPECTED_UNITS_AND_BRIDGES or len(set(expected)) != len(expected):
        raise SystemExit(
            f"Expected {EXPECTED_UNITS_AND_BRIDGES} distinct master inputs; "
            f"found {len(expected)} inputs and {len(set(expected))} distinct inputs"
        )
    with args.ledger.open(encoding="utf-8-sig", newline="") as stream:
        ledger_rows = list(csv.DictReader(stream))
    ledger_count = len(ledger_rows)
    errors: list[str] = []
    missing_fields = LEDGER_FIELDS - set(ledger_rows[0] if ledger_rows else ())
    if missing_fields:
        errors.append(f"diagram ledger missing columns: {sorted(missing_fields)}")
    ledger_ids = [row.get("diagram_id", "").strip() for row in ledger_rows]
    if ledger_count != EXPECTED_DIAGRAMS:
        errors.append(f"diagram ledger has {ledger_count} rows, not {EXPECTED_DIAGRAMS}")
    if not missing_fields:
        if any(not diagram_id for diagram_id in ledger_ids):
            errors.append("diagram ledger contains a blank diagram ID")
        if len(set(ledger_ids)) != ledger_count:
            errors.append("diagram ledger contains duplicate diagram IDs")
        unknown_units = sorted(
            {row["unit_filename"].strip() for row in ledger_rows} - set(expected)
        )
        if unknown_units:
            errors.append(f"diagram ledger names unplanned units: {unknown_units[:10]}")
        if any(not row["alt_text_en"].strip() for row in ledger_rows):
            errors.append("diagram ledger contains a blank English description")
        if any(not row["provenance"].strip() for row in ledger_rows):
            errors.append("diagram ledger contains blank source provenance")
    override_payload = json.loads(
        (script_reader / "diagram-description-overrides-en.json").read_text(encoding="utf-8")
    )
    override_sources = {
        str(row.get("diagram_id", "")).strip(): str(row.get("source_ref", "")).strip()
        for row in override_payload.get("overrides", [])
    }
    expected_description_sources = [
        override_sources.get(row.get("diagram_id", "").strip(), row.get("provenance", "").strip())
        for row in ledger_rows
    ]
    html_files = sorted(args.dist.glob("*.html"))
    if not html_files:
        errors.append("no HTML files")

    parsed: dict[Path, object] = {}
    ids: dict[Path, set[str]] = {}
    math_count = 0
    math_source_count = 0
    image_count = 0
    applied_diagrams: list[str] = []
    applied_description_sources: list[str] = []
    local_refs = 0
    unsupported_math: list[dict[str, str]] = []
    unsupported_raw: list[dict[str, str]] = []
    for path in html_files:
        serialized = path.read_text(encoding="utf-8")
        if "READERDIAGRAM" in serialized:
            errors.append(f"{path.name}: unresolved diagram placeholder token remains")
        for macro, meaning in UNSUPPORTED_RAW.items():
            count = serialized.count(macro)
            if count:
                unsupported_raw.append(
                    {"file": path.name, "macro": macro, "meaning": meaning,
                     "occurrences": count}
                )
        tree = html.parse(str(path), parser=html.HTMLParser(encoding="utf-8"))
        parsed[path] = tree
        id_values = [value for value in tree.xpath("//*[@id]/@id") if value]
        duplicate_ids = sorted({value for value in id_values if id_values.count(value) > 1})
        if duplicate_ids:
            errors.append(f"{path.name}: duplicate ID: {duplicate_ids[:10]}")
        ids[path] = set(id_values)
        if tree.getroot().get("lang") != "en":
            errors.append(f"{path.name}: lang is not en")
        if len(tree.xpath("//title[normalize-space()]")) != 1:
            errors.append(f"{path.name}: missing or empty document title")
        if len(tree.xpath("//main[@id='main-content' and @tabindex='-1']")) != 1:
            errors.append(f"{path.name}: main-content landmark/focus target is missing")
        if len(tree.xpath("//a[contains(concat(' ', normalize-space(@class), ' '), ' skip-link ') and @href='#main-content']")) != 1:
            errors.append(f"{path.name}: skip link is missing or has the wrong target")
        math_count += len(tree.xpath("//*[local-name()='math']"))
        math_source_count += len(tree.xpath(
            "//*[contains(concat(' ', normalize-space(@class), ' '), ' mathjax-inline ') or "
            "contains(concat(' ', normalize-space(@class), ' '), ' mathjax-display ') or "
            "contains(concat(' ', normalize-space(@class), ' '), ' math ')]"
        ))
        for node in tree.xpath(
            "//*[contains(concat(' ', normalize-space(@class), ' '), ' math ')]"
        ):
            source = node.text_content()
            for macro, meaning in UNSUPPORTED_MATH.items():
                if macro in source:
                    unsupported_math.append(
                        {"file": path.name, "macro": macro, "meaning": meaning,
                         "source": source[:300]}
                    )
        images = tree.xpath("//img")
        image_count += len(images)
        for image in images:
            if not (image.get("alt") or "").strip():
                errors.append(f"{path.name}: image without alt text: {image.get('src', '')}")
        applied_diagrams.extend(tree.xpath("//*[@data-diagram-id]/@data-diagram-id"))
        applied_description_sources.extend(
            tree.xpath("//*[@data-diagram-id]/@data-description-source")
        )

    index = args.dist / "index.html"
    if index in parsed:
        tree = parsed[index]
        units = tree.xpath("//section[@data-unit-file]/@data-unit-file")
        if units != expected:
            errors.append(
                f"index.html: unit order {len(units)} does not match the "
                f"{EXPECTED_UNITS_AND_BRIDGES} master inputs"
            )
        unlabeled_units = tree.xpath(
            "//section[@data-unit-file and not(normalize-space(@aria-label))]"
        )
        if unlabeled_units:
            errors.append(f"index.html: {len(unlabeled_units)} unit sections lack accessible labels")
        if len(tree.xpath("//nav[@class='reader-unit-index']//a")) != len(expected):
            errors.append(
                f"index.html: unit index does not contain {EXPECTED_UNITS_AND_BRIDGES} links"
            )
        expected_nav = [f"#unit-{Path(filename).stem}" for filename in expected]
        actual_nav = tree.xpath("//nav[@class='reader-unit-index']//a/@href")
        if actual_nav != expected_nav:
            errors.append("index.html: unit index targets do not exactly match master order")
        logical_sections = len(tree.xpath("//section[@data-unit-file] | //section[@id='bibliography']"))
        if logical_sections != EXPECTED_LOGICAL_SECTIONS:
            errors.append(
                f"index.html: logical sections {logical_sections}, not {EXPECTED_LOGICAL_SECTIONS}"
            )
        if applied_diagrams != ledger_ids:
            errors.append(
                "index.html: diagram identities/order do not exactly match the alt-text ledger "
                f"({len(applied_diagrams)}/{ledger_count})"
            )
        if applied_description_sources != expected_description_sources:
            errors.append(
                "index.html: diagram description provenance does not exactly match ledger/overrides "
                f"({len(applied_description_sources)}/{ledger_count})"
            )
        diagram_figures = tree.xpath("//figure[@data-diagram-id]")
        malformed_figures = [
            figure for figure in diagram_figures
            if figure.get("role") != "img"
            or not (figure.get("aria-labelledby") or "").strip()
            or not (figure.get("data-description-source") or "").strip()
            or len(figure.xpath("./figcaption[@id=$caption]", caption=figure.get("aria-labelledby"))) != 1
        ]
        if malformed_figures:
            errors.append(
                f"index.html: {len(malformed_figures)} diagram fallbacks lack figure/caption semantics"
            )
        raw_tex_captions = [
            figure for figure in diagram_figures if "\\" in figure.text_content()
        ]
        if raw_tex_captions:
            errors.append(
                f"index.html: {len(raw_tex_captions)} diagram captions expose raw TeX commands"
            )
        mathjax_scripts = tree.xpath("//script[contains(@src, 'mathjax-3.2.2/tex-chtml-full.js')]")
        mathjax_config = "".join(tree.xpath("//script[not(@src)]/text()"))
        if math_count == 0 and math_source_count == 0:
            errors.append("index.html: semantic math source not found")
        if not mathjax_scripts:
            errors.append("index.html: local MathJax bundle not referenced")
        if 'ensuremath:["#1",1]' not in mathjax_config:
            errors.append("index.html: MathJax ensuremath compatibility macro is missing")
        if unsupported_math:
            summary = sorted({row["macro"] for row in unsupported_math})
            errors.append(f"index.html: unsupported HTML math macros remain: {summary}")
        if unsupported_raw:
            summary = sorted({row["macro"] for row in unsupported_raw})
            errors.append(f"index.html: raw TeX/PGF implementation tokens remain: {summary}")

        required_mathjax = [
            args.dist / "vendor" / "mathjax-3.2.2" / "tex-chtml-full.js",
            args.dist / "vendor" / "mathjax-3.2.2" / "LICENSE-MathJax.txt",
        ]
        font_dir = args.dist / "vendor" / "mathjax-3.2.2" / "output" / "chtml" / "fonts" / "woff-v2"
        missing_mathjax = [path for path in required_mathjax if not path.is_file()]
        local_fonts = sorted(font_dir.glob("*.woff")) if font_dir.is_dir() else []
        if missing_mathjax or len(local_fonts) != 23:
            errors.append(
                "index.html: local MathJax bundle is incomplete "
                f"({len(missing_mathjax)} required files missing, {len(local_fonts)}/23 fonts)"
            )

        css_path = args.dist / "reader.css"
        if css_path.is_file():
            css_text = css_path.read_text(encoding="utf-8")
            css_requirements = {
                ".reader-main": "centered reflow container",
                "margin-inline: auto": "horizontal centering",
                "@media (max-width: 42rem)": "mobile reflow",
                "overflow-x: auto": "local wide-content scrolling",
                "mjx-container[display=\"true\"]": "display-math scroller",
            }
            for marker, meaning in css_requirements.items():
                if marker not in css_text:
                    errors.append(f"reader.css: missing {meaning} marker: {marker}")

    for path, tree in list(parsed.items()):
        for element, attribute in [
            ("a", "href"), ("img", "src"), ("link", "href"),
            ("object", "data"), ("source", "src"), ("script", "src"),
        ]:
            for node in tree.xpath(f"//{element}[@{attribute}]"):
                raw = (node.get(attribute) or "").strip()
                if not raw:
                    continue
                url = urlsplit(raw)
                if url.scheme.lower() in REMOTE:
                    if element != "a":
                        errors.append(f"{path.name}: network asset: {raw}")
                    continue
                if url.scheme or raw.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", raw):
                    errors.append(f"{path.name}: absolute/private path: {raw}")
                    continue
                target = path if not url.path else (path.parent / unquote(url.path)).resolve()
                try:
                    target.relative_to(args.dist.resolve())
                except ValueError:
                    errors.append(f"{path.name}: reference outside dist: {raw}")
                    continue
                if not target.exists():
                    errors.append(f"{path.name}: missing local target: {raw}")
                    continue
                local_refs += 1
                if url.fragment and target.suffix.lower() in {".html", ".htm"}:
                    if target not in parsed:
                        parsed[target] = html.parse(str(target), parser=html.HTMLParser(encoding="utf-8"))
                        ids[target] = set(parsed[target].xpath("//*[@id]/@id"))
                    if unquote(url.fragment) not in ids[target]:
                        errors.append(f"{path.name}: missing fragment: {raw}")

    report_path = args.dist / "validation-report.json"
    report = {
        "status": "pass" if not errors else "fail",
        "html_files": len(html_files),
        "units_and_bridges": len(expected),
        "mathml_elements": math_count,
        "mathjax_source_elements": math_source_count,
        "images": image_count,
        "diagram_alt_texts_applied": len(applied_diagrams),
        "ledger_diagrams": ledger_count,
        "local_references_checked": local_refs,
        "logical_sections": EXPECTED_LOGICAL_SECTIONS if index in parsed and not any(
            error.startswith("index.html: logical sections") for error in errors
        ) else None,
        "unsupported_math_residue": unsupported_math,
        "unsupported_raw_residue": unsupported_raw,
        "errors": errors,
        "limitations": [
            "MathML pronunciation depends on the browser and assistive technology.",
            "Complex diagram alt text is a summary, not a complete substitute for the visual relation.",
            "No WCAG conformance level or tagged-PDF claim is made.",
        ],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest_path = args.dist / "SHA256SUMS.txt"
    files = sorted(path for path in args.dist.rglob("*") if path.is_file() and path != manifest_path)
    lines = [f"{sha256(path)}  {path.relative_to(args.dist).as_posix()}" for path in files]
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
