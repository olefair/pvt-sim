# Git History Deletion Audit

Date: 2026-04-15
Repo: `pvt-sim_canon`

## Scope

This audit scanned:

- all branch refs
- all remote refs present locally
- all tag refs
- `refs/stash`
- all listed worktrees
- unreachable commit objects reported by `git fsck --full --unreachable`

Observed repo state during audit:

- worktrees: 2
- named branches: `main`
- remote branches present locally: `origin/main`
- reachable commits from `--all`: 71
- unreachable commits found by `git fsck`: 2

## Worktrees

- `C:/Users/olefa/dev/pete-workspace/pvt-sim_canon` at detached `57b7dd3`
- `C:/Users/olefa/.codex/worktrees/integration-root-pvt-sim_canon` on `main` at `57b7dd3`

## Reachable Deletion Inventory

The full reachable history contains 6 deletion commits covering 13 deleted file paths.

### Deletions present on `main`

1. `72b32c7` on 2026-04-11
   Subject: `app/ui: checkpoint canonical desktop shell baseline`
   Deleted:
   - `.env`

2. `792f3ab` on 2026-04-11
   Subject: `docs: remove legacy planning and fix stub docs`
   Deleted:
   - `TEST_FIXES.md`
   - `docs/SCHEMA_VALIDATION_FIXES.md`
   - `docs/audits/README.md`
   - `docs/plans/README.md`
   - `docs/plans/pvt-sim/README.md`

3. `a5beee6` on 2026-04-11
   Subject: `test(mainline): keep phase-envelope certification on dedicated lane`
   Deleted:
   - `tests/unit/test_envelope_continuation.py`
   - `tests/unit/test_envelope_local_roots.py`
   - `tests/unit/test_envelope_trace.py`

4. `b898843` on 2026-04-12
   Subject: `checkpoint: clean runtime validation expansion branch`
   Deleted:
   - `.claude/settings.local.json`
   - `CLAUDE.md`

### Deletions only present on archive/tag side history

5. `deb547b` on 2026-02-16
   Subject: `Stop tracking .env`
   Deleted:
   - `.env`
   Contained by tags:
   - `archive-ui-two-pane-workspace`
   - `recovery-untracked-restoration-2026-03-31`

6. `af4c05a` on 2026-03-22
   Subject: `feat: add TBP-backed plus-fraction schema support`
   Deleted:
   - `src/pvtcore/experiments/tbp.py`
   Contained by tags:
   - `recovery-untracked-restoration-2026-03-31`

## Unreachable Commit Check

`git fsck --full --unreachable` reported two unreachable commits:

- `8fc58c6` - index snapshot on `codex/validate-composition-across-modules`
- `9a7be4f` - `checkpoint: runtime surfaces, gui polish, and test audit`

Neither unreachable commit introduced additional file deletions beyond the reachable deletion inventory above.

## Core-Surface Check

Current `main` shows no file-deletion commits touching these repo-critical surfaces:

- `README.md`
- `AGENTS.md`
- `pyproject.toml`
- `.github/`
- `src/pvtapp/`
- `src/pvtcore/`

This does not mean those surfaces were never modified. It means the deletion audit found no file removals in those surfaces on current `main`.

## .env Findings

- `.env` was created in `e91cdeb` on 2026-02-03
- `.env` content changed in `52618ab` on 2026-04-07 from `.pycache` to `.pycache/bytecode`
- tracked `.env` was deleted on `main` in `72b32c7` on 2026-04-11
- the current on-disk `.env` is ignored by `.gitignore` and not tracked

## Conclusion

The audit did not find any deletion commits beyond the 6 commits listed above across:

- all reachable refs in this repo
- both current worktrees
- stash
- archive/recovery tags
- the 2 unreachable commit objects currently present in the object database
