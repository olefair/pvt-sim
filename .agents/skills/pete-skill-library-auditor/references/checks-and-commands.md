# Pete Skill Library Auditor Checks

Use this note to remember what the repo-local wrappers already cover.

## Full library wrapper

```powershell
python C:\Users\olefa\dev\pete-workspace\tools\scripts\run_pete_skill_library_audit.py
```

This wrapper aggregates:

- `validate_skills.py`
- folder/package inventory parity checks
- `audit_skill_package.py` on every folder/package pair
- `run_skill_vetter_regression.py` unless skipped
- Python unit tests under `tools/scripts/tests`
- the Node hook-guard test when Node is present

## Single skill wrapper

```powershell
python C:\Users\olefa\dev\pete-workspace\tools\scripts\audit_skill_package.py --skill-dir C:\Users\olefa\dev\pete-workspace\tools\SKILLS\folders\<skill-name> --archive C:\Users\olefa\dev\pete-workspace\tools\SKILLS\packages\<skill-name>.skill
```

Use this when the user wants one skill audited rather than the whole library.

## Interpretation rules

- `CLEAN` means no actionable findings.
- `ACTIONABLE` means at least one error or warning needs attention.
- Command-check failures are part of the audit result, not noise.
