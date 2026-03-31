# Worked Bug Investigation Example

Legacy note: if this example mentions historical `repo_*` helper names,
treat them as shorthand for local file reads, `rg`, git history, and the
project's real test commands. They are not required tools.

A complete investigation from symptom report to root cause, showing how
to use the tool suite and hypothesis framework.

---

## Symptom Report

"The voice assistant sometimes returns the response from the PREVIOUS
question instead of the current one. It doesn't happen every time —
maybe 1 in 5 requests. Restarting fixes it temporarily."

---

## Phase 1: Symptom Intake

**Expected:** Each prompt gets its own response.
**Actual:** Sometimes returns a stale response from a prior request.
**Trigger:** Intermittent, ~20% of requests. More common under load.
**Scope:** Affects the main chat endpoint.

**Key signals:**
- "Intermittent" → likely state/concurrency issue, not logic error
- "Previous response" → something is caching or sharing state across requests
- "Restarting fixes it" → confirms it's accumulated runtime state
- "More common under load" → concurrency is the prime suspect

---

## Phase 2: Code Path Tracing

### Entry point

Search for the chat endpoint:
```
repo_search_content(pattern="@app.post.*chat|@router.post.*chat")
→ app/api/llm.py:45: @router.post("/chat")
```

### Trace the call chain

Read `app/api/llm.py`. The `/chat` endpoint calls:
1. `parse_request(body)` → extracts prompt, settings
2. `router.route(prompt, settings)` → picks the LLM backend
3. `backend.generate(prompt)` → calls the LLM
4. `format_response(result)` → wraps the response

Run `repo_impact_graph` with `target_symbols=["generate"]`:
```
→ app/llm/router.py:route() calls → app/llm/llm_client.py:generate()
→ llm_client.generate() calls → app/llm/llm_client.py:_stream_response()
→ _stream_response() writes to → self._buffer
```

**Red flag:** `self._buffer` — instance state on the client.

### Read the suspicious code

```python
# app/llm/llm_client.py
class LLMClient:
    def __init__(self, endpoint):
        self.endpoint = endpoint
        self._buffer = ""          # ← SHARED MUTABLE STATE

    def generate(self, prompt):
        self._buffer = ""          # Reset buffer
        for chunk in self._stream_response(prompt):
            self._buffer += chunk
        return self._buffer

    def _stream_response(self, prompt):
        response = requests.post(self.endpoint, json={"prompt": prompt}, stream=True)
        for line in response.iter_lines():
            yield line.decode()
```

### Check how the client is instantiated

```
repo_search_content(pattern="LLMClient(")
→ app/llm/router.py:12: _client = LLMClient(endpoint)  # MODULE-LEVEL SINGLETON
```

**Found it.** The LLM client is a module-level singleton shared across all
requests. `self._buffer` is instance state on that singleton. If two requests
are handled concurrently:

1. Request A calls `generate("What is PVT?")`, sets `_buffer = ""`
2. Request A starts streaming, accumulates "PVT stands for..."
3. Request B calls `generate("What is porosity?")`, sets `_buffer = ""`  ← WIPES A's buffer
4. Request A reads `self._buffer` → gets B's partial response
5. Request B finishes → gets its own response (correct)
6. Request A returns B's response (WRONG)

---

## Phase 3: Hypothesis Generation

```
Hypothesis H1: Race condition on shared LLMClient._buffer
Location: app/llm/llm_client.py:generate()
Evidence for:
  - _buffer is instance state on a module-level singleton
  - Concurrent requests share the same _buffer
  - Symptom is intermittent and worsens under load
  - Restarting "fixes" it because low load = no concurrent requests initially
Evidence against: None
Diagnostic test: Add request IDs to logging, check if overlapping requests correlate with wrong responses
Likelihood: HIGH
```

```
Hypothesis H2: Response caching returning stale entries
Location: unknown — search for @lru_cache or caching decorators
Evidence for: "previous response" could mean cache hit on stale key
Evidence against: Symptom worsens with load (caching would improve with load)
Diagnostic test: Search for caching decorators on the code path
Likelihood: LOW
```

### Diagnostic search for H2

```
repo_search_content(pattern="lru_cache|cache|memoize", path="app/llm/")
→ No matches
```

H2 eliminated. No caching on this code path.

---

## Phase 4: Root Cause Confirmed

**H1: CONFIRMED**

The root cause is a race condition. `LLMClient._buffer` is shared mutable
state on a module-level singleton. Concurrent requests overwrite each other's
buffers.

---

## Phase 5: Root Cause Report

### Root Cause
Module-level `LLMClient` singleton shares `_buffer` across concurrent requests.
When two requests stream simultaneously, the second resets the buffer before
the first finishes reading it.

Location: `app/llm/llm_client.py:generate()`, line 8
Trigger: Two or more concurrent requests to `/chat`

### Evidence Chain
1. Request arrives at `app/api/llm.py:chat()`
2. `chat()` calls `router.route()` → calls `_client.generate(prompt)`
3. `_client` is a module-level singleton (`app/llm/router.py:12`)
4. `generate()` writes to `self._buffer` during streaming
5. Concurrent request calls `generate()` → resets `self._buffer = ""`
6. First request reads the buffer → gets second request's partial response

### Suggested Fix Direction
- **Option A (minimal):** Remove `_buffer` entirely. Build the response
  as a local variable inside `generate()`:
  ```python
  def generate(self, prompt):
      chunks = []
      for chunk in self._stream_response(prompt):
          chunks.append(chunk)
      return "".join(chunks)
  ```
  Local variables are thread-safe. No shared state, no race condition.

- **Option B (structural):** Create a new `LLMClient` per request instead
  of using a singleton. More memory per request but eliminates all shared
  state concerns.

- **Recommended:** Option A. It's a 3-line change that eliminates the
  specific bug. Option B is a larger refactor for a problem that Option A
  already solves.

### Related Concerns
- Check if `LLMClient` has any other mutable instance state that could
  cause similar issues (`self.endpoint` is set once and never changes,
  so it's safe)
- The module-level singleton pattern is risky for any class with mutable
  state. Consider documenting this as a convention: "Module-level
  instances must be stateless or thread-safe."

---

## What Made This Investigation Work

1. **Symptom keywords triggered the right hypotheses.** "Intermittent" +
   "previous response" + "worsens under load" → concurrency/shared state.
   These are diagnostic shortcuts, not guesses.

2. **The code path trace found the problem.** Following the call chain
   from endpoint to `_buffer` revealed shared mutable state in 4 steps.

3. **H2 was eliminated quickly** with a single search. Don't spend time on
   low-likelihood hypotheses — check them fast and move on.

4. **The fix is proportional to the bug.** A race condition in `_buffer`
   doesn't require rewriting the client architecture. Remove the shared
   state, fix the bug.
