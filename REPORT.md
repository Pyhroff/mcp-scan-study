# Scanning 90 public MCP-server repos with mcpaudit and memsentry

Date: 2026-09-28. Scanners: mcpaudit v0.6.0 (static checks only), memsentry v1.1.0. Single reviewer.

## What was done
- Corpus: 90 top-starred public GitHub repos tagged `mcp-server` (30 each Python / TypeScript / JavaScript; non-fork, non-archived), pinned by commit SHA in `data/corpus.json`.
- Tool manifests were extracted **statically from source** (`scripts/extract_manifests.py`); no third-party code was executed.
- mcpaudit static checks ran on 4,898 extracted tools from 53 repos. memsentry ran on 170 agent-context files (CLAUDE.md, AGENTS.md, .cursor/rules, ...) from 43 repos.
- Findings were hand-reviewed: all 20 "model-directed / cross-tool instruction" findings, a seeded random sample of 40 of the 765 HIGH `permission_scope` findings, all 8 memsentry critical/high/base64 findings, and 12 random long-line findings.

## Results
| Question | Result |
|---|---|
| Real tool-poisoning found in any repo | **0** |
| mcpaudit poisoning-class findings that were true positives | 0 / 20 (95% CI 0-16%) |
| mcpaudit HIGH permission_scope, claim accurate (strict) | 15 / 40 = 37.5% (95% CI 24-53%) |
| ...accurate or weakly accurate (lenient) | 27 / 40 = 67.5% (95% CI 52-80%) |
| memsentry findings that were real injection | 0 / 20 reviewed (of 61): 8 critical/high/blob + 12 random long-line, all benign; 41 not reviewed |
| Confirmed vulnerabilities to disclose | **none** |

Raw counts: mcpaudit 1,018 findings (765 high, 224 medium, 29 low) across 39 repos; memsentry 61 findings (2 critical, 5 high, 54 medium).

"Accurate" means the tool really takes an unconstrained path/URL/command that reaches the claimed resource. Those are still by-design capabilities (a `write_file` tool writes files), so accuracy is not vulnerability rate.

## Why the false positives happen (actionable)
1. `permission_scope` matches the parameter name `path` regardless of meaning: Unity/Godot scene-tree and asset paths, IAM role `path` prefixes, and menu paths are not filesystem access (25 of 40 sampled were false or weak for this reason or a mis-assigned category).
2. The category regex fires on incidental words ("run", "fetch", "file") in descriptions, e.g. a `profile_urn` tool labelled arbitrary command execution.
3. `Cross-tool instruction` flags legitimate "call X first" workflow guidance (AWS, Unity, openstatus).
4. memsentry `long line` flags ordinary prose (all 12 sampled); the zero-width check flags emoji ZWJ sequences (4 of 5) and one genuine word-joiner inside a code span.
5. memsentry `coercive standing instruction` fires critical on authored "you MUST ALWAYS..." coding rules, which are the file's purpose, not injection.

## Limitations (read before quoting numbers)
- Static extraction covered 53 of 90 repos: about 15 have no MCP registration at all (the topic tag is noisy); the rest use patterns the extractor misses (Go/Rust, class-based, wrapper registration). Extraction precision was checked only by path heuristics (4.1% of tools come from tests/fixtures/lint rules) plus spot checks, not measured.
- One reviewer, no second labeller; labels are judgement calls. The permission sample is clustered (Unity, Godot and hexstrike dominate), so the CI understates true uncertainty.
- Corpus is top-starred, so it is biased toward well-maintained projects; it says little about the long tail. Absence of poisoning here does not mean absence in the wild.
- mcpaudit ran on manifests in chunks of 50 tools, so cross-tool checks only see tools in the same chunk.
- Dynamic (LLM) checks were not run.

## Follow-up: mcpaudit v0.7 patch (held-out evaluation)
The failure modes above were turned into a patch (`patches/mcpaudit-0.7.patch`, applied copy in `patches/mcpaudit-0.7/`; the original `mcpaudit` folder was not modified). All 49 existing tests still pass.

Method: a seeded shuffle of the 761 HIGH permission_scope findings gave a dev sample (first 40, used to find failure modes) and a held-out sample (next 40, labelled before the patch was written). Labels: `data/labels.json`; evaluation: `scripts/eval_v07.py`, `data/eval_v07.json`.

