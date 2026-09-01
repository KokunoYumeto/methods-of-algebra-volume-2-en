"""Build and validate the complete English offline HTML reader once."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
READER = ROOT / "reader"
DIST = READER / "dist"
MASTER = ROOT / "source" / "en" / "Al-jabr-2-en-complete-draft.tex"
LEDGER = ROOT / "backend" / "figure-alt-text-en.csv"
RECEIPT = ROOT / "qa" / "HTML_BUILD_RECEIPT.json"
SOURCE_FREEZE = ROOT / "controls" / "SOURCE_FREEZE.json"
EXPECTED_UNITS_AND_BRIDGES = 148
EXPECTED_LOGICAL_SECTIONS = 149
EXPECTED_DIAGRAMS = 907


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def reset_disposable_directory(path: Path) -> None:
    resolved_root = ROOT.resolve()
    resolved = path.resolve()
    if resolved_root != resolved and resolved_root not in resolved.parents:
        raise RuntimeError(f"Refusing to reset path outside English lane: {resolved}")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=False)


def run(command):
    completed = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True)
    display_command = [Path(command[0]).name]
    for argument in command[1:]:
        value = str(argument)
        candidate = Path(value)
        if candidate.is_absolute():
            try:
                value = candidate.resolve().relative_to(ROOT.resolve()).as_posix()
            except ValueError:
                value = candidate.name
        display_command.append(value)
    row = {"command": display_command, "returncode": completed.returncode,
           "stdout_tail": completed.stdout[-5000:], "stderr_tail": completed.stderr[-5000:]}
    if completed.returncode: raise RuntimeError(json.dumps(row, ensure_ascii=False))
    return row


def main():
    admission = json.loads((ROOT / "qa" / "UNIT_ADMISSION.json").read_text(encoding="utf-8-sig"))
    backend = json.loads((ROOT / "backend" / "BACKEND_VALIDATION.json").read_text(encoding="utf-8-sig"))
    source_freeze = json.loads(SOURCE_FREEZE.read_text(encoding="utf-8-sig"))
    if (admission.get("result") != "PASS" or backend.get("result") != "PASS"
            or source_freeze.get("result") != "PASS"):
        raise SystemExit("HTML build requires admitted units and a valid backend")
    reset_disposable_directory(READER / "build")
    reset_disposable_directory(DIST)
    python = sys.executable
    commands = []
    commands.append(run([python, str(READER / "tools" / "build_pandoc_reader.py"),
                         "--project", str(ROOT), "--reader", str(READER)]))
    commands.append(run([python, str(READER / "tools" / "validate_reader.py"),
                         "--dist", str(DIST), "--master", str(MASTER), "--ledger", str(LEDGER)]))
    validation = json.loads((DIST / "validation-report.json").read_text(encoding="utf-8-sig"))
    reader_report_path = READER / "build" / "reader-build-report.json"
    reader_report = json.loads(reader_report_path.read_text(encoding="utf-8-sig"))
    required_validation = {
        "status": "pass",
        "units_and_bridges": EXPECTED_UNITS_AND_BRIDGES,
        "logical_sections": EXPECTED_LOGICAL_SECTIONS,
        "ledger_diagrams": EXPECTED_DIAGRAMS,
        "diagram_alt_texts_applied": EXPECTED_DIAGRAMS,
    }
    validation_ok = all(validation.get(key) == value for key, value in required_validation.items())
    validation_ok = validation_ok and not validation.get("errors")
    validation_ok = validation_ok and not validation.get("unsupported_math_residue")
    validation_ok = validation_ok and not validation.get("unsupported_raw_residue")
    validation_ok = validation_ok and not validation.get("raw_hypertarget_residue")
    validation_ok = validation_ok and not validation.get("misplaced_anchor_fallbacks")
    validation_ok = validation_ok and validation.get("configured_mathjax_macros") is not None
    index = DIST / "index.html"
    receipt = {"schema": "o014-english-html-build-v1", "built_at_utc": datetime.now(timezone.utc).isoformat(),
               "result": "PASS" if validation_ok else "FAIL",
               "index_bytes": index.stat().st_size, "index_sha256": sha(index),
               "dist_files": sum(1 for p in DIST.rglob("*") if p.is_file()),
               "dist_bytes": sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file()),
               "validation": validation, "commands": commands,
               "reader_build_report_sha256": sha(reader_report_path),
               "source_inputs": reader_report.get("source_inputs"),
               "reader_inputs": reader_report.get("reader_inputs"),
               "builder_inputs": {
                   "tools/build_english_reader.py": sha(ROOT / "tools" / "build_english_reader.py"),
                   "reader/tools/build_pandoc_reader.py": sha(READER / "tools" / "build_pandoc_reader.py"),
                   "reader/tools/validate_reader.py": sha(READER / "tools" / "validate_reader.py"),
               },
               "source_freeze_sha256": sha(SOURCE_FREEZE),
               "source_commit": source_freeze.get("commit"),
               "source_tree": source_freeze.get("tree")}
    RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"result": receipt["result"], "index_bytes": receipt["index_bytes"],
                      "index_sha256": receipt["index_sha256"], "dist_files": receipt["dist_files"],
                      "dist_bytes": receipt["dist_bytes"]}))
    if receipt["result"] != "PASS": raise SystemExit(1)


if __name__ == "__main__": main()
