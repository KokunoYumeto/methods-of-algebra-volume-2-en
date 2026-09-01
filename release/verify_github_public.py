"""Anonymously verify the public repository and every GitHub Pages byte."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import requests
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1];DIST=ROOT/"reader"/"dist"
PUBLISH=ROOT/"release"/"GITHUB_PUBLICATION_RECEIPT.json";OUT=ROOT/"release"/"GITHUB_PUBLIC_READBACK.json"
API="https://api.github.com/repos/KokunoYumeto/methods-of-algebra-volume-2-en"
BASE="https://kokunoyumeto.github.io/methods-of-algebra-volume-2-en/"
def sha(data):return hashlib.sha256(data).hexdigest()
def get(url):
    s=requests.Session();s.trust_env=False;s.headers["User-Agent"]="O014-English-public-verifier/1.0"
    r=s.get(url,timeout=(20,90));r.raise_for_status();return r
def one(path):
    rel=path.relative_to(DIST).as_posix();expected=path.read_bytes();r=get(BASE+quote(rel,safe="/"))
    row={"path":rel,"url":r.url,"http_status":r.status_code,"expected_bytes":len(expected),"bytes":len(r.content),
         "expected_sha256":sha(expected),"sha256":sha(r.content)}
    row["pass"]=row["bytes"]==row["expected_bytes"] and row["sha256"]==row["expected_sha256"];return row
def main():
    publication=json.loads(PUBLISH.read_text(encoding="utf-8-sig"));files=sorted(p for p in DIST.rglob("*") if p.is_file())
    repo=get(API).json();pages=get(f"{API}/pages").json();pages_commit=get(f"{API}/commits/gh-pages").json()["sha"]
    rows=[];errors=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(one,p):p for p in files}
        for f in as_completed(futures):
            try:rows.append(f.result())
            except Exception as e:errors.append({"path":futures[f].relative_to(DIST).as_posix(),"type":type(e).__name__,"message":str(e)})
    rows.sort(key=lambda x:x["path"])
    source=pages.get("source",{})
    checks={"publication_boundary":publication.get("result")=="PUSHED_PENDING_ANONYMOUS_READBACK",
            "repository_public":repo.get("private") is False,"repository_name":repo.get("full_name")=="KokunoYumeto/methods-of-algebra-volume-2-en",
            "main_default_branch":repo.get("default_branch")=="main","pages_url":pages.get("html_url")==BASE,
            "pages_source_root":source.get("branch")=="gh-pages" and source.get("path")=="/",
            "pages_commit_exact":pages_commit==publication["pages_commit"],"all_files_read":len(rows)==len(files),
            "all_bytes_exact":all(row["pass"] for row in rows),"root_present":any(row["path"]=="index.html" for row in rows)}
    result="PASS" if not errors and all(checks.values()) else "FAIL"
    out={"schema":"o014-english-github-public-readback-v1","verified_at_utc":datetime.now(timezone.utc).isoformat(),"result":result,
      "repository":f"https://github.com/{repo.get('full_name')}","pages_url":BASE,"main_default_branch":repo.get("default_branch"),
      "pages_commit":pages_commit,"checks":checks,"files":rows,"file_count":len(rows),"total_bytes":sum(r["bytes"] for r in rows),
      "errors":errors,"credentials_used":False}
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"result":result,"files":len(rows),"bytes":out["total_bytes"],"errors":errors,"receipt_sha256":sha(OUT.read_bytes())}))
    if result!="PASS":raise SystemExit(1)
if __name__=="__main__":main()
