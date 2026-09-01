"""Fixed-pass XeLaTeX/Biber/Xindy build for the admitted English corpus."""

from datetime import datetime, timezone
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "en"
MASTER = SOURCE / "Al-jabr-2-en-complete-draft.tex"
STEM = MASTER.stem
BUILD = ROOT / "output" / "pdf" / "build"
FINAL = ROOT / "output" / "pdf" / "methods-of-algebra-volume-2-independent-english-edition.pdf"
RECEIPT = ROOT / "qa" / "PDF_BUILD_RECEIPT.json"
MUTEX_NAME = r"Global\InterlanguageTeXSlotV1"
MUTEX_TIMEOUT_MS = 600_000
WAIT_OBJECT_0 = 0x00000000
WAIT_ABANDONED = 0x00000080
WAIT_TIMEOUT = 0x00000102
EXPECTED_INDEX_COUNTS = {STEM: 512, "sym1": 242}
INDEX_LINE = re.compile(r"^\\indexentry\[([^]]+)\](.*)$")


class TeXMutex:
    """Hold the required machine-wide TeX slot across the entire build."""
    def __init__(self):
        self.handle = None
        self.abandoned = False

    def __enter__(self):
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel32.WaitForSingleObject.restype = ctypes.c_uint32
        self.handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), "CreateMutexW failed")
        result = kernel32.WaitForSingleObject(self.handle, MUTEX_TIMEOUT_MS)
        if result == WAIT_ABANDONED:
            self.abandoned = True
        elif result == WAIT_TIMEOUT:
            kernel32.CloseHandle(self.handle)
            self.handle = None
            raise TimeoutError(f"Did not acquire {MUTEX_NAME} within {MUTEX_TIMEOUT_MS} ms")
        elif result != WAIT_OBJECT_0:
            error = ctypes.get_last_error()
            kernel32.CloseHandle(self.handle)
            self.handle = None
            raise OSError(error, f"WaitForSingleObject returned {result:#x}")
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.handle:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            try:
                if not kernel32.ReleaseMutex(self.handle):
                    raise OSError(ctypes.get_last_error(), "ReleaseMutex failed")
            finally:
                kernel32.CloseHandle(self.handle)
                self.handle = None


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def reset_build_directory(path: Path) -> None:
    resolved_root = ROOT.resolve()
    resolved = path.resolve()
    if resolved_root != resolved and resolved_root not in resolved.parents:
        raise RuntimeError(f"Refusing to reset path outside English lane: {resolved}")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=False)


