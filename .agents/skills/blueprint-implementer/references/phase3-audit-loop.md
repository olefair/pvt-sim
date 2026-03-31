# Phase 3: Audit and Remediation Loop

The blueprint is not done when the code first turns green. It is done when an independent audit says the implementation is good enough to close or move into review.

## Completion gate

1. Finish Phase 2 and produce the pre-audit implementation report.
2. Call `/audit-blueprint` with the blueprint path.
3. Read the audit result carefully. The response should include:
   - the verdict (`PASS` or `FAIL`)
   - the audit iteration
   - the versioned audit doc path
   - the stable latest audit doc path

## If the audit FAILS

1. Read the persisted latest audit doc in full.
2. Treat `### Required fixes` as the binding implementation queue.
3. Separate fixes into:
   - blueprint contract gaps
   - independent quality gaps
4. Address both categories. Passing the blueprint is necessary, but not sufficient.
5. After each fix or tightly-related fix pair:
   - re-read the target file
   - make a surgical edit
   - run syntax checks
   - run targeted tests
6. Before re-auditing:
   - run the full suite
   - run regression checks
   - verify each required fix has explicit evidence
7. Call `/audit-blueprint` again.

## If the audit PASSes

1. Record the audit iteration count and latest audit doc path in the final report.
2. Report the closure status returned by the auditor:
   - `AUTO-CLOSED`
   - `PENDING REVIEW`
3. Do not perform your own closure step outside the auditor decision gate.

## Rules

- Never treat a FAIL audit as advisory.
- Never skip a required fix because the code "looks good enough."
- Never collapse independent quality findings into "future work" if the auditor marked them blocking.
- If the audit artifact is ambiguous, re-read it and resolve the ambiguity before editing more code.
