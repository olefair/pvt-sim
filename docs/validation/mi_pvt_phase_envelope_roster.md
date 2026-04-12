# MI PVT Phase-Envelope Roster

This document is the recommended MI PVT case roster for validating the phase
envelope module across the fluid families a practical PVT simulator should be
expected to handle.

Use this when generating MI PVT reference envelopes for the repo validation
surface.

## Assumptions

Unless a case note says otherwise, use:

- EOS: `Peng-Robinson`
- BIPs: `zero`
- no tuning
- no volume shift

For MI PVT labels, use:

- `C4` in repo feeds as `nC4`
- `C5` in repo feeds as `nC5`
- `iC4` and `iC5` as-is

## Important MI PVT Boundary

The MI PVT demo surface shown in the course screenshots does **not** expose the
full repo component vocabulary. In practice, the MI feed surface is limited to:

- `CO2`
- `C1` through `C6`
- lumped heavy bins:
  - `C7-C12`
  - `C13-C18`
  - `C19-C26`
  - `C27-C37`
  - `C38-C85`

That means MI PVT cannot be the cross-check for:

- `N2`
- `H2S`
- explicit isomers such as `iC4` and `iC5`
- arbitrary explicit SCNs like `C7`, `C8`, `C10`, `C12`, `C14`, `C16`
- inline pseudo-components such as the PETE 665 assignment `PSEUDO+`

So the correct approach is:

- use MI PVT only for an **MI-compatible proxy subset**
- keep the broader repo validation surface for full-component and sour-fluid
  coverage outside MI PVT

Current runtime reality:

- MI capture can include MI-native heavy-bin cases exactly as entered in MI PVT
- the current automated repo harness can only execute the subset that has an
  honest runtime representation today
- heavy-bin MI captures should still be collected now, but some of them will
  remain archived-only until the runtime feed surface can represent them

## Actual MI-Compatible Run List

If you are generating MI PVT envelopes manually, use these cases. They are the
correct MI-facing capture surface.

Important:

- `MI-1`, `MI-9`, and `MI-10` are directly executable against the current repo
  runtime without inventing new heavy-end mappings.
- the heavier MI-native cases should still be captured now, but they are
  expected to be archived-only in the pytest harness until the repo can
  represent the same feed surface honestly.

### MI-1. Default CO2-rich regression gas

```text
CO2      0.649800
C1       0.105700
C2       0.105800
C3       0.123500
nC4      0.015200
```

### MI-2. Dry gas proxy

Derived from the repo dry-gas benchmark after removing unsupported components
and renormalizing to the MI surface.

```text
CO2      0.015152
C1       0.828283
C2       0.070707
C3       0.035354
nC4      0.022222
nC5      0.015152
C6       0.005051
C7-C12   0.008081
```

### MI-3. Gas condensate proxy

```text
CO2      0.025151
C1       0.643863
C2       0.110664
C3       0.075453
nC4      0.050302
nC5      0.034205
C6       0.014085
C7-C12   0.046278
```

### MI-4. CO2-rich gas proxy

```text
CO2      0.478170
C1       0.301455
C2       0.072765
C3       0.046778
nC4      0.039501
nC5      0.024948
C6       0.011435
C7-C12   0.024948
```

### MI-5. Volatile oil proxy

```text
CO2      0.018739
C1       0.348532
C2       0.071350
C3       0.093597
nC4      0.073454
nC5      0.069546
C6       0.057521
C7-C12   0.267261
```

### MI-6. Black oil proxy

```text
CO2      0.010050
C1       0.180905
C2       0.055276
C3       0.070352
nC4      0.090452
nC5      0.092462
C6       0.070352
C7-C12   0.363819
C13-C18  0.066332
```

### MI-7. Heavy black-oil proxy

```text
CO2      0.008008
C1       0.140140
C2       0.045045
C3       0.060060
nC4      0.083083
nC5      0.090090
C6       0.070070
C7-C12   0.390390
C13-C18  0.113113
```

