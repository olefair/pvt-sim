# Code Review Severity Levels

| Level | Meaning | Action |
|-------|---------|--------|
| **BUG** | This is wrong and will cause incorrect behavior | Must fix |
| **RISK** | This could fail under certain conditions | Should fix or add handling |
| **CONVENTION** | Doesn't match repo patterns | Should fix for consistency |
| **COVERAGE GAP** | Changed code has no tests | Should add tests |
| **QUESTION** | Reviewer doesn't understand the intent | Author should clarify |
| **SUGGESTION** | Could be better but isn't wrong | Nice to have |

Order callouts by severity (BUG first, SUGGESTION last).
