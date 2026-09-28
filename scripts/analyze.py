"""Combine scanner output with hand-assigned review labels; compute precision with Wilson 95% CIs."""
import json, math, re, collections, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
D = lambda n: json.loads((ROOT / "data" / n).read_text())
def wilson(k, n, z=1.96):
    if n == 0: return (0, 0)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round((c - h) / d * 100, 1), round((c + h) / d * 100, 1)
NOISE = re.compile(r"(^|/)(tests?|__tests__|e2e|bench|benchmarks?|fixtures?|eslint[_-]?rules?|lint|scripts|examples?|mocks?|stories|plugin-community-nodes)(/|$)|\.(spec|test)\.", re.I)
manifests = D("manifests.json")
tools = [(r, t) for r, v in manifests.items() for t in v["tools"]]
noise = [1 for r, t in tools if NOISE.search(t["src"].split("corpus/")[-1])]
labels = D("labels.json")
out = dict(tools_extracted=len(tools), tools_from_nonproduction_paths=len(noise), pct_nonproduction=round(100 * len(noise) / len(tools), 1))
for name, lab in labels.items():
    c = collections.Counter(lab.values()); n = len(lab)
    acc = c.get("accurate", 0); weak = c.get("weak", 0)
    out[name] = dict(n=n, counts=dict(c), strict_precision_pct=round(100 * acc / n, 1), strict_ci95=wilson(acc, n),
                     lenient_precision_pct=round(100 * (acc + weak) / n, 1), lenient_ci95=wilson(acc + weak, n))
(ROOT / "data" / "analysis.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))
