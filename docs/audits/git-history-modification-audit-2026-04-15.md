# Git History Modification Audit

Date: 2026-04-15
Repo: `pvt-sim_canon`

## Scope

This audit started at the earliest commit currently present in the local git
object database:

- root commit: `e91cdeb` on 2026-02-03

It covered:

- all reachable refs from `git log --all`
- current local branch refs
- current remote refs present locally
- tags
- stash
- both current worktrees
- unreachable commit objects reported by `git fsck --full --unreachable`

This is a full audit of the local git history currently available in this
checkout. It cannot see history that is no longer present in `.git`.

Related deletion-only audit:

- `docs/audits/git-history-deletion-audit-2026-04-15.md`

## Core Surfaces

Core surfaces audited first:

- `README.md`
- `AGENTS.md`
- `pyproject.toml`
- `.github/`
- `src/pvtapp/`
- `src/pvtcore/`

### Core Summary

- commits touching core surfaces: `37`
- file-level change events in core surfaces: `346`
- unique core-surface files touched: `123`
- deletion commits inside core surfaces: `1`
- rename events inside core surfaces: `0`

Important nuance:

- the single core-surface deletion event was `src/pvtcore/experiments/tbp.py`
  in `af4c05a`
- that deletion is not on current `main`; it is archive/tag-side history only
- current `main` shows no core-surface file deletions in this audit scope

### Highest-Churn Core Files

| Path | Events | Adds | Mods | Dels |
|---|---:|---:|---:|---:|
| `src/pvtapp/main.py` | 15 | 1 | 14 | 0 |
| `src/pvtapp/job_runner.py` | 14 | 1 | 13 | 0 |
| `src/pvtapp/widgets/composition_input.py` | 14 | 1 | 13 | 0 |
| `src/pvtapp/widgets/results_view.py` | 13 | 1 | 12 | 0 |
| `src/pvtapp/schemas.py` | 11 | 1 | 10 | 0 |
| `pyproject.toml` | 10 | 1 | 9 | 0 |
| `src/pvtapp/widgets/conditions_input.py` | 10 | 1 | 9 | 0 |
| `src/pvtapp/widgets/text_output_view.py` | 10 | 2 | 8 | 0 |
| `src/pvtapp/style.py` | 8 | 2 | 6 | 0 |
| `src/pvtcore/io/fluid_definition.py` | 8 | 1 | 7 | 0 |
| `src/pvtapp/cli.py` | 7 | 1 | 6 | 0 |
| `AGENTS.md` | 6 | 2 | 4 | 0 |
| `src/pvtapp/widgets/run_log_view.py` | 6 | 2 | 4 | 0 |
| `src/pvtcore/envelope/continuation.py` | 6 | 1 | 5 | 0 |
| `README.md` | 5 | 1 | 4 | 0 |

### Broadest Core Commits

| Date | Commit | Files | Adds | Mods | Dels | Subject |
|---|---|---:|---:|---:|---:|---|
| 2026-02-03 | `e91cdeb` | 70 | 70 | 0 | 0 | Snapshot after claude merge |
| 2026-04-12 | `b898843` | 32 | 10 | 22 | 0 | checkpoint: clean runtime validation expansion branch |
| 2026-02-14 | `68a4450` | 25 | 16 | 9 | 0 | post claude code madness |
| 2026-04-12 | `92312ea` | 21 | 4 | 17 | 0 | Merge validation and EOS updates from feature branch |
| 2026-04-12 | `37b6cbd` | 20 | 3 | 17 | 0 | checkpoint: reconcile validation lane before main sync |
| 2026-04-14 | `2b9ebee` | 17 | 0 | 17 | 0 | checkpoint: land TBP runtime and fit-to-tbp workflow |
| 2026-04-15 | `b6e3ab3` | 17 | 0 | 17 | 0 | checkpoint: preserve runtime and stability worktree slice |
| 2026-04-11 | `72b32c7` | 15 | 3 | 12 | 0 | app/ui: checkpoint canonical desktop shell baseline |
| 2026-02-16 | `6fddc26` | 14 | 7 | 7 | 0 | Merge pvt-sim_codex into pvt-sim_claude (tests green) |
| 2026-02-20 | `11d319d` | 13 | 7 | 6 | 0 | feat: add two-pane workspace UI and widget refactor |
| 2026-04-12 | `9eba778` | 13 | 0 | 13 | 0 | Polish GUI results rail and saved-run workflow |
| 2026-04-07 | `86d9032` | 12 | 7 | 5 | 0 | app/ui: restore workspace shell + cli validation |
| 2026-04-13 | `ee88ad9` | 12 | 0 | 12 | 0 | main: publish gui and tbp follow-on work |
| 2026-04-12 | `d5661b0` | 11 | 1 | 10 | 0 | Polish desktop GUI layout and composition workflow |
| 2026-04-14 | `5490339` | 9 | 0 | 9 | 0 | checkpoint: runtime surfaces, gui polish, and test audit |

