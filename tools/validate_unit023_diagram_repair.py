"""Fail-closed validation for the bounded Unit 023 diagram repair."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import html
import io
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "source" / "en" / "chapter2-unit-023.tex"
CONTROL = ROOT / "controls" / "UNIT023_DIAGRAM_DESCRIPTIONS.json"
LEDGER = ROOT / "backend" / "figure-alt-text-en.csv"
INVENTORY = ROOT / "qa" / "DIAGRAM_SOURCE_INVENTORY.jsonl"
HTML = ROOT / "reader" / "dist" / "index.html"
HTML_VALIDATION = ROOT / "reader" / "dist" / "validation-report.json"
RECEIPT = ROOT / "qa" / "UNIT023_DIAGRAM_REPAIR_QA.json"
DEFECT_REPORT = Path(
    r"C:\Users\Floris\Documents\Codex\2026-10-01\open-course-sheaves-full-review-20261001"
    r"\outputs\SHDC-CPLX-F03-20261003.json"
)
EXPECTED_DEFECT_REPORT_SHA256 = (
    "783700cb6803a6f651a09f08fe2d9dce3f32ec8dcccead5a9f0a57dba47e7bf5"
)
EXPECTED_UNIT_SHA256 = (
    "65ce863946f2f3f4fa33f4aa088f59e6aa82ed8403e93f8939e1c269e6863a5d"
)
ENVIRONMENT = re.compile(
    r"\\begin\{(tikzcd|tikzpicture)\}(.*?)\\end\{\1\}", re.DOTALL
)
TAG = re.compile(r"<[^>]+>")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def normalized_text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG.sub("", fragment))).strip()


def csv_rows(value: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(value)))


def main() -> None:
    control = json.loads(CONTROL.read_text(encoding="utf-8-sig"))
    entries = control["entries"]
    ids = [entry["diagram_id"] for entry in entries]
    source_text = UNIT.read_text(encoding="utf-8-sig")
    source_environments = [
        {"environment": match.group(1), "tex_body": match.group(2).strip()}
        for match in ENVIRONMENT.finditer(source_text)
    ]
    source_segments = re.findall(
        r"segment-id:\s+o014\.li2\.chapter2\.diagram-lemmas\.(g\d{3})",
        source_text,
    )

    with LEDGER.open(encoding="utf-8-sig", newline="") as stream:
        all_ledger_rows = list(csv.DictReader(stream))
    ledger_rows = [
        row for row in all_ledger_rows
        if row["unit_filename"] == "chapter2-unit-023.tex"
    ]
    inventory = [
        json.loads(line)
        for line in INVENTORY.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    inventory_rows = [
        row for row in inventory
        if row["unit_filename"] == "chapter2-unit-023.tex"
    ]

    html_text = HTML.read_text(encoding="utf-8-sig")
    section_start = html_text.find('<section id="unit-chapter2-unit-023"')
    next_unit = html_text.find('<section id="unit-chapter2-unit-024"', section_start)
    unit_html = html_text[section_start:next_unit]
    html_ids = re.findall(r'data-diagram-id="([^"]+)"', unit_html)
    figure_matches = re.findall(
        r'<figure[^>]*data-diagram-id="([^"]+)"[^>]*data-description-source="([^"]*)"'
        r'[^>]*>.*?<figcaption[^>]*>(.*?)</figcaption>.*?</figure>',
        unit_html,
        re.DOTALL,
    )
    figure_by_id = {
        diagram_id: {
            "source": html.unescape(source),
            "caption": normalized_text(caption),
        }
        for diagram_id, source, caption in figure_matches
    }
    validation = json.loads(HTML_VALIDATION.read_text(encoding="utf-8-sig"))

    git_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        text=True, encoding="utf-8", capture_output=True,
    ).stdout.strip()
    head_ledger = subprocess.run(
        ["git", "show", "HEAD:backend/figure-alt-text-en.csv"], cwd=ROOT,
        check=True, text=True, encoding="utf-8", capture_output=True,
    ).stdout
    head_outside = [
        row for row in csv_rows(head_ledger)
        if row["unit_filename"] != "chapter2-unit-023.tex"
    ]
    current_outside = [
        row for row in all_ledger_rows
        if row["unit_filename"] != "chapter2-unit-023.tex"
    ]

    per_diagram = []
    for index, entry in enumerate(entries):
        diagram_id = entry["diagram_id"]
        ledger = ledger_rows[index] if index < len(ledger_rows) else {}
        inventory_row = inventory_rows[index] if index < len(inventory_rows) else {}
        figure = figure_by_id.get(diagram_id, {})
        caption = figure.get("caption", "")
        expected_prefix = f"Diagram {diagram_id}. "
        per_diagram.append({
            "diagram_id": diagram_id,
            "local_order": entry["local_order"],
            "source_segment_id": entry["source_segment_id"],
            "source_ref": entry["source_ref"],
            "checks": {
                "ledger_id_and_order": (
                    ledger.get("diagram_id") == diagram_id
                    and ledger.get("local_order") == str(entry["local_order"])
                ),
                "ledger_description_exact": (
                    ledger.get("alt_text_en") == entry["description_en"]
                ),
                "inventory_id_and_order": (
                    inventory_row.get("diagram_id") == diagram_id
                    and inventory_row.get("actual_order") == entry["local_order"]
                ),
                "inventory_structure_matches": (
                    index < len(source_environments)
                    and inventory_row.get("environment")
                    == source_environments[index]["environment"]
                    and inventory_row.get("source_relationship")
                    == "mapped_indonesian_structure_witness"
                    and str(inventory_row.get("tex_body", "")).count("\\arrow")
                    == source_environments[index]["tex_body"].count("\\arrow")
                    and str(inventory_row.get("tex_body", "")).count("\\draw")
                    == source_environments[index]["tex_body"].count("\\draw")
                ),
                "html_figure_present": diagram_id in figure_by_id,
                "html_description_exact": caption == expected_prefix + entry["description_en"],
                "html_provenance_names_control": (
                    f"controls/UNIT023_DIAGRAM_DESCRIPTIONS.json#{diagram_id}"
                    in figure.get("source", "")
                ),
            },
        })

    forbidden_truncation = re.findall(
        r"(?i)(?:\band\s+\d+\s+(?:other|additional)\s+arrows\b|"
        r"\badditional arrows complete the grid\b|\bfurther displayed objects\b|"
        r"\bpath-composition schematic\b)",
        unit_html,
    )
    d015_position = unit_html.find('data-diagram-id="chapter2-unit-023-d015"')
    d016_position = unit_html.find('data-diagram-id="chapter2-unit-023-d016"')
    proposition_position = unit_html.find('id="prop:5-lemma"')
    proof_lift_position = unit_html.find(
        "Applying Lemma", proposition_position
    )
    checks = {
        "defect_report_exists": DEFECT_REPORT.is_file(),
        "defect_report_sha256_exact": (
            DEFECT_REPORT.is_file()
            and sha256(DEFECT_REPORT) == EXPECTED_DEFECT_REPORT_SHA256
        ),
        "unit_source_sha256_unchanged": sha256(UNIT) == EXPECTED_UNIT_SHA256,
        "control_entries_23": len(entries) == 23,
        "control_ids_unique": len(ids) == len(set(ids)),
        "control_orders_1_to_23": [entry["local_order"] for entry in entries] == list(range(1, 24)),
        "source_environments_23": len(source_environments) == 23,
        "source_segments_g001_to_g023": source_segments == [f"g{n:03d}" for n in range(1, 24)],
        "ledger_rows_23_in_exact_order": [row["diagram_id"] for row in ledger_rows] == ids,
        "inventory_rows_23_in_exact_order": [row["diagram_id"] for row in inventory_rows] == ids,
        "html_figures_23_in_exact_order": html_ids == ids,
        "all_per_diagram_checks_pass": all(
            all(row["checks"].values()) for row in per_diagram
        ),
        "no_truncated_or_generic_descriptions": not forbidden_truncation,
        "d015_between_five_lemma_statement_and_proof_lift": (
            proposition_position >= 0
            and proposition_position < d015_position < proof_lift_position
        ),
        "d016_is_after_proof_lift_context": d016_position > proof_lift_position >= 0,
        "d015_text_is_five_column": (
            "five vertical arrows are f_1" in figure_by_id.get(
                "chapter2-unit-023-d015", {}
            ).get("caption", "")
        ),
        "d016_text_is_four_object_lift": (
            "First lifting square in the Five Lemma proof" in figure_by_id.get(
                "chapter2-unit-023-d016", {}
            ).get("caption", "")
        ),
        "outside_unit_ledger_unchanged_from_head": current_outside == head_outside,
        "reader_validation_pass": validation.get("status") == "pass",
        "reader_sections_149": validation.get("logical_sections") == 149,
        "reader_diagrams_907": validation.get("ledger_diagrams") == 907,
        "reader_alt_texts_907": validation.get("diagram_alt_texts_applied") == 907,
        "reader_validation_errors_zero": not validation.get("errors"),
        "reader_unsupported_math_zero": not validation.get("unsupported_math_residue"),
        "reader_unsupported_raw_zero": not validation.get("unsupported_raw_residue"),
        "reader_broken_anchor_fallbacks_zero": not validation.get("misplaced_anchor_fallbacks"),
    }
    result = "PASS" if all(checks.values()) else "FAIL"
    receipt = {
        "schema": "o014-english-unit023-diagram-repair-qa-v1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "result": result,
        "scope": "Unit 023 only; source mathematics and PDF bytes unchanged",
        "checks": checks,
        "forbidden_truncation_matches": forbidden_truncation,
        "per_diagram": per_diagram,
        "git_head_compared": git_head,
        "files": {
            "defect_report": {
                "bytes": DEFECT_REPORT.stat().st_size,
                "sha256": sha256(DEFECT_REPORT),
            },
            "unit_source": {"bytes": UNIT.stat().st_size, "sha256": sha256(UNIT)},
            "control": {"bytes": CONTROL.stat().st_size, "sha256": sha256(CONTROL)},
            "ledger": {"bytes": LEDGER.stat().st_size, "sha256": sha256(LEDGER)},
            "inventory": {"bytes": INVENTORY.stat().st_size, "sha256": sha256(INVENTORY)},
            "reader_index": {"bytes": HTML.stat().st_size, "sha256": sha256(HTML)},
            "reader_validation": {
                "bytes": HTML_VALIDATION.stat().st_size,
                "sha256": sha256(HTML_VALIDATION),
            },
        },
    }
    RECEIPT.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "result": result,
        "figures": len(per_diagram),
        "checks": len(checks),
        "reader_index_sha256": receipt["files"]["reader_index"]["sha256"],
        "receipt": str(RECEIPT),
    }))
    if result != "PASS":
        failed = [key for key, value in checks.items() if not value]
        raise SystemExit("failed checks: " + ", ".join(failed))


if __name__ == "__main__":
    main()
