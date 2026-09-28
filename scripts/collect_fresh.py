"""Fresh validation corpus: MCP-server repos ranked 31-45 by stars per language, excluding the original 90."""
import json, subprocess, sys, time, urllib.request, urllib.parse, pathlib, concurrent.futures as cf
ROOT = pathlib.Path(__file__).resolve().parent.parent
WORK = pathlib.Path.home() / "mcp-study-work"
SEL = ROOT / "data" / "fresh_selection.json"
old = set(json.loads((ROOT / "data" / "corpus.json").read_text()))
def api(url):
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "mcp-scan-study"}), timeout=30) as r: return json.load(r)
        except Exception: time.sleep(8 * (i + 1))
    raise RuntimeError(url)
if SEL.exists(): repos = json.loads(SEL.read_text())
else:
    repos = {}
    for lang in ["python", "typescript", "javascript"]:
        rank = 0; taken = 0
        for page in (1, 2, 3):
            q = urllib.parse.quote(f"topic:mcp-server language:{lang} archived:false fork:false")
            for it in api(f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page=50&page={page}")["items"]:
                if it["full_name"] in old: continue
                rank += 1
                if rank > 30 and taken < 15:
                    repos[it["full_name"]] = dict(lang=lang, stars=it["stargazers_count"], url=it["clone_url"]); taken += 1
            time.sleep(7)
    SEL.write_text(json.dumps(repos, indent=1))
T0 = time.time()
def clone(item):
    name, meta = item; dest = WORK / "corpus2" / name.replace("/", "__")
    if time.time() - T0 > 140: return name, "SKIP"
    if not (dest / ".git").exists():
        r = subprocess.run(["git", "clone", "--depth", "1", "--single-branch", "--filter=blob:limit=300k", "-q", meta["url"], str(dest)], capture_output=True, text=True, timeout=300)
        if r.returncode: return name, None
    return name, subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
with cf.ThreadPoolExecutor(14) as ex:
    for name, sha in ex.map(clone, repos.items()):
        if sha != "SKIP": repos[name]["sha"] = sha
print("cloned", sum(1 for v in repos.values() if v.get("sha")), "of", len(repos))
if all(v.get("sha") for v in repos.values()): (ROOT / "data" / "fresh_corpus.json").write_text(json.dumps(repos, indent=1)); print("DONE")
