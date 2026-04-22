# Demo Runbook — 2026-04-21

Audience: graduate petroleum engineering professor. ~1 hour prep window.
Surface: `pvtsim-gui` (PySide6 desktop app).
Claude Code edits files directly on disk via Edit/Write — no staging. As of
this runbook's update window, CC has confirmed DL and CVD result surfaces
are fully patched and passing (535 GUI-contract + 82 unit tests). Commit
status is irrelevant for the demo: `pvtsim-gui` reads whatever is on disk at
launch. The only thing that matters is that you restart `pvtsim-gui` once
after any CC edit, since Python doesn't hot-reload.

This runbook is scratch, not canonical. Delete after the demo.

---

## 1. What to demo (safe path)

**Anchor workflow: PT Flash on a known-clean fluid, then Bubble Point, then Phase Envelope.**
These three are the least likely to hit the 9 known pre-existing test failures
and the `pete665_assignment_baseline.md` desktop-path gaps.

Suggested sequence (~15 min, leaves time for questions):

1. **Launch** `pvtsim-gui` from a fresh terminal with `.venv` active.
   - Confirm window opens. If it doesn't, you're on the wrong Python — check
     `.env.defaults` points at `.venv\Scripts\python.exe`.
2. **Load** `examples/pt_flash_config.json`.
   - Narrate: "This is an app-facing config; the runtime converts to canonical
     SI internally." (Backs up the unit discipline story.)
3. **Run PT Flash.** Show phase split, K-values, Z-factors.
4. **Switch to Bubble Point** on the same fluid. Show the saturation pressure
   result. Mention that the solver is protected against poor initial guesses
   (there is an explicit regression test for that).
5. **Switch to Phase Envelope.** Use
   `examples/phase_envelope_config.json` or one of the black-oil / volatile-oil
   continuations. Show the bubble and dew loci.
6. **Switch EOS** between PR76, PR78, and SRK. Re-run the envelope to show the
   runtime EOS surface is live (not just a dropdown).
7. **Excel export** — live on disk and tested. Demo it after the DL run to
   show end-to-end output capture.

