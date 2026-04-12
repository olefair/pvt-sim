---
name: "pete-petroleum"
description: "Use ONLY for the Pete petroleum voice-assistant repo to implement Codex-priority upgrades: dual written vs spoken responses, LLM backend/config menu improvements (incl. vLLM/sglang investigation), cloud vs local compute routing, research-grade web search w/ citations + credibility scoring + scholar mode, class/project petroleum memory, chat viewing/archiving lifecycle, and ElevenLabs model selection. Not for general petroleum Q&A."
---

# Pete Petroleum Skill 🛢️

This skill is a repo-specific execution playbook for Pete’s petroleum-focused voice assistant.

## When to use ✅
Use this skill when the request is to implement or harden any of the following (Codex priority list):

1) Dual response routing (written “textbook” vs spoken “teacher”)
2) Investigate vLLM/sglang as an alternative to Ollama
3) Fix quick setup menu LLM config (especially GPU routing)
4) Add cloud vs local compute selection + submenus for providers
5) Upgrade web search to research-grade summaries + citations + source ranking + scholar mode
6) Class/project memory (petroleum notes, preferences, notation, exam checklists)
7) Chat lifecycle: view/manage/archive chats; manage context window pressure
8) ElevenLabs model selection in setup UX (v1 / v2 / v2.5 / etc.)

## When NOT to use ❌
- Pure Q&A about petroleum engineering concepts
- Generic refactors unrelated to the eight items above
- Large repo rewrites or dependency overhauls

## Required inputs (you must ask for these if missing)
- Which item number (1–8) is being worked on.
- Where it should run:
  - Local (developer machine) vs Cloud (Codex cloud environment)
- Whether internet access is permitted for this task (needed for item 2 and for validating item 5).

## Operating rules (non-negotiable)
- Prefer the smallest safe change; no broad refactors.
- Never introduce new dependencies unless strictly required; explain what/why/how to verify.
- Never print or commit secrets (API keys/tokens). If needed, request they be set as environment variables.
- Do not claim commands/tests ran unless you provide their exact output.

## Workflow (follow in order)
1) Identify the target item (1–8).
2) Read the relevant spec(s) under `docs/specs/` before editing code.
3) Locate the smallest set of files to change.
4) Implement minimal patch.
5) Run the fastest applicable checks:
   - Prefer repo-documented checks.
   - In cloud Linux containers, fall back to `python -m pytest -q` scoped to touched areas.
6) Summarize what changed and how it maps to the target item.

## Pete Vault Document Context

For this workspace, `docs/` means the shared Obsidian vault rooted at
`C:\Users\olefa\dev\pete-workspace\docs`, not a repo-local `docs/` folder
inside an individual project repo or uploaded snapshot. Treat YAML
frontmatter, `[[wikilinks]]`, and backlink-oriented body linking as part of
the operating contract whenever reading or writing notes there.

When a Pete task reads or writes vault-native documents, read and follow:

- `docs/reference/workspace/reference_frontmatter-contract-canonical_v1_2026-03-17.md`
- `docs/reference/workspace/reference_generated-document-routing_v1_2026-03-17.md`
- `docs/reference/workspace/reference_workspace-conventions.md`
- `docs/reference/workspace/reference_vault-context-intake-and-link-strengthening_v1_2026-03-19.md`

Treat document frontmatter as operational context, not decoration:

- `links` are must-read preload context
- `related` is adjacent context that should still be considered
- inspect `blocked_by`, `supersedes`, and `superseded_by` when present
- parse body wikilinks and run a backlink fallback search by basename or slug when no dedicated backlinks tool exists
- when generating a vault note, use canonical family routing and add governing specs, prior or successor notes, and materially adjacent canonical notes so the output improves vault navigation instead of becoming an orphan

---

# Task modules

## 1) Dual response routing (written vs spoken)
**Goal:** For a single user prompt, produce:
- Written response: full, structured, “textbook”
- Spoken response (TTS): shorter, “teacher”, with redundancy removed

**Read first:**
- `docs/specs/dual-response.md`
- `app/system/tts.py`
- `app/llm/router.py`
- `app/api/llm.py`

**Implementation targets:**
- Ensure spoken mode supports: `strip`, `smart`, `llm` variants
- Provide safe defaults + user overrides via env/config
- Maintain consistent API schema returning both channels

**Done when:**
- API returns both `written_text` and `spoken_text` (or equivalent)
- TTS consistently uses spoken channel
- Tests/fixtures cover mode behavior