def run(command, env, cwd=SOURCE):
    completed = subprocess.run(command, cwd=cwd, env=env, text=True,
                               encoding="utf-8", errors="replace", capture_output=True)
    try:
        recorded_cwd = str(Path(cwd).relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        recorded_cwd = str(Path(cwd).resolve())
    record = {"command": [Path(command[0]).name, *command[1:]], "returncode": completed.returncode,
              "cwd": recorded_cwd,
              "stdout_tail": completed.stdout[-4000:], "stderr_tail": completed.stderr[-4000:]}
    if completed.returncode:
        raise RuntimeError(json.dumps(record, ensure_ascii=False))
    return record


def split_index(raw_index: Path) -> tuple[dict[str, Path], dict[str, int]]:
    """Split imakeidx's combined stream without invoking a shell or Perl shim."""
    groups = {name: [] for name in EXPECTED_INDEX_COUNTS}
    unmatched = []
    for line_number, line in enumerate(raw_index.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        match = INDEX_LINE.fullmatch(line)
        if not match or match.group(1) not in groups:
            unmatched.append({"line": line_number, "text": line[:200]})
            continue
        groups[match.group(1)].append(r"\indexentry" + match.group(2))
    counts = {name: len(lines) for name, lines in groups.items()}
    if unmatched or counts != EXPECTED_INDEX_COUNTS:
        raise RuntimeError(json.dumps({"index_split": "FAIL", "counts": counts,
                                       "expected": EXPECTED_INDEX_COUNTS,
                                       "unmatched": unmatched[:20]}, ensure_ascii=False))
    outputs = {}
    for name, lines in groups.items():
        output = BUILD / f"{STEM}-{name}.idx"
        output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        outputs[name] = output
    return outputs, counts


def require_index_outputs(index_paths: dict[str, Path]) -> list[dict]:
    records = []
    for name, idx in index_paths.items():
        ind = idx.with_suffix(".ind")
        ilg = idx.with_suffix(".ilg")
        if not ind.is_file() or ind.stat().st_size == 0:
            raise RuntimeError(f"Xindy did not create a nonempty index for {name}: {ind}")
        if not ilg.is_file() or ilg.stat().st_size == 0:
            raise RuntimeError(f"Xindy did not create a nonempty transcript for {name}: {ilg}")
        transcript = ilg.read_text(encoding="utf-8", errors="replace")
        generated_index = ind.read_text(encoding="utf-8", errors="replace")
        if "\\begin{theindex}" not in generated_index or "\\end{theindex}" not in generated_index:
            raise RuntimeError(f"Xindy output is not a complete theindex environment for {name}: {ind}")
        fatal_markers = ("ERROR:", "Cannot locate", "Cannot open")
        found = [marker for marker in fatal_markers if marker.lower() in transcript.lower()]
        if re.search(r"\b[1-9][0-9]*\s+(?:entries?\s+)?rejected\b", transcript, re.IGNORECASE):
            found.append("nonzero rejected entries")
        if found:
            raise RuntimeError(json.dumps({"index": name, "fatal_markers": found,
                                           "transcript_tail": transcript[-4000:]}, ensure_ascii=False))
        records.append({"name": name,
                        "source": str(idx.relative_to(ROOT)).replace("\\", "/"),
                        "source_bytes": idx.stat().st_size, "source_sha256": sha(idx),
                        "output": str(ind.relative_to(ROOT)).replace("\\", "/"),
                        "output_bytes": ind.stat().st_size, "output_sha256": sha(ind),
                        "transcript": str(ilg.relative_to(ROOT)).replace("\\", "/"),
                        "transcript_bytes": ilg.stat().st_size, "transcript_sha256": sha(ilg)})
    return records


def require_converged_log(log_path: Path) -> dict:
    log = log_path.read_text(encoding="utf-8", errors="replace")
    forbidden = {
        "missing_index": r"No file .*?\.ind\.",
        "undefined_references": r"undefined references",
        "labels_changed": r"Label\(s\) may have changed",
        "rerun_biber": r"Please .*?run Biber",
        "rerun_latex": r"Please rerun LaTeX",
        "empty_bibliography": r"Empty bibliography",
        "splitindex_warning": r"Remember to run .*?splitindex",
    }
    found = {name: re.findall(pattern, log, flags=re.IGNORECASE)
             for name, pattern in forbidden.items() if re.search(pattern, log, flags=re.IGNORECASE)}
    if found:
        raise RuntimeError(json.dumps({"convergence": "FAIL", "markers": found}, ensure_ascii=False))
    return {"result": "PASS", "log": str(log_path.relative_to(ROOT)).replace("\\", "/"),
            "log_bytes": log_path.stat().st_size, "log_sha256": sha(log_path),
            "forbidden_markers_found": 0}


def run_xindy(xindy, source_idx: Path, modules: list[str], env) -> dict:
    """Run MiKTeX Xindy from its only reliable Windows working directory.

    MiKTeX 25.4's Xindy/CLISP launcher fails with ERROR_DIRECTORY from the
    deeply nested lane path.  A unique set of files in the system Temp root
    avoids that launcher defect; only the named files are copied back/deleted.
    """
    temp_root = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Temp"
    if not temp_root.is_dir():
        raise RuntimeError(f"Xindy temporary root is unavailable: {temp_root}")
    nonce = uuid.uuid4().hex
    temporary_idx = temp_root / f"o014xi-{nonce}.idx"
    temporary_ind = temp_root / f"o014xi-{nonce}.ind"
    temporary_ilg = temp_root / f"o014xi-{nonce}.ilg"
    xindy_env = env.copy()
    for key in ("LC_ALL", "LC_CTYPE", "LANG"):
        xindy_env.pop(key, None)
    command = [xindy, "-o", temporary_ind.name, "-t", temporary_ilg.name]
    for module in modules:
        command.extend(["-M", module])
    command.extend(["-I", "xelatex", "-C", "utf8", temporary_idx.name])
    try:
        shutil.copy2(source_idx, temporary_idx)
        record = run(command, xindy_env, cwd=temp_root)
        if not temporary_ind.is_file() or not temporary_ilg.is_file():
            raise RuntimeError(f"Xindy returned success without outputs for {source_idx.name}")
        shutil.copy2(temporary_ind, source_idx.with_suffix(".ind"))
        shutil.copy2(temporary_ilg, source_idx.with_suffix(".ilg"))
        record["windows_launcher_workaround"] = {
            "reason": "MiKTeX Xindy ERROR_DIRECTORY from nested working directories",
            "temporary_cwd": str(temp_root), "unique_files_removed": True}
        return record
    finally:
        for temporary in (temporary_idx, temporary_ind, temporary_ilg):
            temporary.unlink(missing_ok=True)


def main():
    admission = json.loads((ROOT / "qa" / "UNIT_ADMISSION.json").read_text(encoding="utf-8-sig"))
    bridges = json.loads((ROOT / "controls" / "ranges" / "bridges.json").read_text(encoding="utf-8-sig"))
    if admission.get("result") != "PASS" or admission.get("admitted_units") != 146:
        raise SystemExit("PDF build requires all 146 admitted units")
    if "PASS" not in json.dumps(bridges).upper():
        raise SystemExit("PDF build requires the completed mastery-bridge receipt")
    reset_build_directory(BUILD)
    FINAL.parent.mkdir(parents=True, exist_ok=True)
    xelatex = shutil.which("xelatex")
    biber = shutil.which("biber")
    xindy = shutil.which("xindy")
    if not all([xelatex, biber, xindy]):
        raise SystemExit({"xelatex": xelatex, "biber": biber, "xindy": xindy})
    env = os.environ.copy()
    env["TEXINPUTS"] = str(SOURCE) + os.pathsep + env.get("TEXINPUTS", "")
    env["BIBINPUTS"] = str(SOURCE) + os.pathsep + env.get("BIBINPUTS", "")
    env["max_print_line"] = "1000"
    base = [xelatex, "-interaction=nonstopmode", "-halt-on-error", "-file-line-error",
            "-synctex=0", f"-output-directory={BUILD}", MASTER.name]
    acquired_at = None
    with TeXMutex() as mutex:
        acquired_at = datetime.now(timezone.utc).isoformat()
        commands = [run(base, env)]
        commands.append(run([biber, "--input-directory", str(BUILD), "--output-directory", str(BUILD), STEM], env))
        raw_index = BUILD / f"{STEM}.idx"
        if not raw_index.is_file():
            raise RuntimeError(f"XeLaTeX did not create the combined index: {raw_index}")
        index_paths, index_counts = split_index(raw_index)
        main_idx = index_paths[STEM]
        sym_idx = index_paths["sym1"]
        commands.append(run_xindy(xindy, main_idx, ["texindy"], env))
        commands.append(run_xindy(xindy, sym_idx,
                                  ["numeric-sort", "latex", "latex-loc-fmts", "makeindex"], env))
        index_records = require_index_outputs(index_paths)
        commands.append(run(base, env))
        commands.append(run(base, env))
        built = BUILD / f"{STEM}.pdf"
        if not built.is_file(): raise SystemExit("XeLaTeX returned success without a PDF")
        convergence = require_converged_log(BUILD / f"{STEM}.log")
        shutil.copy2(built, FINAL)
        abandoned_recovery = mutex.abandoned
    # pdfinfo is not a TeX process and runs only after the mutex-protected tree ended.
    pdfinfo = shutil.which("pdfinfo")
    info = run([pdfinfo, str(FINAL)], env) if pdfinfo else None
    receipt = {"schema": "o014-english-pdf-build-v1", "built_at_utc": datetime.now(timezone.utc).isoformat(),
               "result": "PASS", "master": str(MASTER.relative_to(ROOT)).replace("\\", "/"),
               "master_sha256": sha(MASTER), "pdf": str(FINAL.relative_to(ROOT)).replace("\\", "/"),
               "pdf_bytes": FINAL.stat().st_size, "pdf_sha256": sha(FINAL),
               "commands": commands, "pdfinfo": info, "index_jobs": len(index_records),
               "index_entries": {"combined": sum(index_counts.values()), "by_index": index_counts},
               "indexes": index_records, "convergence": convergence,
               "tex_mutex": {"name": MUTEX_NAME, "timeout_ms": MUTEX_TIMEOUT_MS,
                              "acquired_at_utc": acquired_at,
                              "abandoned_mutex_recovered": abandoned_recovery,
                              "released_after_process_tree": True},
               "source_commit": "9a5803ff77dd3257484cb177f851a73770a59dd3",
               "source_tree": "23bd05c2fb8434278df4fdfb636559a6a2b0d2ff"}
    RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"result": "PASS", "pdf": str(FINAL), "bytes": FINAL.stat().st_size,
                      "sha256": sha(FINAL), "index_jobs": len(index_records)}))


if __name__ == "__main__": main()
