"""Held-out evaluation of the v0.7 mcpaudit patch. Dev sample = the 40 findings used to find the failure modes;
held-out sample = 40 further findings from the same seeded shuffle, labelled BEFORE the patch was written."""
import json, sys, pathlib, math
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "patches" / "mcpaudit-0.7"))
from mcpaudit.manifest import ServerManifest, ToolManifest
from mcpaudit.checks.permission_scope import check_scope
import mcpaudit; print("using", mcpaudit.__file__)
man = json.loads((ROOT / "data" / "manifests.json").read_text()); labels = json.loads((ROOT / "data" / "labels.json").read_text())
def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return [round((c - h) / d * 100, 1), round((c + h) / d * 100, 1)]
res = {}
for sname, lname in [("review_sample_permission_scope.json", "permission_scope_high_sample40"), ("heldout_sample_permission_scope.json", "permission_scope_high_heldout40")]:
    sample = json.loads((ROOT / "data" / sname).read_text()); lab = labels[lname]; kept = {"accurate": 0, "weak": 0, "false_positive": 0}; tot = {"accurate": 0, "weak": 0, "false_positive": 0}
    for i, x in enumerate(sample):
        t = next(t for t in man[x["repo"]]["tools"] if t["name"] == x["tool"])
        fs = check_scope(ServerManifest(x["repo"], tools=[ToolManifest(t["name"], t["description"], t["input_schema"])]))
        still = any(f.severity.value == "high" and f.title == x["title"] for f in fs)
        tot[lab[str(i)]] += 1; kept[lab[str(i)]] += still
    n_after = sum(kept.values()); acc = kept["accurate"]
    res[lname] = dict(before=tot, after=kept, fp_removed_pct=round(100 * (1 - kept["false_positive"] / tot["false_positive"]), 1),
        accurate_retained_pct=round(100 * kept["accurate"] / tot["accurate"], 1),
        strict_precision_before_pct=round(100 * tot["accurate"] / 40, 1), strict_precision_after_pct=round(100 * acc / n_after, 1) if n_after else None,
        strict_ci95_after=wilson(acc, n_after) if n_after else None, n_after=n_after)
# whole-corpus effect (chunked like the v0.6 run)
tot06 = json.loads((ROOT / "data" / "mcpaudit_findings.json").read_text()); n06 = sum(1 for x in tot06 if x["check"] == "permission_scope" and x["severity"] == "high")
n07 = 0
for repo, v in man.items():
    tools = [ToolManifest(t["name"], t["description"], t["input_schema"]) for t in v["tools"]]
    for i in range(0, len(tools), 50):
        n07 += sum(1 for f in check_scope(ServerManifest(repo, tools=tools[i:i + 50])) if f.severity.value == "high")
res["corpus_high_permission_scope"] = dict(v06=n06, v07=n07, reduction_pct=round(100 * (1 - n07 / n06), 1))
(ROOT / "data" / "eval_v07.json").write_text(json.dumps(res, indent=1)); print(json.dumps(res, indent=1))