| Held-out 40 | v0.6 | v0.7 |
|---|---|---|
| Findings still raised | 40 | 14 |
| Strict precision | 37.5% | 64.3% (95% CI 39-84%, n=14) |
| False positives removed | - | 87.5% (14 of 16) |
| Accurate findings retained | - | 60% (9 of 15) |

The dev sample shows 66.7% strict precision after, but that number is optimistic because the rules were written by looking at it. Corpus-wide, HIGH permission_scope findings fall from 761 to 541 (-29%).

Trade-off, stated plainly: the first-sentence rule and dropping bare "run" cost recall. The six lost accurate cases (ctx_execute "Run code...", smart_rest, memory_import_claude, research_zero_day_opportunities, delete_ecs_infrastructure, export_project) have their risky verb outside the first sentence. Held-out labels are now partly exposed, so a further tuning round needs a fresh sample.

## Follow-up: memsentry v1.2.0 patch
Copy in `patches/memsentry-1.1/`, diff in `patches/memsentry-1.1.patch`; the original `memsentry` folder was not modified. Evaluation: `scripts/eval_memsentry.py`, `data/eval_memsentry.json`.

| | v1.1.0 (original) | v1.2.0 (patched) |
|---|---|---|
| Findings on 170 public agent-context files | 61 | 5 |
| Repo's own malicious sample (`poisoned_memory.md`) | 5 findings | 5 findings (identical) |
| Repo tests | 35 | 39 pass (4 regression tests added) |

Of the 5 remaining, all were reviewed: 1 is a real invisible word-joiner inside a code span (benign origin), 2 are authored "MUST ALWAYS" coding rules (the coercive-instruction check cannot tell an authored rule from an injected one without provenance), and 2 are benign (a 5,937-character flattened document and a one-line shell command).

Caveats: this is a false-positive cleanup evaluated on the same 61 findings that motivated it (only 20 of the 61 were individually reviewed), so it is not a held-out result. Recall is only checked against the repo's own three samples and unit tests. New blind spot: a hidden instruction written as ordinary prose on one 500-4000 character line is no longer flagged by the long-line rule.

## Fresh-sample validation of the mcpaudit v0.7 patch
To test whether the v0.7 result was luck or tuning, I built a new corpus the patch had never seen: 45 further public MCP-server repos (GitHub topic `mcp-server`, ranked 31-45 by stars per language, excluding the original 90; `data/fresh_corpus.json`). Tools were extracted the same way (3,208 tools; 35 of 45 repos yielded tools) with test/fixture paths excluded, then a seeded random sample of 40 HIGH `permission_scope` findings from v0.6 was labelled **blind to whether v0.7 still raised them** (`scripts/fresh_run.py`, `data/fresh_sample.json`, `data/eval_v07_fresh.json`). v0.6 raised 94 HIGH findings on this corpus, v0.7 raised 45.

| Fresh 40 | v0.6 | v0.7 |
|---|---|---|
| Findings still raised | 40 | 22 |
| Strict precision | 40.0% (95% CI 26-55%) | 72.7% (95% CI 52-87%, n=22) |
| Lenient precision (accurate + weak) | 65.0% | 86.4% |
| False positives removed | - | 78.6% (11 of 14) |
| Accurate findings retained | - | 100% (16 of 16) |

Pooling the two samples the patch was not tuned on (held-out 40 + fresh 40): strict precision 38.8% -> 69.4% (25 of 36 findings kept), and 25 of 31 accurate findings retained (80.6%).

Caveats specific to this check: the sample is heavily clustered (22 of 40 findings come from one repo, `opentabs`, a collection of website plugins; 12 repos in total), and one tool appears twice (duplicate registrations count twice). The 100% recall here is much better than the 60% on the earlier held-out set because this corpus is mostly URL/query/path parameters, whereas the earlier misses were "Run code..."-style tools whose risky verb is outside the first sentence; treat 81% pooled recall as the more honest figure. Still one labeller, still static extraction only. The three remaining false positives are two `get_file_content` duplicates (a file ID in a parameter named `path`) and one response field extracted as a parameter.

## Files
`scripts/` collect, extract, run, analyze. `data/` selection, corpus (SHAs), manifests, both findings files, labels, review sample, summary and analysis JSON.