**DL results panel (as of CC's latest confirmed state):** five narrow tables
split as GOR / FVF / Oil / Gas / Vapor & Prod. DL text output has the same
5-section split. Demo the panel scroll if the display is tight.

**CVD results panel:** Summary in psia / °F (changed from bar / °C). Text
output is two stacked tables with two-row `[unit]` headers.

**DL plot grid rule:** 1 series → 1×1, 2 → 2×1, 3+ → 2 rows, grows right.

## 2. What NOT to demo live

Do not click these during the live demo — they hit known-failure territory:

- **Dew Point** on an arbitrary fluid — touches "dew characterization" in the 9
  known failures list. If asked, say it works on the kernel path and is being
  hardened for the GUI surface.
- **BIP panel** — the baseline doc flagged this as "diagnostic theater" not
  wired into `RunConfig`. Not re-verified today. Leave it alone until you
  confirm. If the prof opens it, say the runtime default is zero-BIP (which
  is also the assignment baseline), and the explicit BIP wiring is a
  scheduled upgrade.
- **DL or CVD tables without restarting `pvtsim-gui` after a CC edit** — the
  patches are on disk but the running process is stale until restart.

**Gaps that WERE live per the 2026-04-12 baseline doc but are now CLOSED at
the schema level (verified 2026-04-21 read-only against current
`src/pvtapp/schemas.py`):**

- CCE exact 1000/1250/1500 psia schedule — `CCEConfig.pressure_points_pa`
  now accepts an explicit descending pressure list and `n_steps` minimum
  dropped from `5` to `2`.
- DL exact 500/300/100 psia schedule — `DLConfig.pressure_points_pa` accepts
  an explicit descending list below bubble pressure.
- Raw PETE 665 composition (total 1.00001) — `COMPOSITION_SUM_TOLERANCE` is
  `1e-4`, the diff from 1.0 is `1e-5`, so the raw published composition is
  within tolerance and accepted.
- `Bg` in DL output — `DLStepResult.bg` is now a real field. Still
  `Optional[float]`, so check it's populated for the assignment fluid before
  demoing. CC is patching the display surface right now, so the GUI table
  may start rendering it mid-hour.

What this means: the assignment workflow is much closer to demo-ready on the
desktop path than the baseline doc reads. The remaining risk is
**presentation**, not **capability** — whether the GUI table/text output
clearly labels the fields in assignment nomenclature (RsD, RsDb, BtD vs.
rs, rsi, bt). CC is actively closing that surface right now.

## 3. If the professor is from PETE 665

There is a non-zero chance this is a PETE 665 grader / instructor. If so,
they may ask to see the exact assignment case. Honest answer:

> "The assignment reference path lives kernel-side today at
> `src/pvtcore/validation/pete665_assignment.py`, wrapped by
> `scripts/run_pete665_assignment.py`. The desktop runtime is being aligned
> to that reference; as of 2026-04-12 the published composition (sums to
> 1.00001), the exact CCE / DL schedules, and the initials-based temperature
> picker are the documented desktop gaps. The kernel runner hits the
> assignment schedule exactly and produces `Bg`, `Bo`, `RsD`, `RsDb`, `BtD`.
> I can show the kernel run if you want, alongside the desktop parity work
> currently in flight."

If they want it live, run:

```powershell
python scripts/run_pete665_assignment.py --initials TOF
```

Replace `TOF` with the actual initials from the assignment. The supported
initials are in `examples/pete665_assignment_case.json` under
`temperature_by_initials_f` (TLA, TAS, TEM, TJE, TJP, TOF, THI, TGA, TANS).

## 4. Anticipated hard questions and honest answers

**"Which EOS formulations do you support?"**
PR76, PR78, and SRK at runtime (see `src/pvtapp/capabilities.py`). All three
are wired to the desktop GUI — not display-only. Cubic EOS family, standard
α(T) forms, no custom α functions in the runtime today.

**"How is heavy-end characterization handled?"**
Mandatory standard is Whitson lumping for heavy-end, plus delumping on the
kernel side. See `docs/runtime_surface_standard.md` for the full contract.
Characterization methods are a documented runtime-surface mandatory standard,
not an optional knob.

**"How are BIPs handled?"**
Runtime default is zero-BIP unless supplied via config data. The GUI BIP panel
is currently diagnostic and not wired into `RunConfig` — that is an
acknowledged gap and the correct answer is "it's a known gap, not a hidden
default." Do not claim the panel drives behavior.

**"How do you validate?"**
Point to `docs/validation_plan.md` and `src/pvtcore/validation/` — there is a
PETE 665 assignment validation module, plus a published-literature validation
lane. There is a known pre-existing failure in MI PVT bubble point; don't
hide it if asked.

**"Why does the phase envelope not pass through the computed critical point?"**
This is an intentionally parked xfail per the results_view comment. The
current design does not inject the detected critical point into the bubble /
dew curves; redesign is queued post-demo. The right answer is structural, not
numerical — say so.

**"Units?"**
Canonical internal SI (Pa, K, mol) per `docs/units.md`. Unit conversions live
at I/O boundaries only. Display units are psia / °F / bbl in the GUI. The
round-trip conversion was just hardened in commit `35be0cf` — if pressed on
the history, the honest story is "we found and fixed a silent
°F↔K corruption in the conditions widget, so the current round-trip is
auditable."

**"Tests?"**
~1100 headless tests, 9 known pre-existing failures on `main` as of
2026-04-15, all documented in CLAUDE.md. Default `pytest` is ~13 min; phase
envelope tests dominate. If asked for a live run, use a single targeted file,
e.g. `pytest tests/unit/test_flash.py`.

## 5. Pre-flight checklist (do this 10 min before demo)

- [ ] `.venv` activated; `python --version` is 3.10+.
- [ ] `pvtsim-gui` launches to a visible window.
- [ ] Screen resolution tested — DL tables were just split into 3 narrower
      tables to fit; if your demo display is narrow, verify nothing clips.
- [ ] `examples/pt_flash_config.json` loads and runs without error.
- [ ] Phase envelope config of your choice loads and runs.
- [ ] `python scripts/run_pete665_assignment.py --help` prints cleanly, in
      case the fallback path is needed.
- [ ] A terminal window is already open with `.venv` active, so step (§3)
      fallback is one command away.
- [ ] `pvtsim-gui` was restarted AFTER the last CC edit on disk. Commit
      status does not matter; launch-time disk state does.

## 6. Landmine summary (one-liner per risk)

1. **Dew Point** — known-failure surface. Skip unless CC closed it today.
2. **CCE / DL at exact assignment pressures** — GUI can't express the schedule. Kernel script can.
3. **BIP panel** — cosmetic. Do not claim it drives behavior.
4. **Raw PETE 665 composition** — `RunConfig` rejects 1.00001 total.
5. **Phase envelope at critical point** — continuity gap is known, parked.
6. **DL output set** — `Bg` now present in `DLStepResult`, GUI split into 5 narrow
   tables (GOR / FVF / Oil / Gas / Vapor&Prod). Verified on-disk by CC, tested.
   RsDb maps to `DLResult.rsi` (initial Rs at bubble). If the prof uses assignment
   nomenclature (RsD, RsDb, BtD), translate on the fly.
7. **Uncommitted diff ≠ unstable** — CC edits disk directly. Launch-time disk
   state is what runs. If anything looks off mid-demo, close and relaunch
   `pvtsim-gui` from a known config — don't troubleshoot live.

## 7. Sources

- `CLAUDE.md` — repo posture, test state, entrypoints.
- `docs/validation/pete665_assignment_baseline.md` (2026-04-12) — desktop-path gap catalog.
- `src/pvtapp/capabilities.py` — runtime-wired calc types and EOS set.
- `examples/pete665_assignment_case.json` — assignment fluid + schedule.
- `scripts/run_pete665_assignment.py` — kernel fallback path.
- `docs/runtime_surface_standard.md` — runtime-wiring contract (characterization, BIP, lumping).