---

## 2) Investigate vLLM/sglang instead of Ollama
**Goal:** Produce a factual comparison and (if approved) a minimal integration plan.

**Read first:**
- `app/llm/llm_client.py` (existing TODO notes)
- `docs/specs/llm-config-and-setup.md`

**Deliverables (order):**
1) Investigation summary: setup friction, serving model support, streaming, batching, GPU support, OS constraints
2) Recommendation: keep Ollama vs add vLLM/sglang as optional provider
3) If implementing: add provider behind a config flag; do not remove Ollama by default

**Done when:**
- A clear integration plan exists
- Any code change is optional, non-breaking, and gated by config

---

## 3) Fix LLM config in quick setup menu
**Goal:** Quick setup must reliably set the chosen LLM backend/model and GPU routing without no-op functions.

**Read first:**
- `app/setup/quick_config.py`
- `docs/specs/llm-config-and-setup.md`

**Focus areas:**
- Ensure GPU selection actually updates configuration (avoid placeholder/no-op updates)
- Ensure “Ollama model name” and “backend selection” persist to the correct config store

**Done when:**
- Quick setup updates the right config fields
- A unit/integration check proves the values persist and are read by runtime config

---

## 4) Add cloud vs local compute config menu (+ submenus)
**Goal:** The setup UX should clearly separate:
- Cloud providers (OpenAI, Anthropic, etc.)
- Local providers (Ollama now; optional vLLM/sglang later)

**Read first:**
- `app/setup/full_setup.py`
- `docs/specs/llm-config-and-setup.md`

**Implementation targets:**
- Menus are nested and non-confusing
- Provider-specific API key fields are only shown when relevant
- Local backends can be selected without requiring cloud config

**Done when:**
- Users can configure cloud vs local in a single session without ambiguity
- Config output is consistent and validated

---

## 5) Upgrade web search to research-grade pipeline
**Goal:** Replace basic snippets with:
- multi-query search strategy
- summarized answer with inline citations
- credibility scoring / domain weighting
- optional `--scholar/--academic` mode for papers

**Read first:**
- `docs/specs/web-research.md`
- `app/plugins/web/search.py`

**Constraints:**
- Must stay gated behind `PETE_ENABLE_NETWORK_TOOLS=1`
- Treat web content as untrusted
- Prefer deterministic formatting for citations

**Done when:**
- API returns: `answer`, `citations[]`, `sources[]` with credibility scores
- Scholar mode returns academic sources (or clearly signals unavailability)

---

## 6) Class/project petroleum memory
**Goal:** Persist and retrieve:
- class-specific notation
- project context (reservoir parameters, assumptions)
- user preferences (style, units, typical workflows)

**Read first:**
- `docs/specs/petroleum-knowledge-base.md`
- `app/memory/` (store + retrieval)

**Implementation targets:**
- Short, robust memory schema (key/value + provenance + timestamps)
- Retrieval scoped to current class/project
- User-visible controls to review and prune

**Done when:**
- Memory write + retrieval works in at least one end-to-end flow
- A deletion/prune path exists

---

## 7) View/manage/archive chats (context window lifecycle)
**Goal:** Keep working context tight by:
- browsing chats
- archiving old chats
- summarizing/compacting older context

**Read first:**
- `docs/specs/memory-lifecycle.md`
- `app/memory/` + any UI surface that shows chats

**Done when:**
- User can list chats, archive/unarchive, and restore context as needed
- Compaction strategy exists (even if basic)

---

## 8) ElevenLabs model selection in setup
**Goal:** Setup UX lets user pick ElevenLabs model family/version and stores it in config.

**Read first:**
- `app/setup/full_setup.py` and `app/setup/quick_config.py`
- `app/system/tts.py`

**Done when:**
- Selected model persists and is used for TTS calls
- Sensible defaults exist

---

# Environment variables (commonly used)
- `PETE_TTS_SPOKEN_MODE` = `strip|smart|llm`
- `PETE_TTS_SPOKEN_MAX_SENTENCES`, `PETE_TTS_SPOKEN_MAX_CHARS`
- `PETE_ENABLE_NETWORK_TOOLS` = `0|1`
- `PETE_WARMUP_LLM` = `0|1`
- `PETE_ELEVENLABS_MODEL` = ElevenLabs model id/name

# Secrets / keys
Never commit keys. In cloud environments, prefer keeping keys out of the agent phase whenever possible.
