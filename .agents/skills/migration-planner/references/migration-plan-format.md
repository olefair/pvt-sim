# Migration Plan Output Format

## API Translation Table

| Source | Target | Notes |
|--------|--------|-------|
| old_lib.connect(host, port) | new_lib.create_client(url=f"{host}:{port}") | Args restructured |
| old_lib.Query(sql) | new_lib.execute(sql) | Return type changed: list to iterator |
| old_lib.Config.from_file(path) | new_lib.load_config(path, format="yaml") | Added format param |
| from old_lib import Thing | from new_lib.models import Thing | Moved to submodule |

For each translation note: behavioral differences, return type changes, error handling differences, async/sync changes, and deprecation warnings.

## Touchpoint Classification

| Type | Example | Migration Action |
|------|---------|-----------------|
| Direct import | `from old_lib import X` | Change import |
| Function call | `old_lib.do_thing()` | Change call signature |
| Class usage | `class Foo(old_lib.Base)` | Change base class |
| Type hint | `x: old_lib.Type` | Change type |
| Config reference | `LIBRARY=old_lib` | Change config |
| Mock/test | `@mock.patch('old_lib.X')` | Update mock target |
| String reference | `"powered by old_lib"` | Update string |
| Transitive | Uses module that uses old_lib | May need no change |

## Migration Plan Template

```
## Migration Plan: [source] -> [target]

### Scope
- Files affected: N
- Touchpoints: M (N imports, M calls, K types, ...)
- Estimated steps: S

### API Translation Table
[from analysis]

### Design Decisions Needed
- [situation where no 1:1 mapping exists]

### Migration Steps (in dependency order)

#### Step 1: Add new dependency + config — Risk: LOW
- Add [new_lib] to requirements
- Add new config values with backward-compatible defaults
- Verify: install succeeds, existing tests still pass

#### Step N: Remove old dependency — Risk: LOW
- Remove [old_lib] from requirements
- Search for any remaining references (should be zero)
- Verify: Full test suite passes

### Rollback Plan
- Before-migration snapshot stored
- Each step is independently revertible

### Verification Checklist
- All imports reference new_lib
- All function calls use new API
- All type hints updated
- All mocks/patches updated
- Full test suite passes
- old_lib removed from dependencies
```