### MI-8. MI-native heavy oil from the course screenshot

This is already expressed in MI-native bins and does not need remapping.

```text
CO2      0.062000
C1       0.342700
C2       0.052100
C3       0.036900
nC4      0.025700
nC5      0.018800
C6       0.045500
C7-C12   0.165600
C13-C18  0.100300
C19-C26  0.074600
C27-C37  0.046500
C38-C85  0.029300
```

### MI-9. Ethane / propane control

```text
C2       0.500000
C3       0.500000
```

### MI-10. CO2 / propane control

```text
CO2      0.663000
C3       0.337000
```

## How To Use This Roster

Run all Tier 1 and Tier 2 cases.

- Tier 1 covers realistic field-fluid families
- Tier 2 covers continuation/topology control mixtures that are not always
  field-realistic but are required to catch branch-tracking failures
- Tier 3 covers lab-style `C7+` entry surfaces, which are common in practice

If we get good continuation envelopes on all Tier 1 and Tier 2 cases, we will
have broad confidence in the tracer itself. Tier 3 then checks that this still
holds when the user enters a realistic plus-fraction style fluid rather than a
fully resolved heavy-end composition.

## Tier 1: Practical Field-Fluid Coverage

### 1. Default desktop CO2-rich regression gas

Why this case matters:

- this is the current desktop regression fluid that exposed the bad envelope
  topology and flat-tail behavior
- it must remain in the MI PVT roster even though it is simpler than a full
  field fluid

```text
CO2   0.6498
C1    0.1057
C2    0.1058
C3    0.1235
nC4   0.0152
```

### 2. Dry gas A

Why this case matters:

- lean sweet gas
- checks the low-heavy, dew-dominated end of the practical space

```text
N2    0.0100
CO2   0.0150
C1    0.8200
C2    0.0700
C3    0.0350
iC4   0.0120
nC4   0.0100
iC5   0.0080
nC5   0.0070
C6    0.0050
C7    0.0030
C8    0.0030
C10   0.0020
```

### 3. Dry gas B with acid gas

Why this case matters:

- same basic regime as Dry gas A
- adds acid-gas sensitivity without becoming CO2-dominant

```text
N2    0.0120
CO2   0.0450
H2S   0.0030
C1    0.7600
C2    0.0800
C3    0.0450
iC4   0.0120
nC4   0.0120
iC5   0.0080
nC5   0.0070
C6    0.0060
C7    0.0040
C8    0.0030
C10   0.0030
```

### 4. Gas condensate A

Why this case matters:

- realistic sweet gas-condensate envelope
- checks a broader two-phase region and heavier tail than dry gas

```text
N2    0.0060
CO2   0.0250
C1    0.6400
C2    0.1100
C3    0.0750
iC4   0.0250
nC4   0.0250
iC5   0.0180
nC5   0.0160
C6    0.0140
C7    0.0140
C8    0.0120
C10   0.0100
C12   0.0100
```

### 5. Gas condensate B, sour

Why this case matters:

- sour condensate
- adds H2S and slightly heavier mid-range loading

```text
N2    0.0040
CO2   0.0180
H2S   0.0080
C1    0.5800
C2    0.1200
C3    0.0850
iC4   0.0300
nC4   0.0280
iC5   0.0200
nC5   0.0190
C6    0.0180
C7    0.0180
C8    0.0170
C10   0.0200
C12   0.0150
```

### 6. CO2-rich gas A

Why this case matters:

- CO2-rich injection-style gas
- still has meaningful hydrocarbon tail

```text
N2    0.0080
CO2   0.4600
H2S   0.0100
C1    0.2900
C2    0.0700
C3    0.0450
iC4   0.0200
nC4   0.0180
iC5   0.0120
nC5   0.0120
C6    0.0110
C7    0.0100
C8    0.0080
C10   0.0060
```

