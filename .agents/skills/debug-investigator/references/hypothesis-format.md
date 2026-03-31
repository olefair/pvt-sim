# Debug Hypothesis Format

Legacy note: if this reference mentions historical `repo_*` helper names,
treat them as shorthand for local file reads, `rg`, git history, and the
project's real test commands. They are not required tools.

For each potential failure point, form a hypothesis using this template:

```
Hypothesis H[N]: [specific claim about what's wrong]
Location: [file:function:line range]
Evidence for: [what supports this hypothesis]
Evidence against: [what contradicts it]
Diagnostic test: [how to confirm or eliminate this hypothesis]
Likelihood: HIGH / MEDIUM / LOW
```

## Ranking Heuristics (most likely first)

1. **Recent changes** — If `repo_hotspot_history` shows the file changed recently, it's more likely the source. Recent bugs come from recent code.
2. **Missing error handling** — If a function assumes success but doesn't handle the failure case, and the symptom is a crash/unexpected behavior, this is high likelihood.
3. **Type mismatches** — If data crosses a boundary (API to internal, string to number, dict to object) without validation, corruption is likely.
4. **Shared mutable state** — If multiple code paths write to the same state and the bug is intermittent, this is a race condition candidate.
5. **External dependencies** — If the code path calls an external service (API, database, file system) and the bug is intermittent, the external service may be the source.
6. **Configuration** — If the behavior differs between environments or was "working before," check config values and defaults.

## Verdict Classification

After diagnostic narrowing, classify each hypothesis:

- **CONFIRMED**: Found the specific line(s) where the bug lives
- **ELIMINATED**: The code handles this case correctly
- **INCONCLUSIVE**: Need more information (propose a diagnostic edit)
