"""The study's published numbers must be reproducible from the checked-in data.

Each analysis script is run on a temporary copy of the repository (the scripts overwrite their
output files) and its output compared to the committed result, so a stale or hand-edited data file,
or a script change that silently shifts a headline number, fails CI.
"""
import ast
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def _load_wilson():
    source = (ROOT / "scripts" / "analyze.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "wilson")
    namespace = {"math": math}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "analyze.py", "exec"), namespace)
    return namespace["wilson"]


wilson = _load_wilson()


def _run_on_copy(tmp_path: Path, script: str, output: str) -> dict:
    shutil.copytree(ROOT / "scripts", tmp_path / "scripts")
    shutil.copytree(DATA, tmp_path / "data")
    subprocess.run(
        [sys.executable, str(tmp_path / "scripts" / script)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        timeout=300,
    )
    return json.loads((tmp_path / "data" / output).read_text(encoding="utf-8"))


# --- Wilson interval ---------------------------------------------------------


@pytest.mark.parametrize(
    ("k", "n", "expected"),
    [
        (15, 40, (24.2, 53.0)),  # strict precision, permission_scope sample
        (27, 40, (52.0, 79.9)),  # lenient precision
        (0, 20, (0.0, 16.1)),  # poisoning class: lower bound must clamp to 0, not -0.0
        (20, 20, (83.9, 100.0)),
    ],
)
def test_wilson_interval(k, n, expected):
    assert wilson(k, n) == expected


def test_wilson_bounds_never_leave_0_100():
    for n in range(1, 60):
        for k in range(n + 1):
            lo, hi = wilson(k, n)
            assert 0.0 <= lo <= hi <= 100.0, (k, n)
            assert math.copysign(1, lo) == 1, f"negative zero for k={k}, n={n}"


def test_wilson_empty_sample():
    assert wilson(0, 0) == (0, 0)


# --- reproducibility ---------------------------------------------------------


def test_analysis_json_reproduces_from_data(tmp_path):
    committed = json.loads((DATA / "analysis.json").read_text(encoding="utf-8"))
    assert _run_on_copy(tmp_path, "analyze.py", "analysis.json") == committed


def test_every_label_set_is_analysed():
    labels = json.loads((DATA / "labels.json").read_text(encoding="utf-8"))
    analysis = json.loads((DATA / "analysis.json").read_text(encoding="utf-8"))
    assert set(labels) <= set(analysis)


def test_eval_v07_reproduces_with_mcpaudit_0_7(tmp_path):
    # eval_v07.py imports the patched scanner; pyhroff-mcpaudit==0.7.0 on PyPI is that patch released.
    mcpaudit = pytest.importorskip("mcpaudit")
    from importlib.metadata import version

    if version("pyhroff-mcpaudit") != "0.7.0":
        pytest.skip("needs pyhroff-mcpaudit==0.7.0")
    committed = json.loads((DATA / "eval_v07.json").read_text(encoding="utf-8"))
    assert _run_on_copy(tmp_path, "eval_v07.py", "eval_v07.json") == committed


# --- prose matches data ------------------------------------------------------


def _ci(pair) -> str:
    return f"{round(pair[0])}-{round(pair[1])}%"


def test_report_headline_numbers_match_analysis():
    analysis = json.loads((DATA / "analysis.json").read_text(encoding="utf-8"))
    report = (ROOT / "REPORT.md").read_text(encoding="utf-8")
    sample = analysis["permission_scope_high_sample40"]
    poisoning = analysis["poisoning_class_all20"]

    assert f"{sample['counts']['accurate']} / {sample['n']} = {sample['strict_precision_pct']}% (95% CI {_ci(sample['strict_ci95'])})" in report
    lenient_k = sample["counts"]["accurate"] + sample["counts"]["weak"]
    assert f"{lenient_k} / {sample['n']} = {sample['lenient_precision_pct']}% (95% CI {_ci(sample['lenient_ci95'])})" in report
    assert f"0 / {poisoning['n']} (95% CI {_ci(poisoning['strict_ci95'])})" in report
    assert f"({analysis['pct_nonproduction']}% of tools come from tests/fixtures/lint rules)" in report


def test_readme_summary_matches_analysis():
    analysis = json.loads((DATA / "analysis.json").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    sample = analysis["permission_scope_high_sample40"]

    assert f"{analysis['tools_extracted']:,} tools" in readme
    assert f"{sample['strict_precision_pct']}% strict precision (95% CI {_ci(sample['strict_ci95'])[:-1]}%)" in readme


def test_report_v07_numbers_match_eval():
    ev = json.loads((DATA / "eval_v07.json").read_text(encoding="utf-8"))["permission_scope_high_heldout40"]
    report = (ROOT / "REPORT.md").read_text(encoding="utf-8")
    ci = ev["strict_ci95_after"]

    assert f"{ev['strict_precision_after_pct']}% (95% CI {_ci(ci)}, n={ev['n_after']})" in report
    assert re.search(rf"\| Findings still raised \| 40 \| {ev['n_after']} \|", report)
    assert f"{ev['accurate_retained_pct']:g}% ({ev['after']['accurate']} of {ev['before']['accurate']})" in report
