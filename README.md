# mcp-scan-study

An empirical evaluation of two static AI-security scanners, [mcpaudit](https://github.com/Pyhroff/mcpaudit) and [memsentry](https://github.com/Pyhroff/memsentry), on public MCP-server repositories, with hand-labelled precision measurements and the scanner patches that came out of them.

Full write-up: **[REPORT.md](REPORT.md)**. Scan date: 2026-09-28. Single reviewer.

## Summary

- **Corpus**: 90 top-starred public repos tagged `mcp-server` (30 each Python, TypeScript, JavaScript), pinned by commit SHA, plus a separate 45-repo fresh corpus used for validation.
- **Method**: tool definitions were extracted statically from source (nothing from the repos was executed), then scanned. 4,898 tools from 53 repos, and 170 agent-context files from 43 repos.
- **Findings**: no genuine tool poisoning or memory injection in any repo. No vulnerabilities to disclose.
- **Precision before**: 37.5% strict precision (95% CI 24-53%) for mcpaudit v0.6 HIGH `permission_scope` findings on a 40-finding sample. memsentry v1.1 raised 61 findings on the context files, none of the 20 reviewed being real injection.
- **After patches**: mcpaudit v0.7 raised strict precision to 64.3% on a held-out 40 (95% CI 39-84%), retaining 60% of the accurate findings. On a fresh corpus, blind-labelled, precision went from 40% to 72.7% with all 16 accurate findings retained. memsentry v1.2 cut findings on the 170 files from 61 to 5 while still detecting its own sample.
- **Limits**: one labeller, a clustered sample, top-starred repos only, static extraction covering 53 of 90 repos, no dynamic checks. Details and caveats are in the report.

## Layout

```
REPORT.md       full method, results, limitations
data/           corpus (with commit SHAs), extracted manifests, findings, labels, evaluation output
patches/        mcpaudit-0.7.patch and memsentry-1.1.patch (the scanner changes)
scripts/        collect, extract, scan, analyze, and evaluation scripts
```

## Reproducing

The scripts read the scanner repositories from sibling directories and clone the corpus repos into `~/mcp-study-work`. In order:

```bash
python scripts/collect.py 30          # select corpus (uses the GitHub API)
python scripts/extract_manifests.py   # static manifest extraction
python scripts/run_scans.py           # run mcpaudit and memsentry
python scripts/analyze.py             # join with labels, compute Wilson intervals
python scripts/eval_v07.py            # held-out evaluation of the mcpaudit patch
python scripts/eval_memsentry.py      # memsentry patch evaluation
python scripts/collect_fresh.py && python scripts/extract_manifests_fresh.py && python scripts/fresh_run.py
```

The paths assume `mcpaudit` and `memsentry` are checked out next to this directory. Labels are in `data/labels.json`.

## License

[MIT](LICENSE)
