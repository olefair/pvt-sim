"""Validation of dew-point behavior through the plus-fraction path.

These tests start from realistic laboratory-style gas feeds with resolved light
ends (`C1`-`C6`) plus an aggregate `C7+` fraction. They exercise:

- plus-fraction splitting into SCNs
- contiguous lumping of the SCN tail
- feed-side delumping reconstruction
- dew-point calculations on the characterized lumped fluids using runtime-
  supported characterization knobs

The explicit-component source feeds are already covered by the equation-based
dew benchmarks. This file checks that the lab-style `C1`-`C6` + `C7+` workflow
preserves those dew boundaries closely enough for end-to-end use.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

import numpy as np
import pytest

from pvtcore.characterization import (
    CharacterizationConfig,
    PlusFractionSpec,
    characterize_fluid,
)
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.flash.dew_point import calculate_dew_point
from pvtcore.models.component import load_components


_CARBON_NUMBER_RE = re.compile(r"C(\d+)$", re.IGNORECASE)


@dataclass(frozen=True)
class PlusFractionDewCase:
    """Single plus-fraction dew-point validation case."""

    case_id: str
    temperature_k: float
    explicit_components: tuple[tuple[str, float], ...]
    z_plus: float
    mw_plus_g_per_mol: float
    sg_plus_60f: float
    split_mw_model: str
    max_carbon_number: int
    lumping_n_groups: int
    lumped_pressure_pa: float
    explicit_pressure_rtol: float = 0.04
    guess_pressures_pa: tuple[float | None, ...] = (None, 1e5, 1e6, 5e7)
    pressure_atol_pa: float = 25.0
    shared_composition_atol: float = 5.0e-4
    heavy_total_atol: float = 2.0e-3


PLUS_FRACTION_DEW_CASES = [
    PlusFractionDewCase(
        case_id="plus_dry_gas_a_characterized_dew",
        temperature_k=260.0,
        explicit_components=(
            ("N2", 0.0100),
            ("CO2", 0.0150),
            ("C1", 0.8200),
            ("C2", 0.0700),
            ("C3", 0.0350),
            ("iC4", 0.0120),
            ("C4", 0.0100),
            ("iC5", 0.0080),
            ("C5", 0.0070),
            ("C6", 0.0050),
            ("C7", 0.0030),
            ("C8", 0.0030),
            ("C10", 0.0020),
        ),
        z_plus=0.0080,
        mw_plus_g_per_mol=115.981825,
        sg_plus_60f=0.744625,
        split_mw_model="table",
        max_carbon_number=11,
        lumping_n_groups=4,
        lumped_pressure_pa=4605.880269087789,
    ),
    PlusFractionDewCase(
        case_id="plus_dry_gas_b_characterized_dew",
        temperature_k=280.0,
        explicit_components=(
            ("N2", 0.0120),
            ("CO2", 0.0450),
            ("H2S", 0.0030),
            ("C1", 0.7600),
            ("C2", 0.0800),
            ("C3", 0.0450),
            ("iC4", 0.0120),
            ("C4", 0.0120),
            ("iC5", 0.0080),
            ("C5", 0.0070),
            ("C6", 0.0060),
            ("C7", 0.0040),
            ("C8", 0.0030),
            ("C10", 0.0030),
        ),
        z_plus=0.0100,
        mw_plus_g_per_mol=117.03382,
        sg_plus_60f=0.7457,
        split_mw_model="table",
        max_carbon_number=11,
        lumping_n_groups=4,
        lumped_pressure_pa=17075.459066801785,
    ),
    PlusFractionDewCase(
        case_id="plus_gas_condensate_a_characterized_dew",
        temperature_k=320.0,
        explicit_components=(
            ("N2", 0.0060),
            ("CO2", 0.0250),
            ("C1", 0.6400),
            ("C2", 0.1100),
            ("C3", 0.0750),
            ("iC4", 0.0250),
            ("C4", 0.0250),
            ("iC5", 0.0180),
            ("C5", 0.0160),
            ("C6", 0.0140),
            ("C7", 0.0140),
            ("C8", 0.0120),
            ("C10", 0.0100),
            ("C12", 0.0100),
        ),
        z_plus=0.0460,
        mw_plus_g_per_mol=128.25512173913043,
        sg_plus_60f=0.7571304347826087,
        split_mw_model="paraffin",
        max_carbon_number=18,
        lumping_n_groups=2,
        lumped_pressure_pa=3906.418983182879,
        explicit_pressure_rtol=0.01,
    ),
    PlusFractionDewCase(
        case_id="plus_gas_condensate_b_characterized_dew",
        temperature_k=330.0,
        explicit_components=(
            ("N2", 0.0040),
            ("CO2", 0.0180),
            ("H2S", 0.0080),
            ("C1", 0.5800),
            ("C2", 0.1200),
            ("C3", 0.0850),
            ("iC4", 0.0300),
            ("C4", 0.0280),
            ("iC5", 0.0200),
            ("C5", 0.0190),
            ("C6", 0.0180),
            ("C7", 0.0180),
            ("C8", 0.0170),
            ("C10", 0.0200),
            ("C12", 0.0150),
        ),
        z_plus=0.0700,
        mw_plus_g_per_mol=130.65968142857142,
        sg_plus_60f=0.7603,
        split_mw_model="table",
        max_carbon_number=17,
        lumping_n_groups=2,
        lumped_pressure_pa=5151.61181587608,
        explicit_pressure_rtol=0.02,
    ),
    PlusFractionDewCase(
        case_id="plus_co2_rich_gas_a_characterized_dew",
        temperature_k=290.0,
        explicit_components=(
            ("N2", 0.0080),
            ("CO2", 0.4600),
            ("H2S", 0.0100),
            ("C1", 0.2900),
            ("C2", 0.0700),
            ("C3", 0.0450),
            ("iC4", 0.0200),
            ("C4", 0.0180),
            ("iC5", 0.0120),
            ("C5", 0.0120),
            ("C6", 0.0110),
            ("C7", 0.0100),
            ("C8", 0.0080),
            ("C10", 0.0060),
        ),
        z_plus=0.024489795918367346,
        mw_plus_g_per_mol=115.39738333333332,
        sg_plus_60f=0.7436666666666666,
        split_mw_model="paraffin",
        max_carbon_number=11,
        lumping_n_groups=4,
        lumped_pressure_pa=16367.293851523895,
        explicit_pressure_rtol=0.02,
    ),
    PlusFractionDewCase(
        case_id="plus_co2_rich_gas_b_characterized_dew",
        temperature_k=300.0,
        explicit_components=(
            ("N2", 0.0100),
            ("CO2", 0.3600),
            ("H2S", 0.0300),
            ("C1", 0.3700),
            ("C2", 0.0800),
            ("C3", 0.0550),
            ("iC4", 0.0200),
            ("C4", 0.0200),
            ("iC5", 0.0130),
            ("C5", 0.0130),
            ("C6", 0.0110),
            ("C7", 0.0090),
            ("C8", 0.0060),
            ("C10", 0.0030),
        ),
        z_plus=0.0180,
        mw_plus_g_per_mol=111.89073333333334,
        sg_plus_60f=0.7390,
        split_mw_model="paraffin",
        max_carbon_number=11,
        lumping_n_groups=3,
        lumped_pressure_pa=56668.87532360497,
        explicit_pressure_rtol=0.02,
    ),
]


def _carbon_number_from_id(component_id: str) -> int | None:
    match = _CARBON_NUMBER_RE.search(component_id)
    if not match:
        return None
    return int(match.group(1))


def _normalize_explicit_case(
    case: PlusFractionDewCase,
) -> tuple[list[str], list, np.ndarray, list[tuple[str, float]], PlusFractionSpec]:
    """Normalize an explicit feed and derive the corresponding plus-fraction input."""
    components_db = load_components()
    total = float(sum(z for _, z in case.explicit_components))
    normalized = [(component_id, z / total) for component_id, z in case.explicit_components]

    component_ids = [component_id for component_id, _ in normalized]
    components = [components_db[component_id] for component_id in component_ids]
    feed = np.asarray([z for _, z in normalized], dtype=float)

    resolved = [
        (component_id, z)
        for component_id, z in normalized
        if (_carbon_number_from_id(component_id) or 0) < 7
    ]
    plus = PlusFractionSpec(
        z_plus=case.z_plus,
        mw_plus=case.mw_plus_g_per_mol,
        sg_plus=case.sg_plus_60f,
        label="C7+",
        n_start=7,
    )
    return component_ids, components, feed, resolved, plus


def _characterize_case(case: PlusFractionDewCase):
    """Characterize a dew-point case through the runtime-supported path."""
    _, _, _, resolved, plus = _normalize_explicit_case(case)
    config = CharacterizationConfig(
        n_end=case.max_carbon_number,
        split_mw_model=case.split_mw_model,
        correlation="riazi_daubert",
        lumping_enabled=True,
        lumping_n_groups=case.lumping_n_groups,
    )
    return characterize_fluid(resolved, plus_fraction=plus, config=config), resolved, plus


@pytest.mark.parametrize("case", PLUS_FRACTION_DEW_CASES, ids=lambda case: case.case_id)
def test_plus_fraction_dew_lumped_path_preserves_balances_and_pressure(case: PlusFractionDewCase) -> None:
    """Split/lump/delump should preserve dew pressure and incipient liquid behavior."""
    explicit_ids, explicit_components, explicit_feed, resolved, plus = _normalize_explicit_case(case)
    explicit_result = calculate_dew_point(
        case.temperature_k,
        explicit_feed,
        explicit_components,
        PengRobinsonEOS(explicit_components),
        post_check_stability_flip=True,
    )

    characterized_lumped, _, _ = _characterize_case(case)

    assert characterized_lumped.split_result is not None
    assert characterized_lumped.lumping is not None
    assert len(characterized_lumped.component_ids) == len(resolved) + case.lumping_n_groups

    heavy_offset = len(resolved)
    assert float(characterized_lumped.composition[heavy_offset:].sum()) == pytest.approx(plus.z_plus, abs=1e-12)
    assert float(characterized_lumped.split_result.z.sum()) == pytest.approx(plus.z_plus, abs=1e-12)

    delumped_feed = characterized_lumped.lumping.delump_scn(characterized_lumped.lumping.lump_z)
    np.testing.assert_allclose(
        delumped_feed,
        characterized_lumped.lumping.scn_z,
        atol=1e-14,
        rtol=0.0,
    )

    shared_count = len(resolved)
    solved_pressures: list[float] = []

    for guess in case.guess_pressures_pa:
        lumped_result = calculate_dew_point(
            case.temperature_k,
            np.asarray(characterized_lumped.composition, dtype=float),
            characterized_lumped.components,
            PengRobinsonEOS(characterized_lumped.components),
            pressure_initial=guess,
            post_check_stability_flip=True,
        )

        solved_pressures.append(float(lumped_result.pressure))

        assert lumped_result.converged
        assert float(lumped_result.pressure) == pytest.approx(case.lumped_pressure_pa, abs=case.pressure_atol_pa)
        assert float(lumped_result.pressure) == pytest.approx(
            float(explicit_result.pressure),
            rel=case.explicit_pressure_rtol,
        )

        np.testing.assert_allclose(
            lumped_result.liquid_composition[:shared_count],
            explicit_result.liquid_composition[:shared_count],
            atol=case.shared_composition_atol,
            rtol=0.0,
        )

        lumped_heavy_total = float(np.sum(lumped_result.liquid_composition[shared_count:]))
        explicit_heavy_total = float(np.sum(explicit_result.liquid_composition[shared_count:]))
        assert lumped_heavy_total == pytest.approx(explicit_heavy_total, abs=case.heavy_total_atol)

    for pressure_pa in solved_pressures[1:]:
        assert pressure_pa == pytest.approx(solved_pressures[0], abs=1e-3)
