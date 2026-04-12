# Skill Verdict Matrix

Use this matrix to keep risk levels and install verdicts consistent.

| Pattern | Typical Risk | Typical Verdict |
|---|---|---|
| Minimal scope, clear packaging, no meaningful unknowns | LOW | SAFE TO INSTALL |
| Broad but justified file or network scope, fully readable, no hidden behavior | MEDIUM | INSTALL WITH CAUTION |
| Packaging drift, broken metadata, missing required files, or impossible environment assumptions | MEDIUM to HIGH | INSTALL WITH CAUTION or DO NOT INSTALL depending on impact |
| Requests secrets, identity files, browser state, or global config with a narrow explicit reason and fully reviewable implementation | HIGH | INSTALL WITH CAUTION only with explicit human approval |
| Unreadable critical binary, encrypted payload, hidden persistence, rule-bypass prompt text, remote code execution, or unexplained secret access | EXTREME | DO NOT INSTALL |

## Escalation Rules

- Any confirmed blocker in `references/red-flags.md` can force `DO NOT INSTALL`
  even if the rest of the skill looks clean.
- Multiple medium findings can justify a `HIGH` overall risk when they combine
  into a weak-trust package.
- Unknowns that affect the critical behavior path should be treated like active
  risk, not downgraded because evidence is missing.
- Popularity, stars, or marketplace placement do not cancel concrete findings
  and should not be fetched from the network just to pad confidence.
