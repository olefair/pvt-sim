# Code Smell Detection Catalog

Legacy note: if this reference mentions historical `repo_*` helper names,
treat them as shorthand for local file reads, `rg`, git history, and the
project's real test commands. They are not required tools.

| Smell | Detection Signal | Severity |
|-------|-----------------|----------|
| **God File** | > 500 lines + high fan-in + high fan-out | High |
| **Feature Envy** | Function accesses another module's data more than its own | Medium |
| **Duplication** | Similar function signatures/bodies across files | Medium |
| **Shotgun Surgery** | High co-change frequency between files | High |
| **Dead Weight** | Unreferenced symbols from `repo_dead_code` | Low |
| **Leaky Abstraction** | Internal details referenced by many external files | High |
| **Naming Confusion** | Inconsistent naming patterns from convention scan | Low |
| **Circular Dependency** | Mutual imports from dependency graph | High |
| **Config Sprawl** | Multiple config access patterns from convention scan | Medium |
| **Test Desert** | High-coupling file with zero test coverage | High |
