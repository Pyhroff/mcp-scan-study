"""Run mcpaudit (static checks) on statically-extracted manifests and memsentry on agent context files.
Imports the scanners read-only from the local repos; nothing in those repos is modified."""
import pickle, json, sys, pathlib, collections, subprocess, time
ROOT = pathlib.Path(__file__).resolve().parent.parent
WORK = pathlib.Path.home() / "mcp-study-work"
DESK = ROOT.parent
sys.path[:0] = [str(DESK / "mcpaudit"), str(DESK / "memsentry")]
from mcpaudit.manifest import ServerManifest, ToolManifest
from mcpaudit.checks.description_scan import scan_descriptions
from mcpaudit.checks.permission_scope import check_scope
from memsentry.scanner import scan_file
from memsentry.memfile import MemoryFile

manifests = json.loads((ROOT / "data" / "manifests.json").read_text())
T0 = time.time(); ma, per_repo = [], {}
for repo, v in sorted(manifests.items(), key=lambda kv: len(kv[1]["tools"])):
    tools = [ToolManifest(name=t["name"], description=t["description"], input_schema=t["input_schema"]) for t in v["tools"]]
    if not tools: continue
    sm = ServerManifest(server_name=repo, tools=tools)
    cache = WORK / "cache" / (repo.replace("/", "__") + ".pkl")
    if cache.exists(): fs = pickle.loads(cache.read_bytes())
    else:
        if time.time() - T0 > 140: print("time-boxed; rerun to continue", flush=True); sys.exit(2)
        fs = []
        for i in range(0, len(tools), 50):  # chunked: large manifests scale super-linearly
            part = ServerManifest(server_name=repo, tools=tools[i:i + 50]); fs += scan_descriptions(part) + check_scope(part)
        cache.parent.mkdir(exist_ok=True); cache.write_bytes(pickle.dumps(fs))
    per_repo[repo] = dict(tools=len(tools), findings=len(fs))
    for f in fs:
        src = next((t["src"].split("corpus/")[-1] for t in v["tools"] if t["name"] == f.tool), "")
        ma.append(dict(repo=repo, tool=f.tool, check=f.check, severity=f.severity.value, title=f.title, detail=f.detail, src=src,
                       description=next((t["description"][:400] for t in v["tools"] if t["name"] == f.tool), "")))
(ROOT / "data" / "mcpaudit_findings.json").write_text(json.dumps(ma, indent=1))

print("mcpaudit phase", round(time.time()-T0,1), "s", flush=True)
CTX = ["CLAUDE.md", "AGENTS.md", "GEMINI.md", ".cursorrules", ".windsurfrules", ".clinerules", "copilot-instructions.md"]
ms, ctx_repos, nfiles = [], set(), 0
for repo in manifests:
    d = WORK / "corpus" / repo.replace("/", "__")
    out = subprocess.run(["find", str(d), "-path", "*/node_modules", "-prune", "-o", "-path", "*/.git", "-prune", "-o", "-type", "f",
        "(", "-name", "CLAUDE.md", "-o", "-name", "AGENTS.md", "-o", "-name", "GEMINI.md", "-o", "-name", ".cursorrules", "-o", "-name", ".windsurfrules",
        "-o", "-name", ".clinerules", "-o", "-name", "copilot-instructions.md", "-o", "-path", "*/.cursor/rules/*", ")", "-print"], capture_output=True, text=True).stdout.split("\n")
    cands = [pathlib.Path(x) for x in out if x]
    for p in cands:
        try: fs = scan_file(MemoryFile.load(str(p)))
        except Exception: continue
        nfiles += 1; ctx_repos.add(repo)
        for f in fs:
            ms.append(dict(repo=repo, file=str(p.relative_to(d)), check=f.check, severity=f.severity.value, title=f.title, detail=f.detail, line=f.line, snippet=f.snippet[:300]))
(ROOT / "data" / "memsentry_findings.json").write_text(json.dumps(ms, indent=1))

tools_total = sum(len(v["tools"]) for v in manifests.values())
summary = dict(repos_in_corpus=len(manifests), repos_with_extracted_tools=len(per_repo), tools_extracted=tools_total,
    mcpaudit_findings=len(ma), mcpaudit_by_severity=collections.Counter(x["severity"] for x in ma), mcpaudit_by_check=collections.Counter(x["check"] + ": " + x["title"] for x in ma),
    repos_with_mcpaudit_findings=len({x["repo"] for x in ma}), context_files_scanned=nfiles, repos_with_context_files=len(ctx_repos),
    memsentry_findings=len(ms), memsentry_by_check=collections.Counter(x["check"] + ": " + x["title"] for x in ms), memsentry_by_severity=collections.Counter(x["severity"] for x in ms))
(ROOT / "data" / "summary.json").write_text(json.dumps(summary, indent=1))
print(json.dumps(summary, indent=1))