### Core-Surface Deletion Inventory

| Date | Commit | Path | Subject | Notes |
|---|---|---|---|---|
| 2026-03-22 | `af4c05a` | `src/pvtcore/experiments/tbp.py` | feat: add TBP-backed plus-fraction schema support | archive/tag-side only, not current `main` |

### Full Core Commit Ledger

| Date | Commit | Files | Adds | Mods | Dels | Subject |
|---|---|---:|---:|---:|---:|---|
| 2026-02-03 | `e91cdeb` | 70 | 70 | 0 | 0 | Snapshot after claude merge |
| 2026-02-14 | `45101d8` | 2 | 1 | 1 | 0 | feat: add stability analysis API |
| 2026-02-14 | `68a4450` | 25 | 16 | 9 | 0 | post claude code madness |
| 2026-02-16 | `6fddc26` | 14 | 7 | 7 | 0 | Merge pvt-sim_codex into pvt-sim_claude (tests green) |
| 2026-02-20 | `11d319d` | 13 | 7 | 6 | 0 | feat: add two-pane workspace UI and widget refactor |
| 2026-03-17 | `b690a50` | 1 | 1 | 0 | 0 | add agents.md |
| 2026-03-22 | `1499a56` | 1 | 0 | 1 | 0 | fix: preserve constant volume in single-phase CVD |
| 2026-03-22 | `629243b` | 5 | 2 | 3 | 0 | fix: harden entrypoint contract and add smoke ci |
| 2026-03-22 | `67d68cc` | 4 | 1 | 3 | 0 | fix: harden entrypoint contract and add smoke ci |
| 2026-03-22 | `af4c05a` | 2 | 0 | 1 | 1 | feat: add TBP-backed plus-fraction schema support |
| 2026-03-22 | `e0ef73a` | 1 | 0 | 1 | 0 | fix: clarify unsupported tuning data types |
| 2026-03-22 | `e53f72b` | 1 | 0 | 1 | 0 | docs: refresh README workflow and CLI status |
| 2026-04-07 | `4e32802` | 1 | 0 | 1 | 0 | io: derive plus-fraction aggregate from TBP cuts |
| 2026-04-07 | `52618ab` | 1 | 0 | 1 | 0 | dev/cache: centralize bytecode + pytest cache |
| 2026-04-07 | `86d9032` | 12 | 7 | 5 | 0 | app/ui: restore workspace shell + cli validation |
| 2026-04-07 | `cb25cd3` | 2 | 0 | 2 | 0 | app/io: restore ui shell + parser validation |
| 2026-04-07 | `d4f0298` | 6 | 0 | 6 | 0 | recover gate0 runtime and regression surfaces |
| 2026-04-08 | `95d72df` | 1 | 0 | 1 | 0 | docs/readme: add Windows install + launch quickstart |
| 2026-04-11 | `72b32c7` | 15 | 3 | 12 | 0 | app/ui: checkpoint canonical desktop shell baseline |
| 2026-04-11 | `f15e715` | 2 | 0 | 2 | 0 | fix(ui): preserve early cancel and guard csv export |
| 2026-04-12 | `37b6cbd` | 20 | 3 | 17 | 0 | checkpoint: reconcile validation lane before main sync |
| 2026-04-12 | `92312ea` | 21 | 4 | 17 | 0 | Merge validation and EOS updates from feature branch |
| 2026-04-12 | `9eba778` | 13 | 0 | 13 | 0 | Polish GUI results rail and saved-run workflow |
| 2026-04-12 | `b898843` | 32 | 10 | 22 | 0 | checkpoint: clean runtime validation expansion branch |
| 2026-04-12 | `d5661b0` | 11 | 1 | 10 | 0 | Polish desktop GUI layout and composition workflow |
| 2026-04-12 | `fb04a9b` | 1 | 0 | 1 | 0 | checkpoint: preserve local phase-envelope continuation work |
| 2026-04-13 | `ee88ad9` | 12 | 0 | 12 | 0 | main: publish gui and tbp follow-on work |
| 2026-04-14 | `2b9ebee` | 17 | 0 | 17 | 0 | checkpoint: land TBP runtime and fit-to-tbp workflow |
| 2026-04-14 | `5490339` | 9 | 0 | 9 | 0 | checkpoint: runtime surfaces, gui polish, and test audit |
| 2026-04-14 | `71ca1a9` | 1 | 0 | 1 | 0 | wip(envelope): checkpoint before worktree cleanup |
| 2026-04-14 | `8d7fc72` | 1 | 0 | 1 | 0 | docs: prefer checkpoint progress over full-suite cleanliness |
| 2026-04-14 | `b41615b` | 1 | 0 | 1 | 0 | fix(gui): tighten results rail scrolling and table fill |
| 2026-04-14 | `ca4748e` | 4 | 0 | 4 | 0 | checkpoint: preserve phase-envelope density handoff work |
| 2026-04-14 | `efa84b8` | 1 | 0 | 1 | 0 | chore: retire blocking codex worktree setup |
| 2026-04-14 | `f069cad` | 1 | 0 | 1 | 0 | wip(gui): checkpoint before worktree cleanup |
| 2026-04-15 | `6b4a638` | 5 | 3 | 2 | 0 | ci: add tiered workflows and validation lanes |
| 2026-04-15 | `b6e3ab3` | 17 | 0 | 17 | 0 | checkpoint: preserve runtime and stability worktree slice |

