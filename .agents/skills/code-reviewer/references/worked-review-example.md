# Worked Code Review Example

Legacy note: if this example mentions historical `repo_*` helper names,
treat them as shorthand for local file reads, `rg`, git history, and the
project's real test commands. They are not required tools.

A complete review walkthrough showing how to move from raw changes to
structured findings. Use this to calibrate review depth and classification.

---

## The Change

A developer added retry logic to an API client. Two files changed:

### `app/api/client.py` — Modified

```python
# BEFORE:
def fetch_completions(self, prompt: str) -> dict:
    response = self.session.post(self.endpoint, json={"prompt": prompt})
    response.raise_for_status()
    return response.json()

# AFTER:
def fetch_completions(self, prompt: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            response = self.session.post(self.endpoint, json={"prompt": prompt})
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
```

### `tests/test_client.py` — Modified

```python
# Added:
def test_fetch_retries_on_failure(client, mock_post):
    mock_post.side_effect = [requests.ConnectionError(), mock_response(200)]
    result = client.fetch_completions("test")
    assert result is not None
    assert mock_post.call_count == 2
```

---

## Review Walkthrough

### Step 1: Understand the intent

The change adds retry-with-backoff to API calls. Reasonable goal — network
calls fail intermittently.

### Step 2: Check conventions

Run `repo_convention_scan`. Suppose it reveals:
- Error handling: the codebase uses `logger.error()` on caught exceptions
- Type hints: consistently used throughout
- Imports: `time` is used elsewhere, `requests` exceptions are imported at top

**Finding:** The new code catches `requests.RequestException` but doesn't log
the failure before retrying. Every other exception handler in the codebase logs.

```
[CONVENTION] client.py:fetch_completions
Retry loop catches RequestException silently. The rest of the codebase logs
errors before retrying (see api/search.py:34, api/embedding.py:52).
Add: logger.warning(f"Attempt {attempt+1} failed: {e}, retrying...")
```

### Step 3: Check for bugs

Read the actual code. Trace the logic:
- `retries=3` means `range(3)` → attempts 0, 1, 2 → 3 total attempts. Correct.
- `if attempt == retries - 1: raise` — on the last attempt, re-raises. Correct.
- `time.sleep(2 ** attempt)` — sleeps 1s, 2s, 4s. But wait — `2 ** 0 = 1`,
  `2 ** 1 = 2`, `2 ** 2 = 4`. The last sleep (4s) happens before the final
  attempt, but we raise on the final attempt's failure. So the 4s sleep happens
  before attempt 2, which is correct. No bug here.

But: what about non-retryable errors? A `requests.HTTPError` from a 400 Bad
Request should NOT be retried — the request is malformed. A 429 or 503 should
be retried. A 401 should not.

```
[BUG] client.py:fetch_completions
Retries all RequestExceptions including non-retryable HTTP errors. A 400 Bad
Request or 401 Unauthorized will be retried 3 times with backoff, wasting
time on requests that will never succeed.

Fix: Only retry on ConnectionError, Timeout, and 5xx/429 status codes.
Raise immediately on 4xx (except 429).

Example:
    RETRYABLE = (requests.ConnectionError, requests.Timeout)
    ...
    except RETRYABLE:
        ...
    except requests.HTTPError as e:
        if e.response.status_code in (429, 502, 503, 504):
            ...  # retry
        raise  # don't retry other HTTP errors
```

### Step 4: Check test coverage

The test covers the happy retry path (one failure then success). Missing:
- What happens when ALL retries fail? Does it raise the original exception?
- Does it handle non-retryable errors correctly? (Currently no, see bug above)
- Is the backoff timing correct? (Could assert `time.sleep` call args)
- What if `retries=0`? (Edge case: should it make one attempt or zero?)

```
[COVERAGE GAP] test_client.py:test_fetch_retries_on_failure
Test only covers the 1-failure-then-success path. Missing tests:
- All retries exhausted → should raise the final exception
- Non-retryable error (400) → should raise immediately (once bug is fixed)
- retries=0 → behavior undefined, should be documented
- Backoff timing → assert time.sleep called with [1, 2] for 2 retries
```

### Step 5: Check impact

Run `repo_impact_graph` with `target_symbols=["fetch_completions"]`.
Suppose it shows 8 callers across 4 files. The function signature changed —
`retries` was added with a default, so existing callers aren't broken. Good.

But: the behavior changed. Previously, a transient network error would raise
immediately. Now it retries with up to 7 seconds of delay (1+2+4). Any caller
with a tight timeout might now hit that timeout during retries.

```
[RISK] client.py:fetch_completions
8 callers depend on this function. The retry loop adds up to 7 seconds of
latency on failure. Callers with their own timeouts (check api/streaming.py
which has a 5-second timeout) may now timeout during the retry backoff
rather than getting a fast failure.

Consider: max_retry_time parameter, or making retries opt-in rather than
default-on for latency-sensitive callers.
```

### Step 6: Assemble the review

```
## Code Review: Add retry logic to API client

### Summary
Adds useful retry-with-backoff to API calls. One bug (retries non-retryable
errors), one risk (adds latency for all callers), and missing test coverage
for failure paths. Solid direction but needs refinement before merging.

### Verdict: REQUEST CHANGES

### Findings (4 total: 1 bug, 1 risk, 1 convention, 1 coverage gap)

[BUG] client.py:fetch_completions — Retries non-retryable HTTP errors (400, 401)
[RISK] client.py:fetch_completions — 7s retry delay may timeout latency-sensitive callers
[CONVENTION] client.py:fetch_completions — Missing logging on retry (pattern used everywhere else)
[COVERAGE GAP] test_client.py — Only tests 1-failure-then-success; missing exhaustion and edge cases

### What's Good
- Clean exponential backoff implementation
- Default retries=3 is sensible
- Existing callers unaffected by signature change (good default usage)
```

---

## Key Calibration Points

**BUG vs RISK:** The non-retryable error issue is a BUG because it will
definitely cause wrong behavior (retrying 400s). The timeout issue is a RISK
because it only matters for specific callers.

**Don't over-count:** This review has 4 findings for ~15 lines of change.
That's appropriate. If you have 15 findings for 15 lines, you're nitpicking.
If you have 0 findings for 100 lines, you're not reading carefully enough.

**Convention findings are lower priority** but still worth noting if the
team enforces consistency. Don't make convention issues the bulk of the review.

**Coverage gaps should be specific.** "Needs more tests" is useless. "Missing:
all-retries-exhausted path, non-retryable error path, backoff timing assertion"
is actionable.
