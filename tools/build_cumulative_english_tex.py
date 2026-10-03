"""Assemble the released modular English source into one direct LaTeX file."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "en"
MASTER = SOURCE / "Al-jabr-2-en-complete-draft.tex"
OUTPUT_DIR = ROOT / "output" / "source"
OUTPUT = OUTPUT_DIR / "methods-of-algebra-volume-2-independent-english-edition-cumulative.tex"
RECEIPT = ROOT / "qa" / "CUMULATIVE_TEX_RECEIPT.json"
SOURCE_MAP = ROOT / "controls" / "SOURCE_UNIT_MAP.json"
INPUT = re.compile(r"(?m)^(?P<indent>[ \t]*)\\input\{(?P<stem>[^{}]+)\}[ \t]*$")
ALLOWED_STEM = re.compile(
    r"(?:prelude-unit-\d{3}|chapter\d+-unit-\d{3}|appendix\d+-unit-\d{3}|"
    r"mastery-bridge-\d{3}-[a-z0-9-]+)"
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def main() -> None:
    mapping = json.loads(SOURCE_MAP.read_text(encoding="utf-8-sig"))
    expected_stems = [Path(row["target_path"]).stem for row in mapping["units"]]
    expected_stems.extend(mapping["bridge_stems"])
    if len(expected_stems) != 148 or len(expected_stems) != len(set(expected_stems)):
        raise SystemExit("source map must name exactly 146 units and two unique bridges")

    master = MASTER.read_text(encoding="utf-8-sig")
    observed_stems = [match.group("stem") for match in INPUT.finditer(master)]
    if observed_stems != expected_stems:
        raise SystemExit("master input sequence differs from the admitted source map")

    inputs: list[dict[str, object]] = []
    expected_segment_ids: list[str] = []

    def expand(match: re.Match[str]) -> str:
        stem = match.group("stem")
        if not ALLOWED_STEM.fullmatch(stem):
            raise SystemExit(f"unapproved input stem: {stem}")
        source = SOURCE / f"{stem}.tex"
        if not source.is_file() or source.is_symlink():
            raise SystemExit(f"missing or unsafe source unit: {source}")
        body = source.read_text(encoding="utf-8-sig").rstrip("\r\n")
        if INPUT.search(body):
            raise SystemExit(f"nested input remains in unit: {source.name}")
        expected_segment_ids.extend(
            re.findall(r"(?m)^% segment-id:\s*(\S+)\s*$", body)
        )
        inputs.append({
            "ordinal": len(inputs) + 1,
            "path": source.relative_to(ROOT).as_posix(),
            "bytes": source.stat().st_size,
            "sha256": sha256(source),
        })
        return (
            f"% BEGIN INLINED SOURCE {len(inputs):03d}/148: {source.name}\n"
            f"{body}\n"
            f"% END INLINED SOURCE {len(inputs):03d}/148: {source.name}"
        )

    assembled = INPUT.sub(expand, master)
    if len(inputs) != 148 or [Path(row["path"]).stem for row in inputs] != expected_stems:
        raise SystemExit("not every admitted unit was inlined exactly once")
    if INPUT.search(assembled) or "\\input{" in assembled:
        raise SystemExit("assembled cumulative source still contains an input command")

    notice = (
        "% DIRECT CUMULATIVE RELEASE SOURCE\n"
        "% This file contains the complete released English text: all 146 source units\n"
        "% and both mastery bridges are inlined below in source order. Copy this file\n"
        "% beside the classes, styles, bibliography, fonts, cover, and assets supplied\n"
        "% in 02_complete-xelatex-source.zip before building.\n"
        "% Assembly is deterministic; see qa/CUMULATIVE_TEX_RECEIPT.json.\n"
        "% Accessible-description correction produced by OpenAI Codex — GPT-5.6 Sol,\n"
        "% Ultra effort. Source authorship and CC BY 4.0 attribution remain unchanged.\n\n"
    )
    if assembled.startswith("%!TEX"):
        first_blank = assembled.find("\n\n")
        assembled = assembled[:first_blank + 2] + notice + assembled[first_blank + 2:]
    else:
        assembled = notice + assembled
    encoded = assembled.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(encoded)

    source_segment_ids = re.findall(r"(?m)^% segment-id:\s*(\S+)\s*$", assembled)
    checks = {
        "master_inputs_148": len(observed_stems) == 148,
        "all_inputs_in_admitted_order": observed_stems == expected_stems,
        "all_unit_bodies_inlined": len(inputs) == 148,
        "no_input_commands_remain": "\\input{" not in assembled,
        "documentclass_preserved": assembled.count("\\documentclass") == 1,
        "document_begin_end_preserved": (
            assembled.count("\\begin{document}") == 1
            and assembled.count("\\end{document}") == 1
        ),
        "all_commented_source_segment_ids_preserved_in_order": (
            source_segment_ids == expected_segment_ids
        ),
        "source_segment_ids_unique": len(source_segment_ids) == len(set(source_segment_ids)),
        "source_map_units_146": len(mapping["units"]) == 146,
        "source_map_bridges_2": len(mapping["bridge_stems"]) == 2,
    }
    receipt = {
        "schema": "o014-english-direct-cumulative-tex-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "result": "PASS" if all(checks.values()) else "FAIL",
        "purpose": "Directly downloadable cumulative editable LaTeX paired with the released PDF and complete source ZIP.",
        "output": {
            "path": OUTPUT.relative_to(ROOT).as_posix(),
            "bytes": OUTPUT.stat().st_size,
            "sha256": sha256(OUTPUT),
        },
        "master": {
            "path": MASTER.relative_to(ROOT).as_posix(),
            "bytes": MASTER.stat().st_size,
            "sha256": sha256(MASTER),
        },
        "source_map": {
            "path": SOURCE_MAP.relative_to(ROOT).as_posix(),
            "bytes": SOURCE_MAP.stat().st_size,
            "sha256": sha256(SOURCE_MAP),
        },
        "source_commit": "9a5803ff77dd3257484cb177f851a73770a59dd3",
        "source_tree": "23bd05c2fb8434278df4fdfb636559a6a2b0d2ff",
        "license": "CC-BY-4.0",
        "checks": checks,
        "inlined_inputs": inputs,
        "build_note": "The cumulative file is textually identical to the modular master after deterministic input expansion. Required classes, styles, bibliography, fonts, cover, and assets remain in the adjacent complete source ZIP.",
    }
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "result": receipt["result"],
        "inputs": len(inputs),
        "segments": len(source_segment_ids),
        "bytes": receipt["output"]["bytes"],
        "sha256": receipt["output"]["sha256"],
    }))
    if receipt["result"] != "PASS":
        failed = [name for name, value in checks.items() if not value]
        raise SystemExit("failed checks: " + ", ".join(failed))


if __name__ == "__main__":
    main()
