"""Fixed-pass XeLaTeX/Biber/MakeIndex build for the admitted English corpus."""

from datetime import datetime, timezone
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


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


def run(command, env):
    completed = subprocess.run(command, cwd=SOURCE, env=env, text=True,
                               encoding="utf-8", errors="replace", capture_output=True)
    record = {"command": [Path(command[0]).name, *command[1:]], "returncode": completed.returncode,
              "stdout_tail": completed.stdout[-4000:], "stderr_tail": completed.stderr[-4000:]}
    if completed.returncode:
        raise RuntimeError(json.dumps(record, ensure_ascii=False))
    return record


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
    makeindex = shutil.which("makeindex")
    if not all([xelatex, biber, makeindex]):
        raise SystemExit({"xelatex": xelatex, "biber": biber, "makeindex": makeindex})
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
        index_records = []
        for idx in sorted(BUILD.glob(f"{STEM}*.idx")):
            ind = idx.with_suffix(".ind")
            index_records.append(run([makeindex, "-o", str(ind), str(idx)], env))
        commands.extend(index_records)
        commands.append(run(base, env))
        commands.append(run(base, env))
        built = BUILD / f"{STEM}.pdf"
        if not built.is_file(): raise SystemExit("XeLaTeX returned success without a PDF")
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