## Whole Repo

### Whole-Repo Summary

- commits touching tracked repo files: `55`
- file-level change events: `983`
- unique files touched: `495`
- deletion commits: `6`
- rename events: `0`

### Highest-Churn Whole-Repo Files

| Path | Events | Adds | Mods | Dels |
|---|---:|---:|---:|---:|
| `src/pvtapp/main.py` | 15 | 1 | 14 | 0 |
| `src/pvtapp/job_runner.py` | 14 | 1 | 13 | 0 |
| `src/pvtapp/widgets/composition_input.py` | 14 | 1 | 13 | 0 |
| `src/pvtapp/widgets/results_view.py` | 13 | 1 | 12 | 0 |
| `tests/unit/test_pvtapp_desktop_contract.py` | 12 | 1 | 11 | 0 |
| `.gitignore` | 11 | 1 | 10 | 0 |
| `src/pvtapp/schemas.py` | 11 | 1 | 10 | 0 |
| `tests/unit/test_pvtapp_zero_fraction_duplicates.py` | 11 | 2 | 9 | 0 |
| `pyproject.toml` | 10 | 1 | 9 | 0 |
| `src/pvtapp/widgets/conditions_input.py` | 10 | 1 | 9 | 0 |
| `src/pvtapp/widgets/text_output_view.py` | 10 | 2 | 8 | 0 |
| `tests/unit/test_pvtapp_conditions_input.py` | 9 | 2 | 7 | 0 |
| `src/pvtapp/style.py` | 8 | 2 | 6 | 0 |
| `src/pvtcore/io/fluid_definition.py` | 8 | 1 | 7 | 0 |
| `tests/unit/test_fluid_definition_parser.py` | 8 | 1 | 7 | 0 |
| `tests/unit/test_pvtapp_runtime_contract.py` | 8 | 1 | 7 | 0 |
| `docs/input_schema.md` | 7 | 1 | 6 | 0 |
| `PVTSIM_DEPENDENCY_MAP.md` | 7 | 1 | 6 | 0 |
| `src/pvtapp/cli.py` | 7 | 1 | 6 | 0 |
| `tests/unit/test_envelope_continuation.py` | 7 | 2 | 4 | 1 |

### Broadest Whole-Repo Commits

