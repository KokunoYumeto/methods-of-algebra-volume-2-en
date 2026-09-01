"""Build the locale-linked English backend after all unit admissions pass."""

from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
ID = Path(r"C:\Users\Floris\Documents\interlanguage\04_mirrors\id\methods-of-algebra-volume-2-id")
BACKEND = ROOT / "backend"
TERM_OVERRIDES = BACKEND / "term-overrides-en.csv"

# The Chinese authority has two compound term-index entries whose English
# components are more useful as separately searchable entries.  Every other
# unit remains a strict one-to-one index alignment.  The tuples map an
# authority/Indonesian ordinal to one or more English ordinals.
DOCUMENTED_INDEX_EXPANSIONS = {
    "o014.aljabr2.chapter3.classical-derived-functors": {
        "authority_count": 8,
        "english_count": 9,
        "alignment": (
            (0, (0,)), (1, (1,)), (2, (2,)), (3, (3,)),
            (4, (4,)), (5, (5,)), (6, (6, 7)), (7, (8,)),
        ),
        "reason": (
            "The authority's compound effaceable/co-effaceable entry is "
            "split into two English lookup entries."
        ),
    },
    "o014.aljabr2.chapter3.example-lim1": {
        "authority_count": 2,
        "english_count": 3,
        "alignment": ((0, (0, 1)), (1, (2,))),
        "reason": (
            "The authority's compound exact-countable-products-or-coproducts "
            "entry is split into two English lookup entries."
        ),
    },
}


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def balanced_arguments(text, command):
    out, pos = [], 0
    needle = "\\" + command
    while True:
        at = text.find(needle, pos)
        if at < 0: break
        cur = at + len(needle)
        if cur < len(text) and text[cur] == "*": cur += 1
        while cur < len(text) and text[cur].isspace(): cur += 1
        if cur >= len(text) or text[cur] != "{":
            pos = cur; continue
        depth, start = 1, cur + 1; cur += 1
        while cur < len(text) and depth:
            if text[cur] == "{" and (cur == 0 or text[cur-1] != "\\"): depth += 1
            elif text[cur] == "}" and (cur == 0 or text[cur-1] != "\\"): depth -= 1
            cur += 1
        if depth == 0: out.append(text[start:cur-1])
        pos = cur
    return out


def plain(value):
    value = re.sub(r"\\(?:emph|textbf|textit|texttt|mathrm|mathcal|cate|mathsf)\{([^{}]*)\}", r"\1", value)
    value = re.sub(r"\\[A-Za-z@]+\*?", "", value)
    return re.sub(r"\s+", " ", value.replace("{", "").replace("}", "")).strip(" .")


def visible_index(value):
    value = value.split("@", 1)[-1]
    return re.sub(r"\s*\([^()]*(?:English|Inggris)?[^()]*\)\s*$", "", value).strip()


def load_term_overrides(path, id_terms):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["concept_id", "preferred_en"]:
            raise SystemExit(
                f"{path} must have exactly the columns concept_id,preferred_en"
            )
        rows = list(reader)

    expected_ids = {row["concept_id"] for row in id_terms}
    overrides = {}
    duplicates = []
    blank_values = []
    for row in rows:
        concept_id = row["concept_id"].strip()
        preferred_en = row["preferred_en"].strip()
        if concept_id in overrides:
            duplicates.append(concept_id)
        if not concept_id or not preferred_en:
            blank_values.append(concept_id or "<blank-concept-id>")
        overrides[concept_id] = preferred_en

    missing = sorted(expected_ids - overrides.keys())
    unknown = sorted(overrides.keys() - expected_ids)
    if duplicates or blank_values or missing or unknown:
        details = []
        if duplicates:
            details.append("duplicate=" + ",".join(sorted(set(duplicates))))
        if blank_values:
            details.append("blank=" + ",".join(sorted(set(blank_values))))
        if missing:
            details.append("missing=" + ",".join(missing))
        if unknown:
            details.append("unknown=" + ",".join(unknown))
        raise SystemExit("Invalid English term overrides: " + "; ".join(details))
    return overrides


