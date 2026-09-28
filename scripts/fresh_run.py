"""Run mcpaudit v0.6 (original repo) and v0.7 (patched copy) on the fresh corpus; draw a fresh seeded sample."""
import json, sys, subprocess, random, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parent.parent
CODE = r'''
import sys, json
sys.path.insert(0, sys.argv[1])
from mcpaudit.manifest import ServerManifest, ToolManifest
from mcpaudit.checks.permission_scope import check_scope
man = json.load(open(sys.argv[2])); out = []
NOISE = __import__("re").compile(r"(^|/)(tests?|__tests__|e2e|bench|benchmarks?|fixtures?|eslint[_-]?rules?|lint|scripts|examples?|mocks?|stories)(/|$)|\.(spec|test)\.", 2)
for repo, v in man.items():
    tools = [t for t in v["tools"] if not NOISE.search(t["src"].split("corpus2/")[-1])]
    for i in range(0, len(tools), 50):
        part = tools[i:i + 50]
        for f in check_scope(ServerManifest(repo, tools=[ToolManifest(t["name"], t["description"], t["input_schema"]) for t in part])):
            if f.severity.value == "high": out.append([repo, f.tool, f.title, f.detail])
print(json.dumps(out))
'''
man = str(ROOT / "data" / "manifests_fresh.json")
res = {}
for ver, path in (("v06", ROOT.parent / "mcpaudit"), ("v07", ROOT / "patches" / "mcpaudit-0.7")):
    res[ver] = json.loads(subprocess.run([sys.executable, "-c", CODE, str(path), man], capture_output=True, text=True).stdout)
m = json.loads(pathlib.Path(man).read_text())
def key(x): return (x[0], x[1], x[2])
v07 = {key(x) for x in res["v07"]}
v06 = sorted(res["v06"], key=key)
random.Random(11).shuffle(v06); S = v06[:40]
sample = []
for x in S:
    t = next(t for t in m[x[0]]["tools"] if t["name"] == x[1])
    params = re.findall(r"parameter\(s\) (\[.*?\])", x[3])
    sample.append(dict(repo=x[0], tool=x[1], title=x[2], params=params[0] if params else "", desc=t["description"][:150], src=t["src"].split("corpus2/")[-1][-45:], kept_v07=key(x) in v07))
(ROOT / "data" / "fresh_sample.json").write_text(json.dumps(sample, indent=1))
print("v06 high:", len(res["v06"]), "v07 high:", len(res["v07"]), "repos:", len(m))
for i, s in enumerate(sample):   # kept_v07 is deliberately NOT printed: label blind
    print(f"{i}. [{s['repo'].split('/')[1]}] {s['tool']} | {s['title'].replace('Unscoped ','')} | {s['params']} | ..{s['src']}\n    {s['desc']!r}")