| Date | Commit | Files | Adds | Mods | Dels | Subject |
|---|---|---:|---:|---:|---:|---|
| 2026-04-12 | `b898843` | 216 | 157 | 57 | 2 | checkpoint: clean runtime validation expansion branch |
| 2026-02-03 | `e91cdeb` | 141 | 141 | 0 | 0 | Snapshot after claude merge |
| 2026-03-31 | `3e952c3` | 62 | 62 | 0 | 0 | recovery: preserve restored untracked work after cleanup incident |
| 2026-03-31 | `bc3d182` | 57 | 57 | 0 | 0 | recovery: preserve repo meta and planning artifacts |
| 2026-02-14 | `68a4450` | 46 | 33 | 13 | 0 | post claude code madness |
| 2026-04-12 | `92312ea` | 46 | 15 | 31 | 0 | Merge validation and EOS updates from feature branch |
| 2026-04-12 | `37b6cbd` | 45 | 12 | 33 | 0 | checkpoint: reconcile validation lane before main sync |
| 2026-04-15 | `b6e3ab3` | 45 | 11 | 34 | 0 | checkpoint: preserve runtime and stability worktree slice |
| 2026-04-11 | `72b32c7` | 29 | 10 | 18 | 1 | app/ui: checkpoint canonical desktop shell baseline |
| 2026-04-14 | `2b9ebee` | 29 | 1 | 28 | 0 | checkpoint: land TBP runtime and fit-to-tbp workflow |
| 2026-02-16 | `6fddc26` | 23 | 15 | 8 | 0 | Merge pvt-sim_codex into pvt-sim_claude (tests green) |
| 2026-04-12 | `3719d2f` | 20 | 19 | 1 | 0 | Add external saturation validation anchors |
| 2026-04-14 | `ca4748e` | 19 | 5 | 14 | 0 | checkpoint: preserve phase-envelope density handoff work |
| 2026-04-13 | `ee88ad9` | 17 | 1 | 16 | 0 | main: publish gui and tbp follow-on work |
| 2026-04-14 | `5490339` | 17 | 0 | 17 | 0 | checkpoint: runtime surfaces, gui polish, and test audit |

### Whole-Repo Deletion Inventory

| Date | Commit | Path | Subject |
|---|---|---|---|
| 2026-02-16 | `deb547b` | `.env` | Stop tracking .env |
| 2026-03-22 | `af4c05a` | `src/pvtcore/experiments/tbp.py` | feat: add TBP-backed plus-fraction schema support |
| 2026-04-11 | `72b32c7` | `.env` | app/ui: checkpoint canonical desktop shell baseline |
| 2026-04-11 | `792f3ab` | `TEST_FIXES.md` | docs: remove legacy planning and fix stub docs |
| 2026-04-11 | `792f3ab` | `docs/SCHEMA_VALIDATION_FIXES.md` | docs: remove legacy planning and fix stub docs |
| 2026-04-11 | `792f3ab` | `docs/audits/README.md` | docs: remove legacy planning and fix stub docs |
| 2026-04-11 | `792f3ab` | `docs/plans/README.md` | docs: remove legacy planning and fix stub docs |
| 2026-04-11 | `792f3ab` | `docs/plans/pvt-sim/README.md` | docs: remove legacy planning and fix stub docs |
| 2026-04-11 | `a5beee6` | `tests/unit/test_envelope_continuation.py` | test(mainline): keep phase-envelope certification on dedicated lane |
| 2026-04-11 | `a5beee6` | `tests/unit/test_envelope_local_roots.py` | test(mainline): keep phase-envelope certification on dedicated lane |
| 2026-04-11 | `a5beee6` | `tests/unit/test_envelope_trace.py` | test(mainline): keep phase-envelope certification on dedicated lane |
| 2026-04-12 | `b898843` | `.claude/settings.local.json` | checkpoint: clean runtime validation expansion branch |
| 2026-04-12 | `b898843` | `CLAUDE.md` | checkpoint: clean runtime validation expansion branch |

### Whole-Repo Commit Ledger

