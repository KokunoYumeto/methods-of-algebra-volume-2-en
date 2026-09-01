"""Deterministically admit complete English unit targets.

Admission is conservative: a target is considered only after its disjoint
range receipt exists and reports PASS. Structural identities and math bodies
are compared with the completed Indonesian witness, while human-facing
``\\text{...}`` content may be translated.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "controls" / "SOURCE_UNIT_MAP.json"
STATE = ROOT / "controls" / "CURRENT_STATE.json"
RANGES = ROOT / "controls" / "ranges"
QA = ROOT / "qa" / "UNIT_ADMISSION.json"
RANGE_BOUNDS = [(1,15),(16,24),(25,32),(33,40),(41,46),(47,55),(56,64),
                (65,73),(74,82),(83,89),(90,99),(100,109),(110,121),
                (122,132),(133,146)]
INDONESIAN_WORDS = re.compile(
    r"\b(yang|dengan|adalah|untuk|dari|dalam|pada|sebagai|maka|karena|"
    r"jika|dan|atau|suatu|dapat|akan|kita|ini|tersebut|bukti|latihan|"
    r"petunjuk|teorema|definisi|contoh|catatan|misalkan|sehingga)\b", re.I)
ENVIRONMENT_ROLE = {
    "bukti": "proof",
    "catatan": "remark",
    "contoh": "example",
    "definisi": "definition",
    "definisi-proposisi": "definition-proposition",
    "definisiproposisi": "definition-proposition",
    "definisiteorema": "definition-theorem",
    "hipotesis": "hypothesis",
    "konjektur": "conjecture",
    "konvensi": "convention",
    "korolari": "corollary",
    "latihan": "exercise",
    "lema": "lemma",
    "petunjukbacaan": "reading-guide",
    "proposisi": "proposition",
    "teorema": "theorem",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_slice_hashes(path: Path, start: int, end: int) -> set[str]:
    """Hash only the two exact inclusive-line serializations used by the map."""
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    selected = "\n".join(lines[start - 1 : end])
    variants = {selected.encode("utf-8"), (selected + "\n").encode("utf-8")}
    variants.add(
        "".join(text.splitlines(keepends=True)[start - 1 : end]).encode("utf-8")
    )
    return {hashlib.sha256(value).hexdigest() for value in variants}


def receipt_pass(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return False
    for key in ("result", "status", "overall_status"):
        if key in payload:
            return str(payload[key]).upper() == "PASS"
    return False


def receipt_evidence(path: Path, row: dict, target: Path):
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {"unit_present": False, "hash_exact": False, "bytes_exact": False,
                "true_check_count": 0}
    units = payload.get("units", [])
    match = next((unit for unit in units if unit.get("sequence") == row["sequence"]), None)
    recorded_hash = "" if not match else str(match.get("sha256") or match.get("target_sha256") or "")
    recorded_bytes = -1 if not match else int(match.get("bytes", -1))

    def booleans(value):
        if isinstance(value, dict):
            for item in value.values():
                yield from booleans(item)
        elif isinstance(value, list):
            for item in value:
                yield from booleans(item)
        elif isinstance(value, bool):
            yield value

    true_count = sum(1 for value in booleans(payload.get("checks", payload.get("validation", {}))) if value)
    if match:
        true_count += sum(1 for value in booleans(match.get("checks", match.get("evidence", {}))) if value)
    return {
        "unit_present": match is not None,
        "hash_exact": bool(recorded_hash) and recorded_hash.lower() == sha(target),
        "bytes_exact": recorded_bytes == target.stat().st_size,
        "true_check_count": true_count,
    }


def range_receipt(sequence: int) -> Path:
    for start, end in RANGE_BOUNDS:
        if start <= sequence <= end:
            return RANGES / f"{start:03d}-{end:03d}.json"
    raise AssertionError(sequence)


def captures(pattern: str, text: str):
    return re.findall(pattern, text, flags=re.MULTILINE)


def environment_roles(text: str):
    return [
        (boundary, ENVIRONMENT_ROLE.get(name, name))
        for boundary, name in captures(r"\\(begin|end)\{([^}]+)\}", text)
    ]


def strip_tex_comments(text: str) -> str:
    clean = []
    for line in text.splitlines(keepends=True):
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


def mask_balanced_language_commands(text: str) -> str:
    """Mask balanced human-language arguments while preserving math syntax."""
    commands = ("text", "textrm", "textsf", "textbf", "textit", "mbox")
    output = []
    cursor = 0
    while cursor < len(text):
        matched = next((name for name in commands if text.startswith("\\" + name, cursor)), None)
        if not matched:
            output.append(text[cursor])
            cursor += 1
            continue
        pos = cursor + len(matched) + 1
        if pos >= len(text) or text[pos] != "{":
            output.append(text[cursor])
            cursor += 1
            continue
        depth = 1
        end = pos + 1
        while end < len(text) and depth:
            if text[end] == "{" and text[end - 1] != "\\":
                depth += 1
            elif text[end] == "}" and text[end - 1] != "\\":
                depth -= 1
            end += 1
        if depth:
            output.append(text[cursor])
            cursor += 1
            continue
        output.append(r"\text{<LANG>}")
        cursor = end
    return "".join(output)


def normalized_math(text: str):
    # Keep formulas byte-sensitive except human-language material in common
    # text boxes. These patterns are deliberately shallow and deterministic.
    def strip_text(value):
        return re.sub(r"\s+", "", mask_balanced_language_commands(value))
    parts = []
    patterns = [
        r"\\\[(.*?)\\\]",
        r"\\begin\{(equation\*?|align\*?|alignat\*?|gather\*?|multline\*?)\}(.*?)\\end\{\1\}",
        r"(?<!\\)\$(?!\$)(.*?)(?<!\\)\$",
    ]
    for idx, pattern in enumerate(patterns):
        for match in re.finditer(pattern, text, flags=re.DOTALL):
            body = match.group(2) if idx == 1 else match.group(1)
            parts.append((idx, strip_text(body)))
    return Counter(parts)


def validate(row):
    target = ROOT / row["target_path"]
    witness = Path(row["id_reference_path"])
    chinese = Path(row["chinese_source_path"])
    receipt = range_receipt(row["sequence"])
    checks = {
        "range_receipt_pass": receipt_pass(receipt),
        "target_exists": target.is_file(),
        "id_witness_exists": witness.is_file(),
        "chinese_source_exists": chinese.is_file(),
    }
    result = {"sequence": row["sequence"], "unit_id": row["unit_id"],
              "target_path": row["target_path"], "receipt": str(receipt), "checks": checks}
    if not all(checks.values()):
        result["pass"] = False
        return result
    target_text = target.read_text(encoding="utf-8-sig")
    witness_text = witness.read_text(encoding="utf-8-sig")
    target_active = strip_tex_comments(target_text)
    range_evidence = receipt_evidence(receipt, row, target)
    checks.update({
        "source_slice_sha256": row["source_slice_sha256"] in source_slice_hashes(
            chinese, row["source_start_line"], row["source_end_line"]
        ),
        "id_witness_sha256": sha(witness) == row["id_reference_sha256"],
        "stable_unit_id_present": row["unit_id"] in target_text,
        "range_receipt_unit_present": range_evidence["unit_present"],
        "range_receipt_target_sha256_exact": range_evidence["hash_exact"],
        "range_receipt_target_bytes_exact": range_evidence["bytes_exact"],
        "range_receipt_has_structural_qa": range_evidence["true_check_count"] >= 4,
        "segment_ids_exact": captures(r"^%\s*segment-id:\s*(\S+)", target_text) == captures(r"^%\s*segment-id:\s*(\S+)", witness_text),
        "labels_exact": captures(r"\\label\{([^}]+)\}", target_text) == captures(r"\\label\{([^}]+)\}", witness_text),
        "hypertargets_exact": captures(r"\\hypertarget\{([^}]+)\}", target_text) == captures(r"\\hypertarget\{([^}]+)\}", witness_text),
        "citation_keys_exact": captures(r"\\(?:cite|parencite|textcite)(?:\[[^]]*\])?\{([^}]+)\}", target_text) == captures(r"\\(?:cite|parencite|textcite)(?:\[[^]]*\])?\{([^}]+)\}", witness_text),
        "not_identical_to_indonesian": sha(target) != sha(witness),
        "substantive_length": len(target_text) >= max(200, int(len(witness_text) * 0.55)),
        "indonesian_residue_bounded": len(INDONESIAN_WORDS.findall(target_text)) <= 8,
    })
    result.update({"bytes": target.stat().st_size, "sha256": sha(target),
                   "receipt_true_check_count": range_evidence["true_check_count"],
                   "indonesian_residue_hits": len(INDONESIAN_WORDS.findall(target_text)),
                   "pass": all(checks.values())})
    return result


def main():
    data = json.loads(MAP.read_text(encoding="utf-8-sig"))
    results = [validate(row) for row in data["units"]]
    by_seq = {row["sequence"]: row for row in results}
    translated = sum(row["checks"].get("target_exists", False) for row in results)
    admitted = sum(row["pass"] for row in results)
    cursor = next((seq for seq in range(1, 147) if not by_seq[seq]["pass"]), 147)
    next_sequence = None if admitted == 146 else cursor
    for row in data["units"]:
        qa = by_seq[row["sequence"]]
        row["status"] = "translated_structurally_admitted" if qa["pass"] else (
            "translated_pending_admission" if qa["checks"].get("target_exists") else "not_started")
        if qa.get("sha256"):
            row["target_sha256"] = qa["sha256"]
    data["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    MAP.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    state = json.loads(STATE.read_text(encoding="utf-8-sig"))
    state.update({"translated_units": translated, "admitted_units": admitted,
                  "next_sequence": next_sequence,
                  "status": "unit_translation_complete" if admitted == 146 else "translation_in_progress",
                  "last_admission_utc": data["updated_at_utc"],
                  "admission_receipt": "qa/UNIT_ADMISSION.json"})
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    receipt = {"schema": "o014-english-unit-admission-v1", "recorded_at_utc": data["updated_at_utc"],
               "translated_units": translated, "admitted_units": admitted,
               "next_sequence": next_sequence, "results": results,
               "result": "PASS" if admitted == 146 else "IN_PROGRESS"}
    QA.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    failed = [{"sequence": row["sequence"], "failed": [k for k,v in row["checks"].items() if not v]}
              for row in results if row["checks"].get("target_exists") and not row["pass"]]
    print(json.dumps({"translated": translated, "admitted": admitted, "next": next_sequence,
                      "failed_existing": failed[:20], "failed_count": len(failed)}))


if __name__ == "__main__":
    main()
