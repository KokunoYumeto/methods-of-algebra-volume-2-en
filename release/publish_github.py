"""Publish the verified English corpus and Pages reader to one public repo.

All Git commands are scoped to this small English lane. No workspace-root scan
or watcher is used. The gh-pages update uses an exact force-with-lease.
"""

import argparse
from datetime import datetime, timezone
import hashlib, json
from pathlib import Path
import subprocess


ROOT=Path(__file__).resolve().parents[1]
OWNER="KokunoYumeto";REPO="methods-of-algebra-volume-2-en";SLUG=f"{OWNER}/{REPO}"
RECEIPT=ROOT/"release"/"GITHUB_PUBLICATION_RECEIPT.json"
PUBLISH_PATHS=(".gitignore","README.md","backend","controls",
               "output/pdf/methods-of-algebra-volume-2-independent-english-edition.pdf",
               "qa","reader","release","source/en","tools")
CHECKPOINT_PATHS=(".gitignore","README.md","backend","controls","qa","reader",
                  "release","source/en","tools")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args,check=True):
    p=subprocess.run(args,cwd=ROOT,text=True,encoding="utf-8",errors="replace",capture_output=True)
    if check and p.returncode:raise RuntimeError(f"{args[0]} {args[1] if len(args)>1 else ''}: {p.stderr[-1000:]}")
    return p
