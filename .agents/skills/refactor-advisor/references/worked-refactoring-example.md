# Worked Refactoring Example: God File Decomposition

Legacy note: if this example mentions historical `repo_*` helper names,
treat them as shorthand for local file reads, `rg`, git history, and the
project's real test commands. They are not required tools.

A complete refactoring walkthrough showing how to break up a 600-line file
that does too many things into focused modules.

---

## The Patient

`app/llm/router.py` — 587 lines, fan_in=8, fan_out=12.

```
repo_coupling_analysis() reports:
  risk_score: 0.72
  instability: 0.60
  classification: GOD FILE
  change_propagation: 14 files affected by changes
```

Reading the file reveals it handles:
1. LLM backend selection (Ollama, OpenAI, Anthropic)
2. Prompt formatting and template rendering
3. Streaming response assembly
4. Token counting and context window management
5. Error handling and retry logic for all backends
6. Response caching

Six responsibilities in one file. Changes to caching break routing tests.
Changes to prompt formatting touch the same file as backend selection.

---

## Step 1: Map the Responsibilities

Read the file completely. Group functions by what they do:

### Group A: Backend Selection (routing)
```
route_to_backend(prompt, settings) → BackendClient  # lines 45-89
_pick_backend(settings) → str                       # lines 91-120
_validate_backend(name) → bool                      # lines 122-140
```

### Group B: Prompt Formatting
```
format_prompt(template, variables) → str            # lines 150-210
_render_system_prompt(role, context) → str           # lines 212-250
_inject_tool_descriptions(prompt, tools) → str       # lines 252-290
```

### Group C: Streaming
```
stream_response(client, prompt) → Generator          # lines 300-350
_assemble_chunks(chunks) → str                       # lines 352-380
_handle_stream_error(error, client) → str            # lines 382-420
```

### Group D: Token Management
```
count_tokens(text, model) → int                      # lines 430-460
truncate_to_context(messages, max_tokens) → list     # lines 462-510
_estimate_token_count(text) → int                    # lines 512-530
```

### Group E: Error/Retry
```
retry_with_backoff(func, retries, backoff) → Any     # lines 540-570
```

### Group F: Caching
```
_cache_key(prompt, settings) → str                   # lines 23-30
_check_cache(key) → Optional[str]                    # lines 32-38
_store_cache(key, response) → None                   # lines 40-43
```

---

## Step 2: Check What Imports What

Within the file, trace internal calls:
- `route_to_backend` calls `_pick_backend`, `_validate_backend`
- `stream_response` calls `_assemble_chunks`, `_handle_stream_error`, `retry_with_backoff`
- `route_to_backend` calls `format_prompt` (Group A depends on Group B)
- `route_to_backend` calls `_check_cache`, `_store_cache` (Group A depends on Group F)
- Token management is called by streaming (Group C depends on Group D)

Dependency flow: **F → A → B**, **D → C → E**

Two clean clusters:
- Routing cluster: caching + backend selection + prompt formatting
- Execution cluster: token management + streaming + retry

---

## Step 3: Prescribe the Extraction

### Operation 1: Extract `app/llm/prompt.py` — Risk: LOW
Move Group B (prompt formatting) out. It has no dependencies on anything
else in router.py. Three functions, ~140 lines.

**Blast radius:** `route_to_backend` calls `format_prompt` — update the
import. 0 external files import prompt formatting directly (they go through
the router).

**Verify:** Run tests for router. The import change is the only code change.

### Operation 2: Extract `app/llm/tokens.py` — Risk: LOW
Move Group D (token management) out. It's a pure utility — no dependencies
on other groups. Three functions, ~100 lines.

**Blast radius:** `stream_response` calls `count_tokens` — update import.
Also check: does anything outside router.py call `count_tokens` directly?
```
repo_search_content(pattern="count_tokens")
→ app/llm/router.py:305 (internal call)
→ app/api/llm.py:67 (external call!)
```

One external caller — `app/api/llm.py` imports `count_tokens` from router.
After extraction, update that import too.

**Verify:** Run tests for both router and api/llm.

### Operation 3: Extract `app/llm/streaming.py` — Risk: MEDIUM
Move Groups C and E (streaming + retry) together. They're tightly coupled
and form a coherent unit. ~120 lines.

**Blast radius:** `route_to_backend` calls `stream_response` — update import.
External callers of `stream_response`:
```
repo_search_content(pattern="stream_response")
→ app/api/llm.py:72 (external call)
→ app/api/streaming.py:15 (external call)
```

Two external callers. Both need import updates.

**Medium risk because:** Streaming has error handling paths that interact
with the retry logic. Extracting both together preserves the relationship,
but verify that the extracted module has everything it needs (no dangling
references back to router.py).

**Verify:** Run full test suite — streaming touches multiple modules.

### Operation 4: Extract `app/llm/cache.py` — Risk: LOW
Move Group F (caching). Three small functions, ~20 lines. No external
callers (cache is internal to router).

**Verify:** Router tests only.

### Final state of `app/llm/router.py`

After all extractions, router.py contains only Group A (backend selection):
~100 lines, fan_out reduced from 12 to 4 (imports prompt, streaming, cache, tokens).
Each extracted module is focused, testable, and independently modifiable.

---

## Step 4: Execution Order

1. Extract `prompt.py` first (zero external callers, lowest risk)
2. Extract `tokens.py` second (one external caller, easy to verify)
3. Extract `cache.py` third (internal only, easy)
4. Extract `streaming.py` last (two external callers, most complex)

**Why this order:** Start with the easiest extraction. Each successful step
validates the process and reduces the remaining file. By the time you reach
the hardest extraction (streaming), the file is already much smaller and
easier to reason about.

---

## Key Lessons

1. **Read the whole file before planning.** The dependency flow between groups
   determined the extraction order. You can't know this from coupling scores
   alone.

2. **Check external callers before extracting.** `count_tokens` had an
   external caller that wasn't obvious from the router file alone.

3. **Extract pure utilities first.** Token counting and prompt formatting
   have no side effects and no dependencies — they're the safest to move.

4. **Keep tightly coupled code together.** Streaming and retry were extracted
   as one module because they call each other. Splitting them would create
   a circular dependency.

5. **The goal is focused files, not small files.** A 100-line file with
   two responsibilities is worse than a 200-line file with one.
