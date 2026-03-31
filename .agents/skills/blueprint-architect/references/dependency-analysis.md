# Dependency & Impact Analysis Protocol

Phase 2: Dependency & Impact Mapping — detailed steps.

---

## Step 1: File-Level Dependency Graph

Build the file-level dependency graph manually by reading imports, exports,
package `__init__` files, registries, startup code, and cross-file references.

**Extract:** High fan-in (many import it) = foundational, wide blast radius; high fan-out (imports many) = integration/orchestrator, fragile; circular dependencies = implementation hazards; unresolved imports = external vs broken.

**Guide:** fan_in > 5 → load-bearing; fan_out > 5 → fragile; both → god file; circular_dependencies non-empty → flag.

## Step 2: Symbol-Level Impact Graph

Build the symbol-level impact picture manually from `rg` callsite searches,
targeted file reads, and registration or dispatch surfaces.

**Extract:** Hub symbols (top of hub_symbols) = "neurons"; orphan symbols = dead-code candidates; use `target_symbols` for impact subgraph when user has a specific area or blueprint references.

**Guide:** total_connections > 10 → linchpin; fan_in > fan_out → stable utility; fan_out > fan_in → orchestrator, fragile.

## Step 3: Coupling & Risk Scores

Estimate coupling and risk manually from fan-in, fan-out, shared utilities,
co-change evidence, and how much hidden wiring each file owns.

**Extract:** risk_score (0–1); god_files; tightly_coupled_clusters (change one → change all); change_propagation (blast radius); instability (0 = stable, 1 = unstable). Focus risk_score > 0.3.

**Blueprint use:** High-risk files → own milestone; cluster files → same milestone; propagation → milestone must verify affected files.

## Step 4: Git Hotspot History

Use `git log --stat`, `git log --name-only`, recent diffs, or file timestamps
to identify hotspots and co-change patterns.

**Extract:** High-frequency files; co_change_pairs (change together = hidden coupling). Cross-reference: high-coupling + high-churn = most dangerous; flag.

## Step 5: Dead Code

Search for dead-code candidates by checking callsites, imports, registrations,
plugin hooks, and tests before recommending removal.

**Extract:** Unreferenced symbols. If > 10% of symbols, suggest cleanup before new features. Verify entry points / test helpers / plugin hooks before recommending removal.

---

## Risk Map Summary

After all steps, produce:

```
Risk Map:
CRITICAL (risk > 0.5, high churn): [file]: risk=X, churn=Y — [reason]
HIGH (risk > 0.3 OR high churn): [file]: risk=X — [reason]
MODERATE: [file] — [reason]
Hub Symbols: [symbol] in [file]: fan_in=X, fan_out=Y — [role]
Tightly-Coupled Clusters: [file_a, file_b, file_c]
Dead Code: [count] unreferenced in [count] files
```

Use for milestone ordering: high-risk → own milestone; clusters → same milestone; low-risk independent → parallelize.
