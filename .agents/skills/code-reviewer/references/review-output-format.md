# Code Review Output Format

```
## Code Review

### Summary
[2-3 sentences: overall quality assessment, biggest concern, overall verdict]

### Verdict: APPROVE / APPROVE WITH COMMENTS / REQUEST CHANGES
[APPROVE: No bugs, minor suggestions only]
[APPROVE WITH COMMENTS: No bugs, but convention/coverage gaps worth fixing]
[REQUEST CHANGES: Bugs found, or significant risks without test coverage]

### Stats
- Files reviewed: N
- Lines changed: ~M (estimated from symbol diffs)
- New functions: X | Modified: Y | Removed: Z
- Test coverage of changes: A%
- Health impact: [HEALTHIER / NEUTRAL / CONCERNING / DEGRADED]

### Findings (N total: X bugs, Y risks, Z conventions, ...)

#### Bugs
[BUG] file.py:function_name
[description + suggestion]

#### Risks
[RISK] file.py:function_name
[description + suggestion]

#### Convention Issues
[CONVENTION] file.py:function_name
[description + suggestion]

#### Coverage Gaps
[COVERAGE GAP] file.py:function_name
[description + suggestion]

#### Questions
[QUESTION] file.py:function_name
[what the reviewer doesn't understand]

#### Suggestions
[SUGGESTION] file.py:function_name
[description + suggestion]

### What's Good
[Explicitly call out things done well — good error handling, clean
abstractions, thorough tests. Reviews shouldn't be all negative.]
```