def git(*args):return run(["git","-C",str(ROOT),*args]).stdout.strip()
def validate_publication_boundary(gates):
    package=gates["PACKAGE_RECEIPT.json"];zenodo=gates["ZENODO_PUBLICATION_RECEIPT.json"]
    if zenodo.get("package_receipt_sha256")!=sha(ROOT/"release"/"staging"/"PACKAGE_RECEIPT.json"):
        raise RuntimeError("Zenodo receipt does not bind the current package receipt")
    expected={row["filename"]:(int(row["bytes"]),row["sha256"]) for row in package.get("files",[])}
    public={row["filename"]:(int(row["bytes"]),row["sha256"]) for row in zenodo.get("public_files",[]) if row.get("pass") is True}
    if len(expected)!=9 or public!=expected:raise RuntimeError("Zenodo public-byte receipt does not match the nine-file package")
    md=zenodo.get("metadata",{})
    if md.get("access_right")!="open" or md.get("license")!="cc-by-4.0" or md.get("defects"):
        raise RuntimeError("Zenodo public metadata is not an open, defect-free CC BY 4.0 boundary")
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--reader-checkpoint",action="store_true",
                        help="Publish the complete verified HTML reader while PDF/Zenodo remain pending")
    args=parser.parse_args()
    if args.reader_checkpoint:
        gate_paths=[ROOT/"qa"/"HTML_BUILD_RECEIPT.json",ROOT/"qa"/"HTML_BROWSER_QA.json",
                    ROOT/"backend"/"BACKEND_VALIDATION.json"]
        gates={p.name:json.loads(p.read_text(encoding="utf-8-sig")) for p in gate_paths}
        if not all(row.get("result")=="PASS" for row in gates.values()):
            raise SystemExit("HTML build, browser, and backend gates must PASS before reader checkpoint publication")
        publish_paths=CHECKPOINT_PATHS
        commit_message="Publish complete English HTML reader checkpoint"
        publication_scope="complete_html_reader_checkpoint_pdf_and_zenodo_pending"
    else:
        gate_paths=[ROOT/"qa"/"PDF_BUILD_RECEIPT.json",ROOT/"qa"/"HTML_BUILD_RECEIPT.json",
                    ROOT/"backend"/"BACKEND_VALIDATION.json",ROOT/"release"/"staging"/"PACKAGE_RECEIPT.json",
                    ROOT/"release"/"ZENODO_PUBLICATION_RECEIPT.json"]
        gates={p.name:json.loads(p.read_text(encoding="utf-8-sig")) for p in gate_paths}
        if not all(row.get("result")=="PASS" for row in gates.values()):
            raise SystemExit("All build/package/Zenodo gates must PASS before final GitHub publication")
        validate_publication_boundary(gates)
        publish_paths=PUBLISH_PATHS
        commit_message="Publish complete independent English edition"
        publication_scope="complete_pdf_html_source_backend_release"
        readme=ROOT/"README.md"
        status=("Public release status: complete HTML reader, editable source, and modular\n"
                "backend checkpoint; the PDF and Zenodo archive are pending the serialized TeX\n"
                "build.")
        replacement=("Public release status: complete PDF and HTML readers, editable source,\n"
                     "modular backend, and published Zenodo archive.")
        text=readme.read_text(encoding="utf-8")
        if text.count(status)!=1:
            raise RuntimeError("README checkpoint-status marker is missing or ambiguous")
        readme.write_text(text.replace(status,replacement),encoding="utf-8")
    if not (ROOT/".git").exists():
        run(["git","init","-b","main",str(ROOT)])
        git("config","user.name","OpenAI Codex")
        git("config","user.email","codex@openai.com")
    view=run(["gh","repo","view",SLUG,"--json","nameWithOwner,visibility"],check=False)
    exists=view.returncode==0
    if not exists:
        run(["gh","repo","create",SLUG,"--public","--source",str(ROOT),"--remote","origin",
             "--description","Independent English edition of Wen-Wei Li's Methods of Algebra, Volume 2 (CC BY 4.0)"])
    else:
        repo=json.loads(view.stdout)
        if repo.get("nameWithOwner")!=SLUG:raise RuntimeError("GitHub repository identity mismatch")
        if repo.get("visibility")!="PUBLIC":
            run(["gh","repo","edit",SLUG,"--visibility","public","--accept-visibility-change-consequences"])
    remotes=git("remote").splitlines()
    if "origin" not in remotes:
        git("remote","add","origin",f"https://github.com/{SLUG}.git")
    else:
        origin=git("remote","get-url","origin").removesuffix("/")
        allowed={f"https://github.com/{SLUG}.git",f"git@github.com:{SLUG}.git"}
        if origin not in allowed:raise RuntimeError(f"Refusing unexpected origin: {origin}")
    git("add","--all","--",*publish_paths)
    if git("status","--porcelain=v1","--",*publish_paths):
        git("commit","--only","-m",commit_message,"--",*publish_paths)
    git("branch","-M","main")
    git("push","-u","origin","main")
    content_commit=git("rev-parse","HEAD");content_tree=git("rev-parse","HEAD^{tree}")
    pages_commit=git("subtree","split","--prefix=reader/dist","HEAD")
    old=git("ls-remote","origin","refs/heads/gh-pages")
    old_sha=old.split()[0] if old else ""
    lease=f"--force-with-lease=refs/heads/gh-pages:{old_sha}"
    git("push",lease,"origin",f"{pages_commit}:refs/heads/gh-pages")
    get=run(["gh","api",f"repos/{SLUG}/pages"],check=False)
    method="PUT" if get.returncode==0 else "POST"
    configured=run(["gh","api","--method",method,f"repos/{SLUG}/pages","-f","build_type=legacy",
                    "-f","source[branch]=gh-pages","-f","source[path]=/"],check=False)
    if configured.returncode:
        current=run(["gh","api",f"repos/{SLUG}/pages"])
        page=json.loads(current.stdout);source=page.get("source",{})
        if not (page.get("public") is True and page.get("build_type")=="legacy" and
                source.get("branch")=="gh-pages" and source.get("path")=="/"):
            raise RuntimeError(f"GitHub Pages configuration failed: {configured.stderr[-1000:]}")
    receipt={"schema":"o014-english-github-publication-v1","published_at_utc":datetime.now(timezone.utc).isoformat(),
      "result":"PUSHED_PENDING_ANONYMOUS_READBACK","repository":f"https://github.com/{SLUG}",
      "pages_url":f"https://{OWNER.lower()}.github.io/{REPO}/","visibility":"public",
      "publication_scope":publication_scope,
      "main_content_commit":content_commit,"main_content_tree":content_tree,"pages_commit":pages_commit,
      "pages_previous_commit":old_sha or None,"source_commit":"9a5803ff77dd3257484cb177f851a73770a59dd3",
      "source_tree":"23bd05c2fb8434278df4fdfb636559a6a2b0d2ff","credentials_recorded":False}
    RECEIPT.write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    receipt_path=str(RECEIPT.relative_to(ROOT)).replace("\\","/")
    git("add","--",receipt_path)
    git("commit","--only","-m","Record publication boundary","--",receipt_path)
    git("push","origin","main")
    print(json.dumps({"result":receipt["result"],"content_commit":content_commit,"pages_commit":pages_commit,
                      "main_head":git("rev-parse","HEAD"),"receipt_sha256":sha(RECEIPT)}))
if __name__=="__main__":main()