| Date | Commit | Files | Adds | Mods | Dels | Subject |
|---|---|---:|---:|---:|---:|---|
| 2026-02-03 | `e91cdeb` | 141 | 141 | 0 | 0 | Snapshot after claude merge |
| 2026-02-14 | `45101d8` | 3 | 2 | 1 | 0 | feat: add stability analysis API |
| 2026-02-14 | `68a4450` | 46 | 33 | 13 | 0 | post claude code madness |
| 2026-02-14 | `719834f` | 2 | 2 | 0 | 0 | feat: add stability analysis API |
| 2026-02-16 | `01fbce4` | 1 | 0 | 1 | 0 | .gitignore update: Ignore Windows Explorer metadata files |
| 2026-02-16 | `6fddc26` | 23 | 15 | 8 | 0 | Merge pvt-sim_codex into pvt-sim_claude (tests green) |
| 2026-02-16 | `90ae2ea` | 4 | 0 | 4 | 0 | location agnostic fix |
| 2026-02-16 | `c242796` | 1 | 0 | 1 | 0 | update .gitignore |
| 2026-02-16 | `deb547b` | 1 | 0 | 0 | 1 | Stop tracking .env |
| 2026-02-20 | `11d319d` | 16 | 9 | 7 | 0 | feat: add two-pane workspace UI and widget refactor |
| 2026-03-17 | `b690a50` | 1 | 1 | 0 | 0 | add agents.md |
| 2026-03-22 | `1499a56` | 2 | 0 | 2 | 0 | fix: preserve constant volume in single-phase CVD |
| 2026-03-22 | `629243b` | 8 | 3 | 5 | 0 | fix: harden entrypoint contract and add smoke ci |
| 2026-03-22 | `67d68cc` | 7 | 2 | 5 | 0 | fix: harden entrypoint contract and add smoke ci |
| 2026-03-22 | `af4c05a` | 8 | 3 | 4 | 1 | feat: add TBP-backed plus-fraction schema support |
| 2026-03-22 | `e0ef73a` | 3 | 2 | 1 | 0 | fix: clarify unsupported tuning data types |
| 2026-03-22 | `e53f72b` | 1 | 0 | 1 | 0 | docs: refresh README workflow and CLI status |
| 2026-03-31 | `2161b18` | 1 | 0 | 1 | 0 | test: reconcile TBP example parser coverage |
| 2026-03-31 | `3e952c3` | 62 | 62 | 0 | 0 | recovery: preserve restored untracked work after cleanup incident |
| 2026-03-31 | `3fa9c4c` | 2 | 2 | 0 | 0 | test: reconcile codex TBP and tuning policy coverage |
| 2026-03-31 | `bc3d182` | 57 | 57 | 0 | 0 | recovery: preserve repo meta and planning artifacts |
| 2026-03-31 | `cc3bc05` | 2 | 2 | 0 | 0 | test: preserve recovered depletion regression coverage |
| 2026-03-31 | `e6e523d` | 3 | 3 | 0 | 0 | test: preserve recovered pvtapp regression coverage |
| 2026-03-31 | `e9213a8` | 2 | 2 | 0 | 0 | test: reconcile codex pvtapp workflow files |
| 2026-04-07 | `4e32802` | 2 | 1 | 1 | 0 | io: derive plus-fraction aggregate from TBP cuts |
| 2026-04-07 | `52618ab` | 3 | 0 | 3 | 0 | dev/cache: centralize bytecode + pytest cache |
| 2026-04-07 | `86d9032` | 15 | 8 | 7 | 0 | app/ui: restore workspace shell + cli validation |
| 2026-04-07 | `cb25cd3` | 4 | 0 | 4 | 0 | app/io: restore ui shell + parser validation |
| 2026-04-07 | `d4f0298` | 7 | 0 | 7 | 0 | recover gate0 runtime and regression surfaces |
| 2026-04-08 | `95d72df` | 1 | 0 | 1 | 0 | docs/readme: add Windows install + launch quickstart |
| 2026-04-11 | `72b32c7` | 29 | 10 | 18 | 1 | app/ui: checkpoint canonical desktop shell baseline |
| 2026-04-11 | `792f3ab` | 5 | 0 | 0 | 5 | docs: remove legacy planning and fix stub docs |
| 2026-04-11 | `a5beee6` | 4 | 0 | 1 | 3 | test(mainline): keep phase-envelope certification on dedicated lane |
| 2026-04-11 | `f15e715` | 4 | 0 | 4 | 0 | fix(ui): preserve early cancel and guard csv export |
| 2026-04-11 | `f38a24c` | 1 | 0 | 1 | 0 | docs: rename canonical branch references to main |
| 2026-04-12 | `3719d2f` | 20 | 19 | 1 | 0 | Add external saturation validation anchors |
| 2026-04-12 | `37b6cbd` | 45 | 12 | 33 | 0 | checkpoint: reconcile validation lane before main sync |
| 2026-04-12 | `92312ea` | 46 | 15 | 31 | 0 | Merge validation and EOS updates from feature branch |
| 2026-04-12 | `9eba778` | 16 | 0 | 16 | 0 | Polish GUI results rail and saved-run workflow |
| 2026-04-12 | `b898843` | 216 | 157 | 57 | 2 | checkpoint: clean runtime validation expansion branch |
| 2026-04-12 | `d5661b0` | 15 | 1 | 14 | 0 | Polish desktop GUI layout and composition workflow |
| 2026-04-12 | `e94de03` | 1 | 0 | 1 | 0 | Ignore local docs and agent tooling artifacts |
| 2026-04-12 | `fb04a9b` | 3 | 0 | 3 | 0 | checkpoint: preserve local phase-envelope continuation work |
| 2026-04-13 | `ee88ad9` | 17 | 1 | 16 | 0 | main: publish gui and tbp follow-on work |
| 2026-04-14 | `2b9ebee` | 29 | 1 | 28 | 0 | checkpoint: land TBP runtime and fit-to-tbp workflow |
| 2026-04-14 | `5490339` | 17 | 0 | 17 | 0 | checkpoint: runtime surfaces, gui polish, and test audit |
| 2026-04-14 | `71ca1a9` | 3 | 1 | 2 | 0 | wip(envelope): checkpoint before worktree cleanup |
| 2026-04-14 | `8d7fc72` | 1 | 0 | 1 | 0 | docs: prefer checkpoint progress over full-suite cleanliness |
| 2026-04-14 | `b41615b` | 2 | 0 | 2 | 0 | fix(gui): tighten results rail scrolling and table fill |
| 2026-04-14 | `ca4748e` | 19 | 5 | 14 | 0 | checkpoint: preserve phase-envelope density handoff work |
| 2026-04-14 | `efa84b8` | 2 | 0 | 2 | 0 | chore: retire blocking codex worktree setup |
| 2026-04-14 | `f069cad` | 2 | 0 | 2 | 0 | wip(gui): checkpoint before worktree cleanup |
| 2026-04-15 | `0bafa39` | 6 | 5 | 1 | 0 | Add phase-envelope validation harness and DWSIM helper |
| 2026-04-15 | `6b4a638` | 6 | 3 | 3 | 0 | ci: add tiered workflows and validation lanes |
| 2026-04-15 | `b6e3ab3` | 45 | 11 | 34 | 0 | checkpoint: preserve runtime and stability worktree slice |

