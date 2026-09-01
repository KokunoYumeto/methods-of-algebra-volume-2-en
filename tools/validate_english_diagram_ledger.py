"""Validate the complete English diagram-description ledger without building.

This check is intentionally source-local: it compares the complete ledger
with the admitted target filenames and their TikZ environment order.  It does
not render, mutate, or scan outside the English edition root.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "backend" / "figure-alt-text-en.csv"
SOURCE = ROOT / "source" / "en"
SOURCE_MAP = ROOT / "controls" / "SOURCE_UNIT_MAP.json"
OUT = ROOT / "qa" / "DIAGRAM_LEDGER_VALIDATION.json"
DIAGRAM = re.compile(r"\\begin\{(tikzcd|tikzpicture)\}")
HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
INDONESIAN = re.compile(
    r"\b(yang|dengan|adalah|untuk|dari|dalam|pada|sebagai|maka|karena|"
    r"jika|dan|atau|suatu|dapat|akan|kita|ini|tersebut|bukti|latihan|"
    r"petunjuk|teorema|definisi|contoh|catatan|misalkan|sehingga|"
    r"kelasnya|citranya|pemetaan|homotopi)\b|\bdi three column to right\b",
    re.I,
)
PLACEHOLDER = re.compile(
    r"\b(?:todo|tbd|placeholder|description unavailable|alt text unavailable|"
    r"diagram omitted|see (?:the )?(?:source|figure))\b",
    re.I,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def braces_balanced(value: str) -> bool:
    depth = 0
    escaped = False
    for char in value:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def strip_tex_comments(value: str) -> str:
    """Remove unescaped TeX comments while retaining line boundaries."""
    clean = []
    for line in value.splitlines(keepends=True):
        cut = len(line)
        for index, char in enumerate(line):
            if char != "%":
                continue
            slashes = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                slashes += 1
                cursor -= 1
            if slashes % 2 == 0:
                cut = index
                break
        suffix = "\n" if line.endswith("\n") else ""
        clean.append(line[:cut].rstrip("\r\n") + suffix)
    return "".join(clean)


def main() -> None:
    with LEDGER.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    required = {"diagram_id", "unit_filename", "local_order", "alt_text_en", "provenance"}
    columns = set(rows[0]) if rows else set()
    defects: list[dict[str, object]] = []
    by_unit: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_unit[row["unit_filename"]].append(row)
        alt = row["alt_text_en"].strip()
        reasons = []
        if len(alt) < 15:
            reasons.append("too_short")
        if not braces_balanced(alt):
            reasons.append("unbalanced_braces")
        if HAN.search(alt):
            reasons.append("han_residue")
        if INDONESIAN.search(alt):
            reasons.append("indonesian_residue")
        if PLACEHOLDER.search(alt):
            reasons.append("placeholder")
        if not row["provenance"].strip():
            reasons.append("missing_provenance")
        try:
            order = int(row["local_order"])
            if order < 1:
                reasons.append("invalid_local_order")
        except ValueError:
            reasons.append("invalid_local_order")
        if reasons:
            defects.append({"diagram_id": row["diagram_id"], "reasons": reasons, "alt_text_en": alt})

    duplicate_ids = sorted(key for key, count in Counter(row["diagram_id"] for row in rows).items() if count > 1)
    duplicate_unit_orders = sorted(
        f"{unit}:{order}" for (unit, order), count in
        Counter((row["unit_filename"], row["local_order"]) for row in rows).items() if count > 1
    )
    mapping = json.loads(SOURCE_MAP.read_text(encoding="utf-8-sig"))
    witness_by_file = {
        Path(row["target_path"]).name: Path(row["id_reference_path"])
        for row in mapping["units"]
    }
    for stem in mapping["bridge_stems"]:
        witness_by_file[f"{stem}.tex"] = SOURCE / f"{stem}.tex"
    witness_mismatches = []
    target_mismatches = []
    expected_counts = {}
    for unit, witness in sorted(witness_by_file.items()):
        unit_rows = by_unit.get(unit, [])
        if not witness.is_file():
            witness_mismatches.append({"unit_filename": unit, "reason": "mapped_witness_missing"})
            expected_counts[unit] = None
        else:
            witness_expected = len(DIAGRAM.findall(strip_tex_comments(
                witness.read_text(encoding="utf-8-sig")
            )))
            expected_counts[unit] = witness_expected
            if witness_expected != len(unit_rows):
                witness_mismatches.append(
                    {"unit_filename": unit, "witness_diagrams": witness_expected,
                     "ledger_rows": len(unit_rows)}
                )
        path = SOURCE / unit
        if not path.is_file():
            target_mismatches.append({"unit_filename": unit, "reason": "target_missing"})
            continue
        expected = len(DIAGRAM.findall(strip_tex_comments(
            path.read_text(encoding="utf-8-sig")
        )))
        orders = sorted(int(row["local_order"]) for row in unit_rows if row["local_order"].isdigit())
        if expected != len(unit_rows) or orders != list(range(1, len(unit_rows) + 1)):
            target_mismatches.append(
                {"unit_filename": unit, "source_diagrams": expected,
                 "ledger_rows": len(unit_rows), "local_orders": orders}
            )

    checks = {
        "columns_exact": columns == required,
        "rows_907": len(rows) == 907,
        "files_with_diagrams_exact": set(by_unit) == {
            unit for unit, count in expected_counts.items() if count
        },
        "diagram_ids_unique": not duplicate_ids,
        "unit_local_orders_unique": not duplicate_unit_orders,
        "descriptions_and_provenance_valid": not defects,
        "witness_counts_exact": not witness_mismatches,
        "target_counts_and_orders_exact": not target_mismatches,
    }
    report = {
        "schema": "o014-english-diagram-ledger-validation-v1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "result": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "rows": len(rows),
        "unit_files": len(by_unit),
        "unique_descriptions": len({row["alt_text_en"].strip() for row in rows}),
        "duplicate_ids": duplicate_ids,
        "duplicate_unit_orders": duplicate_unit_orders,
        "description_defects": defects,
        "witness_mismatches": witness_mismatches,
        "target_mismatches": target_mismatches,
        "ledger_bytes": LEDGER.stat().st_size,
        "ledger_sha256": sha256(LEDGER),
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"result": report["result"], "rows": len(rows),
                      "description_defects": len(defects),
                      "witness_mismatches": len(witness_mismatches),
                      "target_mismatches": len(target_mismatches),
                      "receipt": str(OUT)}))
    if report["result"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
