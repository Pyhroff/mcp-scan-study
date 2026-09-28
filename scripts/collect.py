"""Build the study corpus: top-starred public GitHub repos tagged mcp-server, per language.
Selection is deterministic (stars desc, non-fork, non-archived) and recorded with commit SHAs."""
import json, subprocess, sys, time, urllib.request, urllib.parse, pathlib, concurrent.futures as cf
PER_LANG = int(sys.argv[1]) if len(sys.argv) > 1 else 30
ROOT = pathlib.Path(__file__).resolve().parent.parent
WORK = pathlib.Path.home() / "mcp-study-work"  # clones live outside the synced folder (fs there breaks git checkout)
def api(url):
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "mcp-scan-study"}), timeout=30) as r:
                return json.load(r)
        except Exception as e:
            time.sleep(8 * (i + 1))
    raise RuntimeError(url)
import os
LIST=ROOT/"data"/"selection.json"
repos = json.loads(LIST.read_text()) if LIST.exists() else {}
for lang in ([] if repos else ["python","typescript","javascript"]):
    pass
for lang in ([] if repos else ["python", "typescript", "javascript"]):
    got = 0
    for page in (1, 2):
        q = urllib.parse.quote(f"topic:mcp-server language:{lang} archived:false fork:false")
        d = api(f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page=50&page={page}")
        for it in d["items"]:
            if it["full_name"] in repos or got >= PER_LANG: continue
            repos[it["full_name"]] = dict(lang=lang, stars=it["stargazers_count"], license=(it["license"] or {}).get("spdx_id"), url=it["clone_url"], pushed=it["pushed_at"])
            got += 1
        time.sleep(7)
if not LIST.exists(): LIST.write_text(json.dumps(repos, indent=1))
T0=time.time()
def clone(item):
    if time.time()-T0>140: return item[0], "SKIP"
    name, meta = item
    dest = WORK / "corpus" / name.replace("/", "__")
    if not (dest / ".git").exists():
        r = subprocess.run(["git", "clone", "--depth", "1", "--single-branch", "--filter=blob:limit=300k", "-q", meta["url"], str(dest)], capture_output=True, text=True, timeout=300)
        if r.returncode: return name, None
    sha = subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    return name, sha
with cf.ThreadPoolExecutor(14) as ex:
    for name, sha in ex.map(clone, repos.items()):
        if sha=="SKIP": continue
        repos[name]["sha"] = sha
        print(name, sha, flush=True)
(ROOT / "data" / "corpus.json").write_text(json.dumps(repos, indent=1))
print("DONE", len(repos))