### 7. CO2-rich gas B, higher acid-gas loading

Why this case matters:

- stronger CO2/H2S stress case
- checks whether the envelope remains stable in acid-gas-heavy mixtures

```text
N2    0.0100
CO2   0.3600
H2S   0.0300
C1    0.3700
C2    0.0800
C3    0.0550
iC4   0.0200
nC4   0.0200
iC5   0.0130
nC5   0.0130
C6    0.0110
C7    0.0090
C8    0.0060
C10   0.0030
```

### 8. Volatile oil A

Why this case matters:

- classic volatile-oil envelope
- stronger bubble-side behavior and heavier liquid branch

```text
N2    0.0021
CO2   0.0187
C1    0.3478
C2    0.0712
C3    0.0934
iC4   0.0302
nC4   0.0431
iC5   0.0276
nC5   0.0418
C6    0.0574
C7    0.0835
C8    0.0886
C10   0.0946
```

### 9. Volatile oil B

Why this case matters:

- slightly heavier volatile oil
- increases upper-liquid-branch difficulty

```text
N2    0.0015
CO2   0.0150
C1    0.2900
C2    0.0800
C3    0.0950
iC4   0.0340
nC4   0.0460
iC5   0.0320
nC5   0.0460
C6    0.0650
C7    0.0940
C8    0.0920
C10   0.0650
C12   0.0450
```

### 10. Black oil A

Why this case matters:

- practical black-oil regime
- significantly heavier than volatile oils

```text
N2    0.0010
CO2   0.0100
H2S   0.0040
C1    0.1800
C2    0.0550
C3    0.0700
iC4   0.0400
nC4   0.0500
iC5   0.0420
nC5   0.0500
C6    0.0700
C7    0.0950
C8    0.1020
C10   0.0850
C12   0.0800
C14   0.0660
```

### 11. Black oil B

Why this case matters:

- heavier black oil with broader SCN tail
- useful for testing upper envelope closure in heavier systems

```text
N2    0.0010
CO2   0.0080
H2S   0.0060
C1    0.1400
C2    0.0450
C3    0.0600
iC4   0.0380
nC4   0.0450
iC5   0.0420
nC5   0.0480
C6    0.0700
C7    0.0950
C8    0.1050
C10   0.1000
C12   0.0900
C14   0.0700
C16   0.0430
```

### 12. Sour oil A

Why this case matters:

- high-acid-gas oil
- must be covered if the simulator is expected to handle sour fluids

```text
N2    0.0010
CO2   0.0500
H2S   0.0700
C1    0.2200
C2    0.0600
C3    0.0700
iC4   0.0300
nC4   0.0400
iC5   0.0300
nC5   0.0400
C6    0.0600
C7    0.0850
C8    0.0900
C10   0.0800
C12   0.0650
C14   0.0500
C16   0.0290
```

### 13. Sour oil B

Why this case matters:

- even stronger H2S stress
- catches sour-oil branch distortions that sweeter oils do not show

```text
N2    0.0010
CO2   0.0350
H2S   0.0900
C1    0.1800
C2    0.0550
C3    0.0650
iC4   0.0300
nC4   0.0400
iC5   0.0300
nC5   0.0400
C6    0.0650
C7    0.0900
C8    0.0950
C10   0.0850
C12   0.0700
C14   0.0550
C16   0.0390
```

## Tier 2: Continuation / Topology Control Cases

These are not meant to represent the full practical fluid space by themselves.
They exist because a continuation tracer can look acceptable on field fluids
while still failing branch identity, critical switching, or near-trivial root
tracking.

### 14. Ethane / propane equal molar

Why this case matters:

- similar-component binary
- useful for validating clean bubble-to-dew switching near a compact critical
  region

```text
C2    0.5000
C3    0.5000
```

### 15. Methane / n-decane equal molar

Why this case matters:

- strongly asymmetric binary
- useful for validating local branch-family tracking without branch teleporting

```text
C1    0.5000
C10   0.5000
```

### 16. Simple dry-gas control

Why this case matters:

- minimal light-gas sanity check
- useful when you want a quick MI PVT run before committing to the full field
  roster

```text
C1    0.9000
C2    0.0500
C3    0.0500
```

### 17. CO2 / propane binary control

Why this case matters:

- simpler acid-gas control than the multicomponent CO2-rich cases
- helps separate continuation failure from multicomponent heavy-tail effects

```text
CO2   0.6630
C3    0.3370
```

## Tier 3: Practical `C7+` Entry Surfaces

These should also be run if the goal is to validate what a user is reasonably
likely to enter into a PVT simulator rather than just EOS-ready SCN feeds.

### 18. Volatile oil with `C7+`

```text
Resolved components
N2    0.0021
CO2   0.0187
C1    0.3478
C2    0.0712
C3    0.0934
iC4   0.0302
nC4   0.0431
iC5   0.0276
nC5   0.0418
C6    0.0574

Plus fraction
C7+   z = 0.2667
      MW = 119.78759868766404 g/mol
      SG = 0.82
```

### 19. Black oil with `C7+`

```text
Resolved components
N2    0.0010
CO2   0.0100
H2S   0.0040
C1    0.1800
C2    0.0550
C3    0.0700
iC4   0.0400
nC4   0.0500
iC5   0.0420
nC5   0.0500
C6    0.0700

Plus fraction
C7+   z = 0.4280
      MW = 140.1515261682243 g/mol
      SG = 0.85
```

### 20. Gas condensate with `C7+`

```text
Resolved components
N2    0.0060
CO2   0.0250
C1    0.6400
C2    0.1100
C3    0.0750
iC4   0.0250
nC4   0.0250
iC5   0.0180
nC5   0.0160
C6    0.0140

Plus fraction
C7+   z = 0.0460
      MW = 128.25512173913043 g/mol
      SG = 0.7571304347826087
```

### 21. CO2-rich gas with `C7+`

```text
Resolved components
N2    0.0080
CO2   0.4600
H2S   0.0100
C1    0.2900
C2    0.0700
C3    0.0450
iC4   0.0200
nC4   0.0180
iC5   0.0120
nC5   0.0120
C6    0.0110

Plus fraction
C7+   z = 0.024489795918367346
      MW = 115.39738333333332 g/mol
      SG = 0.7436666666666666
```

## Tier 4: Course-Specific Optional Case

### 22. PETE 665 assignment baseline

Why this case matters:

- keeps the course project surface tied to the same envelope validation effort
- not broad enough to substitute for the full roster above

```text
C1         0.19962
C2         0.10010
C3         0.18579
nC4        0.09036
nC5        0.18851
PSEUDO+    0.23563

PSEUDO+ properties
MW         86.177 g/mol
Tc         453.65 F
Pc         436.293 psia
omega      0.296
```

## Recommended Minimum Run Order

If you want the smallest run set that still gives broad confidence, do these
first:

1. Default desktop CO2-rich regression gas
2. Dry gas A
3. Gas condensate A
4. CO2-rich gas A
5. Volatile oil A
6. Black oil A
7. Sour oil A
8. Ethane / propane equal molar
9. Methane / n-decane equal molar
10. One `C7+` case, preferably Volatile oil with `C7+`

If all of those look good, then expand to the full roster.

## Source Surface In This Repo

This roster is assembled directly from the current repo validation feeds:

- `tests/validation/test_phase_envelope_runtime_matrix.py`
- `tests/validation/test_saturation_equation_benchmarks.py`
- `tests/validation/test_plus_fraction_bubble_characterization.py`
- `tests/validation/test_plus_fraction_dew_characterization.py`
- `tests/fixtures/fluids/co2_rich_gas.json`
- `examples/pete665_assignment_case.json`