## Current Dirty Tree Snapshot

This section is not git history. It is the current uncommitted state at audit
time.

### Current Dirty Core Surfaces

```text
MM .github/workflows/ci.yml
M  .github/workflows/nightly.yml
MD .github/workflows/smoke.yml
MM README.md
M  pyproject.toml
 M src/pvtapp/widgets/results_view.py
```

### Current Full Dirty Tree

```text
A  .cursor/README.md
A  .cursor/mcp.json.example
A  .cursor/rules/00-repo-contract.mdc
A  .cursor/rules/10-runtime-surface.mdc
A  .cursor/rules/20-python-boundaries.mdc
AM .cursor/rules/30-verification-and-lanes.mdc
A  .cursorindexingignore
MM .github/workflows/ci.yml
M  .github/workflows/nightly.yml
MD .github/workflows/smoke.yml
MM .gitignore
A  .vscode/extensions.json
MM .vscode/settings.json
AM .vscode/tasks.json
MM README.md
MM docs/development.md
MM docs/validation_plan.md
M  pyproject.toml
A  scripts/run_full_validation.py
AM scripts/run_premerge_checks.py
 M src/pvtapp/widgets/results_view.py
M  tests/conftest.py
M  tests/unit/test_envelope_continuation.py
 M tests/unit/test_pvtapp_desktop_contract.py
?? .env.defaults
?? docs/audits/
```

## Interpretation

- The highest-churn runtime files are concentrated in the desktop/runtime
  surface: `src/pvtapp/main.py`, `src/pvtapp/job_runner.py`,
  `src/pvtapp/widgets/composition_input.py`, and
  `src/pvtapp/widgets/results_view.py`.
- The broadest whole-repo change burst is `b898843` on 2026-04-12. That commit
  touched `216` files and includes two deletions.
- There are no rename events in the reachable repo history audited here.
- Inside the defined core trust surfaces, the audit found no deletions on
  current `main`.
- Across the whole repo, deletion history is limited to the `6` commits listed
  above.
