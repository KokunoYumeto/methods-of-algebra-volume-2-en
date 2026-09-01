"""Inventory every active TikZ diagram and align the inherited 829 rows.

The output is a review aid, not a finished accessibility ledger.  It preserves
all existing diagram IDs/descriptions where their frozen provenance line maps
to a source environment, assigns collision-free IDs to previously omitted
inline/bridge diagrams, and embeds the exact TeX body for bounded human/model
description repair.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from validate_english_diagram_ledger import ROOT, SOURCE, strip_tex_comments


MAP = ROOT / "controls" / "SOURCE_UNIT_MAP.json"
LEDGER = ROOT / "backend" / "figure-alt-text-en.csv"
OUT = ROOT / "qa" / "DIAGRAM_SOURCE_INVENTORY.jsonl"
RECEIPT = ROOT / "qa" / "DIAGRAM_SOURCE_INVENTORY_RECEIPT.json"
ENVIRONMENT = re.compile(
    r"\\begin\{(tikzcd|tikzpicture)\}(.*?)\\end\{\1\}", re.DOTALL
)
PROVENANCE_LINE = re.compile(r":(\d+)(?:;|$)")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def occurrences(path: Path) -> list[dict[str, object]]:
    clean = strip_tex_comments(path.read_text(encoding="utf-8-sig"))
    found = []
    for order, match in enumerate(ENVIRONMENT.finditer(clean), 1):
        found.append({
            "actual_order": order,
            "line": clean.count("\n", 0, match.start()) + 1,
            "environment": match.group(1),
            "tex_body": match.group(2).strip(),
        })
    return found


def align_existing(unit: str, diagrams: list[dict[str, object]], rows: list[dict[str, str]]):
    ordered_rows = sorted(rows, key=lambda value: int(value["local_order"]))
    failures = []
    provenance_lines = []
    for row in ordered_rows:
        match = PROVENANCE_LINE.search(row["provenance"])
        if not match:
            failures.append({"diagram_id": row["diagram_id"], "reason": "no_provenance_line"})
        provenance_lines.append(int(match.group(1)) if match else 0)
    if failures:
        return {}, failures
    if len(diagrams) < len(ordered_rows):
        return {}, [{"unit_filename": unit, "reason": "fewer_environments_than_inherited_rows",
                     "environments": len(diagrams), "inherited_rows": len(ordered_rows)}]

    # Ordered minimum-cost alignment.  Existing rows and active environments
    # are both source-ordered; omitted inline diagrams are skips.  Provenance
    # line distance chooses the skipped positions without brittle thresholds.
    m, n = len(ordered_rows), len(diagrams)
    infinity = 10**18
    cost = [[infinity] * (n + 1) for _ in range(m + 1)]
    choice = [[""] * (n + 1) for _ in range(m + 1)]
    for j in range(n + 1):
        cost[0][j] = 0
        choice[0][j] = "skip"
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if cost[i][j - 1] < cost[i][j]:
                cost[i][j] = cost[i][j - 1]
                choice[i][j] = "skip"
            prior = cost[i - 1][j - 1]
            if prior < infinity:
                distance = abs(int(diagrams[j - 1]["line"]) - provenance_lines[i - 1])
                candidate = prior + distance
                if candidate <= cost[i][j]:
                    cost[i][j] = candidate
                    choice[i][j] = "match"
    if cost[m][n] >= infinity:
        return {}, [{"unit_filename": unit, "reason": "ordered_alignment_failed"}]
    mapped: dict[int, dict[str, str]] = {}
    i, j = m, n
    while i:
        if j <= 0:
            return {}, [{"unit_filename": unit, "reason": "alignment_backtrack_failed"}]
        if choice[i][j] == "match":
            row = dict(ordered_rows[i - 1])
            row["alignment_line_distance"] = str(
                abs(int(diagrams[j - 1]["line"]) - provenance_lines[i - 1])
            )
            mapped[int(diagrams[j - 1]["actual_order"])] = row
            i -= 1
            j -= 1
        else:
            j -= 1
    return mapped, []


def main() -> None:
    mapping = json.loads(MAP.read_text(encoding="utf-8-sig"))
    sources = [
        (Path(row["target_path"]).name, Path(row["id_reference_path"]), ROOT / row["target_path"],
         "mapped_indonesian_structure_witness")
        for row in mapping["units"]
    ]
    sources.extend(
        (f"{stem}.tex", SOURCE / f"{stem}.tex", SOURCE / f"{stem}.tex",
         "independent_mastery_bridge_source")
        for stem in mapping["bridge_stems"]
    )
    with LEDGER.open(encoding="utf-8-sig", newline="") as stream:
        inherited = list(csv.DictReader(stream))
    inherited_by_unit: dict[str, list[dict[str, str]]] = {}
    for row in inherited:
        inherited_by_unit.setdefault(row["unit_filename"], []).append(row)

    inventory = []
    failures = []
    reused = 0
    added = 0
    for unit, source, target, source_relationship in sources:
        diagrams = occurrences(source)
        # Inherited provenance lines refer to source/en targets.  Align against
        # that line space, then reuse the ordinal in the structurally identical
        # frozen witness so translated line wrapping cannot shift identities.
        alignment_diagrams = occurrences(target) if target.is_file() else diagrams
        if len(alignment_diagrams) < len(inherited_by_unit.get(unit, [])):
            alignment_diagrams = diagrams
        aligned, unit_failures = align_existing(unit, alignment_diagrams, inherited_by_unit.get(unit, []))
        failures.extend({"unit_filename": unit, **failure} for failure in unit_failures)
        stem = Path(unit).stem
        for diagram in diagrams:
            order = int(diagram["actual_order"])
            prior = aligned.get(order)
            if prior:
                diagram_id = prior["diagram_id"]
                description = prior["alt_text_en"].strip()
                disposition = "inherited_description_requires_validation"
                reused += 1
            else:
                diagram_id = f"{stem}-diagram-{order:03d}"
                description = ""
                disposition = "missing_description_requires_authoring"
                added += 1
            inventory.append({
                "diagram_id": diagram_id,
                "unit_filename": unit,
                "actual_order": order,
                "source_line": diagram["line"],
                "environment": diagram["environment"],
                "source_relationship": source_relationship,
                "description_en": description,
                "disposition": disposition,
                "inherited_alignment_line_distance": int(prior["alignment_line_distance"]) if prior else None,
                "tex_body": diagram["tex_body"],
            })

    with OUT.open("w", encoding="utf-8", newline="\n") as stream:
        for row in inventory:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    ids = [row["diagram_id"] for row in inventory]
    initial_expansion = len(inherited) == 829 and reused == 829 and added == 78
    complete_revalidation = (
        len(inherited) == 907
        and reused == 907
        and added == 0
        and all(str(row["description_en"]).strip() for row in inventory)
    )
    checks = {
        "inventory_907": len(inventory) == 907,
        "recognized_inventory_transition": initial_expansion or complete_revalidation,
        "initial_829_to_907_expansion_or_complete_907_revalidation": (
            initial_expansion or complete_revalidation
        ),
        "diagram_ids_unique": len(ids) == len(set(ids)),
        "alignment_failures_zero": not failures,
        "all_source_bodies_nonempty": all(str(row["tex_body"]).strip() for row in inventory),
    }
    receipt = {
        "schema": "o014-english-complete-diagram-inventory-v2",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "result": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "inventory_rows": len(inventory),
        "inherited_ledger_rows": len(inherited),
        "inherited_rows_aligned": reused,
        "new_descriptions_required": added,
        "transition_mode": (
            "initial_829_to_907_expansion"
            if initial_expansion
            else "complete_907_row_revalidation"
            if complete_revalidation
            else "unrecognized"
        ),
        "alignment_failures": failures,
        "inventory_bytes": OUT.stat().st_size,
        "inventory_sha256": sha256(OUT),
        "inherited_ledger_sha256": sha256(LEDGER),
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"result": receipt["result"], "rows": len(inventory),
                      "reused": reused, "new": added, "failures": len(failures),
                      "inventory_sha256": receipt["inventory_sha256"]}))
    if receipt["result"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
