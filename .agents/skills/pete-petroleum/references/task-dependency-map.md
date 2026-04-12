# Pete Petroleum — Task Dependency Map

How the 8 Codex-priority items relate to each other. Use this to determine
implementation order and avoid blocked work.

---

## Dependency Graph

```
                    ┌──────────────────┐
                    │  3. Fix LLM      │
                    │  quick config    │
                    └───────┬──────────┘
                            │ must work before
                            ▼
┌──────────────────┐   ┌──────────────────┐
│  2. Investigate  │──▶│  4. Cloud vs     │
│  vLLM/sglang     │   │  local config    │
└──────────────────┘   └───────┬──────────┘
  (informs 4's menu)          │ providers must be selectable before
                              ▼
                    ┌──────────────────┐
                    │  1. Dual response│
                    │  routing         │
                    └───────┬──────────┘
                            │ TTS needs spoken channel
                            ▼
                    ┌──────────────────┐
                    │  8. ElevenLabs   │
                    │  model selection │
                    └──────────────────┘

┌──────────────────┐   ┌──────────────────┐
│  5. Web search   │   │  6. Class/project│
│  research-grade  │   │  petroleum       │
└──────────────────┘   │  memory          │
  (independent)        └───────┬──────────┘
                               │ memory must exist before
                               ▼
                       ┌──────────────────┐
                       │  7. Chat         │
                       │  lifecycle       │
                       └──────────────────┘
```

---

## Recommended Implementation Order

### Tier 1 — No dependencies, unblocks others

**Task 3: Fix LLM quick config**
- Depends on: nothing
- Unblocks: Task 4 (config menus build on working quick config)
- Risk: LOW — scoped to `quick_config.py`
- Time estimate: small

**Task 2: Investigate vLLM/sglang**
- Depends on: nothing (research task)
- Unblocks: Task 4 (investigation determines what providers to add)
- Risk: LOW — investigation only, no code changes
- Time estimate: medium (research + write-up)

### Tier 2 — Depends on Tier 1

**Task 4: Cloud vs local config menu**
- Depends on: Task 3 (config persistence must work), Task 2 (provider list)
- Unblocks: Task 1 (backend selection informs response routing)
- Risk: MEDIUM — touches `full_setup.py` and `quick_config.py`
- Key files: `app/setup/full_setup.py`, `app/setup/quick_config.py`

### Tier 3 — Depends on Tier 2

**Task 1: Dual response routing**
- Depends on: Task 4 (need backend configured to generate responses)
- Unblocks: Task 8 (TTS model selection needs spoken channel)
- Risk: MEDIUM — new code path through LLM router and TTS
- Key files: `app/llm/router.py`, `app/api/llm.py`, `app/system/tts.py`

### Tier 4 — Depends on Tier 3

**Task 8: ElevenLabs model selection**
- Depends on: Task 1 (spoken channel must exist for TTS to use)
- Unblocks: nothing
- Risk: LOW — config + TTS client change
- Key files: `app/setup/full_setup.py`, `app/system/tts.py`

### Independent Track A

**Task 5: Research-grade web search**
- Depends on: nothing
- Unblocks: nothing
- Risk: MEDIUM — new pipeline, but gated behind env var
- Key files: `app/plugins/web/search.py`
- Can be implemented in parallel with any tier

### Independent Track B

**Task 6: Class/project petroleum memory**
- Depends on: nothing
- Unblocks: Task 7 (lifecycle management needs memory store)
- Risk: MEDIUM — new memory schema
- Key files: `app/memory/`

**Task 7: Chat lifecycle**
- Depends on: Task 6 (memory store must exist)
- Unblocks: nothing
- Risk: MEDIUM — touches memory and UI surface
- Key files: `app/memory/`, UI chat views

---

## Parallel Execution Strategy

If multiple agents or sessions are working simultaneously:

- **Agent A:** Tasks 3 → 4 → 1 → 8 (main LLM pipeline)
- **Agent B:** Tasks 6 → 7 (memory pipeline)
- **Agent C:** Task 5 (web search — fully independent)
- **Agent D:** Task 2 (research — fully independent)

No conflicts between B, C, D. Agent A's work on config/setup files
could conflict with Agent B if both touch `app/setup/` — coordinate
on that directory.

---

## Shared File Risks

These files are touched by multiple tasks:

| File | Tasks | Conflict Risk |
|------|-------|---------------|
| `app/setup/full_setup.py` | 3, 4, 8 | HIGH — sequential only |
| `app/setup/quick_config.py` | 3, 4 | MEDIUM — sequential only |
| `app/system/tts.py` | 1, 8 | MEDIUM — 1 before 8 |
| `app/llm/router.py` | 1 | LOW — single owner |
| `app/memory/` | 6, 7 | MEDIUM — 6 before 7 |

Never modify a shared file from two tasks in parallel. Complete the
earlier task's changes to that file before starting the later task.
