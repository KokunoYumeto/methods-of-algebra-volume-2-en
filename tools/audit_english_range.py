"""Read-only structural audit for a contiguous English source range.

This tool never edits translations or controls.  It gives translators and the
root admission pass one common set of deterministic diagnostics while leaving
linguistic and mathematical judgment in the signed range receipt.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE_MAP = ROOT / "controls" / "SOURCE_UNIT_MAP.json"

ENV_ROLE = {
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
    "readingguide": "reading-guide",
    "reading-guide": "reading-guide",
    "proposisi": "proposition",
    "teorema": "theorem",
}

INDONESIAN = re.compile(
    r"\b(yang|dengan|adalah|untuk|dari|dalam|pada|sebagai|maka|karena|jika|"
    r"dan|atau|suatu|dapat|akan|kita|ini|tersebut|bukti|latihan|petunjuk|"
    r"teorema|definisi|contoh|catatan|misalkan|sehingga|lihat|bab|bagian)\b",
    re.IGNORECASE,
)
PLACEHOLDER = re.compile(
    r"\b(?:TODO|FIXME|TBD|TRANSLATION\s+PENDING|PLACEHOLDER|XXX)\b",
    re.IGNORECASE,
)
HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

# Fail-closed mathematical corrections already proved and recorded in the
# signed range receipts.  The replacement is applied only to the in-memory
# structural witness used for strict math comparison; source files are never
# changed by this read-only auditor.  Each exact token must occur once on the
# prescribed side, so this cannot hide unrelated formula drift.
APPROVED_WITNESS_MATH_CORRECTIONS = {
    "o014.aljabr2.chapter7.monoidal-algebras": (
        "\\arrow[d, \"{\\mu_M \\otimes \\identity}\"']",
        "\\arrow[d, \"{\\mu_A \\otimes \\identity}\"']",
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_slice_hashes(path: Path, start: int, end: int) -> set[str]:
    """Return exact hashes for the two frozen line-slice conventions in use.

    Early map rows were frozen from LF-joined selected lines, while later rows
    retained the selected final line ending.  Both serialize the same explicit
    inclusive source range; accepting no other variant keeps the check exact.
    """
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    selected = "\n".join(lines[start - 1 : end])
    variants = {selected.encode("utf-8"), (selected + "\n").encode("utf-8")}
    kept = "".join(text.splitlines(keepends=True)[start - 1 : end]).encode("utf-8")
    variants.add(kept)
    return {hashlib.sha256(value).hexdigest() for value in variants}


def strip_comments(text: str) -> str:
    out: list[str] = []
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
        suffix = "\n" if line.endswith(("\n", "\r")) else ""
        out.append(line[:cut].rstrip("\r\n") + suffix)
    return "".join(out)


def captures(pattern: str, text: str) -> list[str]:
    return re.findall(pattern, text, flags=re.MULTILINE)


def canonical_envs(text: str) -> list[tuple[str, str]]:
    return [
        (boundary, ENV_ROLE.get(name, name))
        for boundary, name in re.findall(r"\\(begin|end)\{([^}]+)\}", text)
    ]


def env_stack_ok(text: str) -> bool:
    stack: list[str] = []
    for boundary, name in re.findall(r"\\(begin|end)\{([^}]+)\}", text):
        if boundary == "begin":
            stack.append(name)
        elif not stack or stack.pop() != name:
            return False
    return not stack


def braces_ok(text: str) -> bool:
    depth = 0
    for index, char in enumerate(text):
        if char not in "{}":
            continue
        slashes = 0
        cursor = index - 1
        while cursor >= 0 and text[cursor] == "\\":
            slashes += 1
            cursor -= 1
        if slashes % 2:
            continue
        depth += 1 if char == "{" else -1
        if depth < 0:
            return False
    return depth == 0


def mask_language_commands(text: str) -> str:
    commands = (
        "text", "textrm", "textsf", "textbf", "textit", "textnormal",
        "mbox", "underbrace", "overbrace",
    )
    out: list[str] = []
    cursor = 0
    while cursor < len(text):
        command = next(
            (name for name in commands if text.startswith("\\" + name, cursor)),
            None,
        )
        if command is None:
            out.append(text[cursor])
            cursor += 1
            continue
        brace = cursor + len(command) + 1
        if brace >= len(text) or text[brace] != "{":
            out.append(text[cursor])
            cursor += 1
            continue
        depth = 1
        end = brace + 1
        while end < len(text) and depth:
            if text[end] == "{" and text[end - 1] != "\\":
                depth += 1
            elif text[end] == "}" and text[end - 1] != "\\":
                depth -= 1
            end += 1
        if depth:
            out.append(text[cursor])
            cursor += 1
            continue
        out.append("\\text{<LANG>}")
        cursor = end
    return "".join(out)


def normalized_display_math(text: str) -> Counter[tuple[str, str]]:
    active = strip_comments(text)
    blocks: list[tuple[str, str]] = []
    patterns = (
        ("display", r"\\\[(.*?)\\\]", 1),
        (
            "environment",
            r"\\begin\{(equation\*?|align\*?|alignat\*?|gather\*?|multline\*?)\}"
            r"(.*?)\\end\{\1\}",
            2,
        ),
    )
    for kind, pattern, group in patterns:
        for match in re.finditer(pattern, active, flags=re.DOTALL):
            body = mask_language_commands(match.group(group))
            blocks.append((kind, re.sub(r"\s+", "", body)))
    return Counter(blocks)


def ref_keys(text: str) -> list[str]:
    return re.findall(
        r"\\(?:ref|eqref|pageref|cref|Cref|autoref|sourcecrossref)\{([^}]+)\}",
        text,
    )


def diagram_count(text: str) -> int:
    return len(
        re.findall(
            r"\\begin\{(?:tikzpicture|tikzcd|xy|xymatrix|pspicture)\}", text
        )
    )


def audit(row: dict) -> dict:
    target = ROOT / row["target_path"]
    witness = Path(row["id_reference_path"])
    chinese = Path(row["chinese_source_path"])
    result = {
        "sequence": row["sequence"],
        "unit_id": row["unit_id"],
        "target_path": row["target_path"],
        "checks": {
            "target_exists": target.is_file(),
            "witness_exists": witness.is_file(),
            "chinese_source_exists": chinese.is_file(),
        },
    }
    if not all(result["checks"].values()):
        result["pass"] = False
        return result

    target_text = target.read_text(encoding="utf-8-sig")
    witness_text = witness.read_text(encoding="utf-8-sig")
    active_target = strip_comments(target_text)
    active_witness = strip_comments(witness_text)
    slice_hashes = source_slice_hashes(
        chinese, row["source_start_line"], row["source_end_line"]
    )

    target_segments = captures(r"^%\s*segment-id:\s*(\S+)", target_text)
    witness_segments = captures(r"^%\s*segment-id:\s*(\S+)", witness_text)
    target_labels = captures(r"\\label\{([^}]+)\}", target_text)
    witness_labels = captures(r"\\label\{([^}]+)\}", witness_text)
    target_hypertargets = captures(r"\\hypertarget\{([^}]+)\}", target_text)
    witness_hypertargets = captures(r"\\hypertarget\{([^}]+)\}", witness_text)
    target_cites = captures(
        r"\\(?:cite|parencite|textcite)(?:\[[^]]*\])?\{([^}]+)\}", target_text
    )
    witness_cites = captures(
        r"\\(?:cite|parencite|textcite)(?:\[[^]]*\])?\{([^}]+)\}", witness_text
    )
    # The author acknowledgment contains the proper name Yang Enlin.  Preserve
    # that name while continuing to flag lowercase Indonesian "yang".
    indonesian_hits = [
        match.group(0)
        for match in INDONESIAN.finditer(active_target)
        if match.group(0) != "Yang"
    ]
    han_hits = HAN.findall(active_target)
    placeholder_hits = PLACEHOLDER.findall(active_target)
    math_witness_text = witness_text
    approved_source_math_correction_exact = True
    correction = APPROVED_WITNESS_MATH_CORRECTIONS.get(row["unit_id"])
    if correction is not None:
        witness_token, target_token = correction
        approved_source_math_correction_exact = (
            witness_text.count(witness_token) == 1
            and target_text.count(target_token) == 1
            and target_text.count(witness_token) == 0
        )
        if approved_source_math_correction_exact:
            math_witness_text = witness_text.replace(witness_token, target_token, 1)
    target_math = normalized_display_math(target_text)
    witness_math = normalized_display_math(math_witness_text)

    checks = result["checks"]
    checks.update(
        {
            "source_slice_sha256_exact": row["source_slice_sha256"] in slice_hashes,
            "witness_sha256_exact": sha256(witness) == row["id_reference_sha256"],
            "unit_id_present": row["unit_id"] in target_text,
            "segment_sequence_exact": target_segments == witness_segments,
            "label_sequence_exact": target_labels == witness_labels,
            "hypertarget_sequence_exact": target_hypertargets
            == witness_hypertargets,
            "citation_key_sequence_exact": target_cites == witness_cites,
            "canonical_environment_sequence_exact": canonical_envs(target_text)
            == canonical_envs(witness_text),
            "reference_key_multiset_exact": Counter(ref_keys(target_text))
            == Counter(ref_keys(witness_text)),
            "item_count_exact": len(re.findall(r"\\item\b", target_text))
            == len(re.findall(r"\\item\b", witness_text)),
            "index_command_count_exact": len(re.findall(r"\\index\{", target_text))
            == len(re.findall(r"\\index\{", witness_text)),
            "diagram_count_exact": diagram_count(target_text)
            == diagram_count(witness_text),
            "approved_source_math_correction_exact":
            approved_source_math_correction_exact,
            "normalized_display_math_counter_exact": target_math == witness_math,
            "balanced_braces": braces_ok(active_target),
            "balanced_environment_stack": env_stack_ok(active_target),
            "zero_han_residue": not han_hits,
            "zero_indonesian_residue": not indonesian_hits,
            "zero_placeholders": not placeholder_hits,
            "substantive_length": len(target_text)
            >= max(200, int(len(witness_text) * 0.55)),
            "not_identical_to_witness": sha256(target) != sha256(witness),
        }
    )

    result.update(
        {
            "bytes": target.stat().st_size,
            "lines": len(target_text.splitlines()),
            "target_sha256": sha256(target),
            "source_slice_sha256": row["source_slice_sha256"]
            if row["source_slice_sha256"] in slice_hashes
            else sorted(slice_hashes),
            "witness_sha256": sha256(witness),
            "counts": {
                "segments": len(target_segments),
                "environment_tokens": len(canonical_envs(target_text)),
                "labels": len(target_labels),
                "references": len(ref_keys(target_text)),
                "citation_keys": len(target_cites),
                "math_blocks": sum(target_math.values()),
                "diagrams": diagram_count(target_text),
                "items": len(re.findall(r"\\item\b", target_text)),
                "index_commands": len(re.findall(r"\\index\{", target_text)),
            },
            "residue": {
                "han_count": len(han_hits),
                "indonesian_hits": indonesian_hits[:20],
                "placeholder_hits": placeholder_hits[:20],
            },
            "math_diagnostics": {
                "target_blocks": sum(target_math.values()),
                "witness_blocks": sum(witness_math.values()),
                "target_only_samples": list((target_math - witness_math).elements())[:20],
                "witness_only_samples": list((witness_math - target_math).elements())[:20],
            },
            "failed_checks": [key for key, value in checks.items() if not value],
            "pass": all(checks.values()),
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    if not (1 <= args.start <= args.end <= 146):
        parser.error("range must satisfy 1 <= start <= end <= 146")

    payload = json.loads(SOURCE_MAP.read_text(encoding="utf-8-sig"))
    rows = [
        row
        for row in payload["units"]
        if args.start <= int(row["sequence"]) <= args.end
    ]
    results = [audit(row) for row in rows]
    report = {
        "schema": "o014-english-range-audit-v1",
        "range": {"first_sequence": args.start, "last_sequence": args.end},
        "units_expected": args.end - args.start + 1,
        "units_audited": len(results),
        "units_passing_all_automated_checks": sum(row["pass"] for row in results),
        "result": "PASS"
        if len(results) == args.end - args.start + 1 and all(row["pass"] for row in results)
        else "FAIL",
        "units": results,
    }
    print(json.dumps(report, indent=2 if args.pretty else None, ensure_ascii=False))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
