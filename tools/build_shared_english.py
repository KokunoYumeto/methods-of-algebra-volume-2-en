"""Validate the canonical shared English source layer.

The historical filename is retained because release tooling already refers to
it.  Shared files are now authored canonical inputs; regenerating them from the
Indonesian edition would overwrite later English corrections.  This command is
therefore deliberately read-only except for its deterministic QA receipt.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "en"
SOURCE_MAP = ROOT / "controls" / "SOURCE_UNIT_MAP.json"
RECEIPT = ROOT / "qa" / "SHARED_SOURCE_VALIDATION.json"
MASTER = SOURCE / "Al-jabr-2-en-complete-draft.tex"
SHARED = (
    MASTER,
    SOURCE / "coverpage-en.tex",
    SOURCE / "font-setup-en.tex",
    SOURCE / "titles-setup-en.tex",
    SOURCE / "Al-jabr.bib",
    SOURCE / "mycommand.sty",
    SOURCE / "myarrows.sty",
    SOURCE / "AJbook2.cls",
)
HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
INDONESIAN = re.compile(
    r"\b(?:bahasa|indonesia|sampul|penulis|tanggal|diterbitkan|karya|"
    r"lisensi|bab|bagian|lampiran|yang|dengan|adalah|untuk|dari|dalam|"
    r"pada|sebagai|maka|karena|jika|dan|atau|suatu|kita|tersebut)\b",
    re.IGNORECASE,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def main() -> None:
    mapping = json.loads(SOURCE_MAP.read_text(encoding="utf-8-sig"))
    expected_units = [Path(row["target_path"]).stem for row in mapping["units"]]
    expected_bridges = list(mapping["bridge_stems"])
    expected_inputs = expected_units + expected_bridges
    master_text = MASTER.read_text(encoding="utf-8-sig")
    actual_inputs = re.findall(r"^\\input\{([^}]+)\}$", master_text, re.MULTILINE)
    missing_inputs = [name for name in expected_inputs if not (SOURCE / f"{name}.tex").is_file()]

    active_shared = {
        path.name: strip_comments(path.read_text(encoding="utf-8-sig"))
        for path in SHARED[:4]
        if path.is_file()
    }
    residue = {
        name: {
            "han": HAN.findall(text)[:20],
            "indonesian": [match.group(0) for match in INDONESIAN.finditer(text)][:20],
        }
        for name, text in active_shared.items()
        if HAN.search(text) or INDONESIAN.search(text)
    }

    checks = {
        "source_map_146_units": len(expected_units) == 146,
        "source_map_2_bridges": len(expected_bridges) == 2,
        "shared_files_present": all(path.is_file() for path in SHARED),
        "master_input_sequence_exact": actual_inputs == expected_inputs,
        "all_148_input_files_present": not missing_inputs,
        "pdf_language_en": "pdflang={en}" in master_text,
        "source_author_preserved": "pdfauthor={Wen-Wei Li}" in master_text,
        "license_and_nonendorsement_present": (
            "Creative Commons Attribution 4.0 International" in master_text
            and "do not endorse" in master_text
        ),
        "model_provenance_present": "OpenAI Codex" in master_text
        and "gpt-5.6-sol, Ultra" in master_text,
        "english_visible_environment_labels": all(
            token in master_text
            for token in (
                "{Theorem}", "{Definition}", "{Example}", "{Remark}",
                "{Exercise}", "{Proof}", "title={Reading Guide}",
            )
        ),
        "deterministic_release_date": "September 1, 2026" in master_text,
        "zero_active_shared_language_residue": not residue,
    }
    report = {
        "schema": "o014-english-shared-source-validation-v1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "result": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "input_counts": {
            "units": len(expected_units),
            "bridges": len(expected_bridges),
            "master_inputs": len(actual_inputs),
        },
        "missing_inputs": missing_inputs,
        "active_language_residue": residue,
        "artifacts": {
            str(path.relative_to(ROOT)).replace("\\", "/"): {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in SHARED
            if path.is_file()
        },
    }
    RECEIPT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "result": report["result"],
                "master_inputs": len(actual_inputs),
                "missing_inputs": len(missing_inputs),
                "residue_files": len(residue),
                "receipt": str(RECEIPT),
            }
        )
    )
    if report["result"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
