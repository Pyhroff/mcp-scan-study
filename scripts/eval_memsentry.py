"""Compare memsentry 1.0 (original repo) vs 1.1 (patched copy): recall on the repo's own malicious samples,
and findings on the 170 public agent-context files."""
import json, subprocess, sys, pathlib, collections
ROOT = pathlib.Path(__file__).resolve().parent.parent; WORK = pathlib.Path.home() / "mcp-study-work"
DESK = ROOT.parent
CODE = r'''
import sys, json, subprocess, pathlib
sys.path.insert(0, sys.argv[1])
from memsentry.scanner import scan_file
from memsentry.memfile import MemoryFile
files = json.loads(sys.argv[2]); out = {}
for f in files:
    try: out[f] = [[x.check, x.severity.value, x.title, x.line] for x in scan_file(MemoryFile.load(f))]
    except Exception as e: out[f] = []
print(json.dumps(out))
'''
ctx = []
for d in sorted((WORK / "corpus").iterdir()):
    r = subprocess.run(["find", str(d), "-path", "*/node_modules", "-prune", "-o", "-path", "*/.git", "-prune", "-o", "-type", "f", "(", "-name", "CLAUDE.md", "-o", "-name", "AGENTS.md", "-o", "-name", "GEMINI.md", "-o", "-name", ".cursorrules", "-o", "-name", ".windsurfrules", "-o", "-name", ".clinerules", "-o", "-name", "copilot-instructions.md", "-o", "-path", "*/.cursor/rules/*", ")", "-print"], capture_output=True, text=True).stdout.split("\n")
    ctx += [x for x in r if x]
samples = [str(DESK / "memsentry" / "samples" / n) for n in ("clean_memory.md", "poisoned_memory.md", "subtle_memory.md")]
res = {}
for ver, path in (("v1.0", DESK / "memsentry"), ("v1.1", ROOT / "patches" / "memsentry-1.1")):
    res[ver] = json.loads(subprocess.run([sys.executable, "-c", CODE, str(path), json.dumps(samples + ctx)], capture_output=True, text=True).stdout)
def cnt(v, files): return collections.Counter(t[2] for f in files for t in res[v][f])
summ = dict(context_files=len(ctx),
    samples={n.split("/")[-1]: dict(v10=len(res["v1.0"][n]), v11=len(res["v1.1"][n])) for n in samples},
    samples_identical=all(res["v1.0"][n] == res["v1.1"][n] for n in samples),
    ctx_findings_v10=sum(len(res["v1.0"][f]) for f in ctx), ctx_findings_v11=sum(len(res["v1.1"][f]) for f in ctx),
    ctx_by_title_v10=cnt("v1.0", ctx), ctx_by_title_v11=cnt("v1.1", ctx))
remaining = [(f.split("corpus/")[-1], t) for f in ctx for t in res["v1.1"][f]]
(ROOT / "data" / "eval_memsentry.json").write_text(json.dumps(dict(summary=summ, remaining_v11=remaining), indent=1))
print(json.dumps(summ, indent=1)); print("REMAINING:")
for r in remaining: print(r)