def main():
    source_map = json.loads((ROOT / "controls" / "SOURCE_UNIT_MAP.json").read_text(encoding="utf-8-sig"))
    admission = json.loads((ROOT / "qa" / "UNIT_ADMISSION.json").read_text(encoding="utf-8-sig"))
    if admission.get("result") != "PASS" or admission.get("admitted_units") != 146:
        raise SystemExit("All 146 units must pass admission before backend generation")

    with (ID / "backend" / "terms.csv").open(encoding="utf-8-sig", newline="") as stream:
        id_terms = list(csv.DictReader(stream))
    term_overrides = load_term_overrides(TERM_OVERRIDES, id_terms)

    units = []
    index_pairs = []
    index_alignment_mismatches = []
    index_alignment_expansions = []
    unit_text = {}
    for row in source_map["units"]:
        path = ROOT / row["target_path"]
        text = path.read_text(encoding="utf-8-sig")
        unit_text[row["unit_id"]] = (path, text)
        headings = []
        for command in ("chapter", "section", "subsection"):
            headings.extend((text.find("\\" + command), plain(value)) for value in balanced_arguments(text, command))
        headings = [item for item in headings if item[0] >= 0 and item[1]]
        headings.sort()
        title = headings[0][1] if headings else row["unit_id"].split(".")[-1].replace("-", " ").title()
        if row["sequence"] == 1 and len(headings) > 1:
            title = f"{headings[0][1]} — {headings[1][1]}"
        record = {key: value for key, value in row.items() if key not in {"title_id", "id_reference_path", "id_reference_sha256", "chinese_source_path"}}
        record.update({"title_en": title, "locale": "en", "status": "translated_built_pending",
                       "target_sha256": sha(path), "target_bytes": path.stat().st_size})
        units.append(record)
        id_text = Path(row["id_reference_path"]).read_text(encoding="utf-8-sig")
        id_indexes = balanced_arguments(id_text, "index")
        authority_lines = Path(row["chinese_source_path"]).read_text(
            encoding="utf-8-sig"
        ).splitlines()
        authority_slice = "\n".join(
            authority_lines[row["source_start_line"] - 1:row["source_end_line"]]
        )
        authority_indexes = balanced_arguments(authority_slice, "index")
        english_indexes = balanced_arguments(text, "index")
        if len(authority_indexes) == len(id_indexes) == len(english_indexes):
            index_pairs.extend(
                (plain(visible_index(a)).casefold(), plain(visible_index(b)))
                for a, b in zip(id_indexes, english_indexes)
            )
        else:
            expansion = DOCUMENTED_INDEX_EXPANSIONS.get(row["unit_id"])
            exact_expansion = (
                expansion
                and len(authority_indexes) == len(id_indexes)
                == expansion["authority_count"]
                and len(english_indexes) == expansion["english_count"]
            )
            if exact_expansion:
                for left_index, right_indexes in expansion["alignment"]:
                    index_pairs.extend(
                        (
                            plain(visible_index(id_indexes[left_index])).casefold(),
                            plain(visible_index(english_indexes[right_index])),
                        )
                        for right_index in right_indexes
                    )
                index_alignment_expansions.append({
                    "unit_id": row["unit_id"],
                    "authority_index_entries": len(authority_indexes),
                    "id_index_entries": len(id_indexes),
                    "en_index_entries": len(english_indexes),
                    "reason": expansion["reason"],
                })
            else:
                index_alignment_mismatches.append({
                    "unit_id": row["unit_id"],
                    "authority_index_entries": len(authority_indexes),
                    "id_index_entries": len(id_indexes),
                    "en_index_entries": len(english_indexes),
                })
    write_jsonl(BACKEND / "units.jsonl", units)

    segment_templates = [json.loads(line) for line in (ID / "backend" / "segments.jsonl").read_text(encoding="utf-8-sig").splitlines() if line]
    segments = []
    for unit_id, group in __import__("itertools").groupby(segment_templates, key=lambda row: row["unit_id"]):
        group = list(group)
        path, text = unit_text[unit_id]
        lines = text.splitlines()
        marker_lines = {}
        for number, line in enumerate(lines, 1):
            match = re.match(r"%\s*segment-id:\s*(\S+)", line)
            if match: marker_lines[match.group(1)] = number
        ordered_markers = sorted(marker_lines.items(), key=lambda item: item[1])
        next_line = {seg: (ordered_markers[i+1][1]-1 if i+1 < len(ordered_markers) else len(lines))
                     for i,(seg,_) in enumerate(ordered_markers)}
        for template in group:
            row = dict(template)
            row["locale"] = "en"
            row["target_path"] = str(path.relative_to(ROOT)).replace("\\", "/")
            marker = marker_lines.get(row["segment_id"])
            if marker:
                row.update({"target_marker_line": marker, "target_start_line": marker+1,
                            "target_end_line": next_line[row["segment_id"]]})
            segments.append(row)
    write_jsonl(BACKEND / "segments.jsonl", segments)

    pair_map = {}
    for id_term, en_term in index_pairs:
        if id_term and en_term and id_term not in pair_map: pair_map[id_term] = en_term
    aligned_index_concepts = sum(
        plain(row["preferred_id"]).casefold() in pair_map for row in id_terms
    )
    terms = []
    for row in id_terms:
        value = term_overrides[row["concept_id"]]
        terms.append({"concept_id": row["concept_id"], "preferred_en": value,
                      "locale": "en", "source_course_ids": row["source_course_ids"],
                      "status": "active", "derivation": "curated_override"})
    with (BACKEND / "terms.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=terms[0].keys()); writer.writeheader(); writer.writerows(terms)

    bridges = []
    for sequence, stem in enumerate(source_map["bridge_stems"], 1):
        path = ROOT / "source" / "en" / f"{stem}.tex"
        bridges.append({"bridge_id": f"o014.aljabr2.{stem}", "sequence": sequence,
                        "locale": "en", "source_relationship": "independent_course_addition",
                        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                        "bytes": path.stat().st_size, "sha256": sha(path), "license_id": "CC-BY-4.0"})
    write_jsonl(BACKEND / "bridges.jsonl", bridges)

    figure_rows = list(csv.DictReader((BACKEND / "figure-alt-text-en.csv").open(encoding="utf-8-sig", newline="")))
    checks = {
        "units_146": len(units) == 146,
        "unit_ids_unique": len({row["unit_id"] for row in units}) == 146,
        "unit_locale_en": all(row["locale"] == "en" for row in units),
        "segments_6347": len(segments) == 6347,
        "segment_ids_unique": len({row["segment_id"] for row in segments}) == 6347,
        "terms_511": len(terms) == 511,
        "term_ids_unique": len({row["concept_id"] for row in terms}) == len(terms),
        "term_preferred_en_nonempty": all(row["preferred_en"].strip() for row in terms),
        "term_unresolved_zero": all(row["status"] == "active" for row in terms),
        "figures_907": len(figure_rows) == 907,
        "figure_ids_unique": len({row["diagram_id"] for row in figure_rows})
        == len(figure_rows) == 907,
        "bridges_2": len(bridges) == 2,
        "index_alignment_mismatches_zero": not index_alignment_mismatches,
    }
    report = {"schema": "o014-english-backend-validation-v1", "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
              "checks": checks, "term_fallback_count": 0, "term_unresolved_count": 0,
              "term_override_count": len(term_overrides),
              "term_aligned_index_concept_count": aligned_index_concepts,
              "term_aligned_index_pair_count": len(index_pairs),
              "term_aligned_index_key_count": len(pair_map),
              "index_alignment_mismatches": index_alignment_mismatches,
              "index_alignment_expansions": index_alignment_expansions,
              "term_override_input": {"path": str(TERM_OVERRIDES.relative_to(ROOT)).replace("\\", "/"),
                                      "bytes": TERM_OVERRIDES.stat().st_size,
                                      "sha256": sha(TERM_OVERRIDES)},
              "result": "PASS" if all(checks.values()) else "FAIL",
              "artifacts": {name: {"bytes": (BACKEND/name).stat().st_size, "sha256": sha(BACKEND/name)}
                            for name in ["units.jsonl","segments.jsonl","terms.csv","figure-alt-text-en.csv","bridges.jsonl"]}}
    (BACKEND / "BACKEND_VALIDATION.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"result": report["result"], "units": len(units), "segments": len(segments),
                      "terms": len(terms), "term_fallback": 0, "term_unresolved": 0,
                      "figures": len(figure_rows), "bridges": len(bridges)}))
    if report["result"] != "PASS": raise SystemExit(1)


if __name__ == "__main__": main()
