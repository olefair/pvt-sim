"""Validation of bubble-point behavior through the plus-fraction path.

These tests start from realistic laboratory-style feeds with resolved light ends
(`C1`-`C6`) plus an aggregate `C7+` fraction. They exercise:

- plus-fraction splitting into SCNs
- contiguous lumping of the SCN tail
- feed-side delumping reconstruction
- bubble-point calculations on both full and lumped characterized fluids

This complements the equation-based saturation benchmarks, which validate the
solver against independent equilibrium equations on already EOS-ready fluids.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from pvtcore.characterization import (
    CharacterizationConfig,
    PlusFractionSpec,
    characterize_fluid,
)
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.flash.bubble_point import calculate_bubble_point


@dataclass(frozen=True)
class PlusFractionBubbleCase:
    """Single plus-fraction bubble-point validation case."""

    case_id: str
    temperature_k: float
    resolved_components: tuple[tuple[str, float], ...]
    z_plus: float
    mw_plus_g_per_mol: float
    sg_plus_60f: float
    max_carbon_number: int = 20
    lumping_n_groups: int = 6
    lumped_pressure_pa: float = 0.0
    unlumped_pressure_pa: float = 0.0
    guess_pressures_pa: tuple[float | None, ...] = (None, 1e5, 1e6, 5e7)
    lumped_pressure_atol_pa: float = 3.0e4
    shared_composition_atol: float = 2.0e-3
    heavy_total_atol: float = 2.0e-3


PLUS_FRACTION_BUBBLE_CASES = [
    PlusFractionBubbleCase(
        case_id="plus_volatile_oil_characterized_bubble",
        temperature_k=360.0,
        resolved_components=(
            ("N2", 0.0021),
            ("CO2", 0.0187),
            ("C1", 0.3478),
            ("C2", 0.0712),
            ("C3", 0.0934),
            ("iC4", 0.0302),
            ("C4", 0.0431),
            ("iC5", 0.0276),
            ("C5", 0.0418),
            ("C6", 0.0574),
        ),
        z_plus=0.2667,
        mw_plus_g_per_mol=119.78759868766404,
        sg_plus_60f=0.82,
        unlumped_pressure_pa=11485428.523724416,
        lumped_pressure_pa=11466642.931388617,
    ),
    PlusFractionBubbleCase(
        case_id="plus_black_oil_characterized_bubble",
        temperature_k=380.0,
        resolved_components=(
            ("N2", 0.0010),
            ("CO2", 0.0100),
            ("H2S", 0.0040),
            ("C1", 0.1800),
            ("C2", 0.0550),
            ("C3", 0.0700),
            ("iC4", 0.0400),
            ("C4", 0.0500),
            ("iC5", 0.0420),
            ("C5", 0.0500),
            ("C6", 0.0700),
        ),
        z_plus=0.4280,
        mw_plus_g_per_mol=140.1515261682243,
        sg_plus_60f=0.85,
        unlumped_pressure_pa=6433286.67514886,
        lumped_pressure_pa=6424213.010809813,
    ),
    PlusFractionBubbleCase(
        case_id="plus_sour_oil_a_characterized_bubble",
        temperature_k=340.0,
        resolved_components=(
            ("N2", 0.0010),
            ("CO2", 0.0500),
            ("H2S", 0.0700),
            ("C1", 0.2200),
            ("C2", 0.0600),
            ("C3", 0.0700),
            ("iC4", 0.0300),
            ("C4", 0.0400),
            ("iC5", 0.0300),
            ("C5", 0.0400),
            ("C6", 0.0600),
        ),
        z_plus=0.3990,
        mw_plus_g_per_mol=141.17340601503758,
        sg_plus_60f=0.86,
        unlumped_pressure_pa=6842678.819886137,
        lumped_pressure_pa=6838841.936847714,
    ),
    PlusFractionBubbleCase(
        case_id="plus_sour_oil_b_characterized_bubble",
        temperature_k=330.0,
        resolved_components=(
            ("N2", 0.0010),
            ("CO2", 0.0350),
            ("H2S", 0.0900),
            ("C1", 0.1800),
            ("C2", 0.0550),
            ("C3", 0.0650),
            ("iC4", 0.0300),
            ("C4", 0.0400),
            ("iC5", 0.0300),
            ("C5", 0.0400),
            ("C6", 0.0650),
        ),
        z_plus=0.4340,
        mw_plus_g_per_mol=142.62157603686637,
        sg_plus_60f=0.87,
        unlumped_pressure_pa=5295375.60185969,
        lumped_pressure_pa=5293491.026136925,
    ),
]


def _normalize_plus_fraction_case(
    case: PlusFractionBubbleCase,
) -> tuple[list[tuple[str, float]], PlusFractionSpec]:
    """Normalize resolved plus aggregate inputs into a valid characterization feed."""
    total = float(sum(z for _, z in case.resolved_components) + case.z_plus)
    resolved = [(component_id, z / total) for component_id, z in case.resolved_components]
    plus = PlusFractionSpec(
        z_plus=case.z_plus / total,
        mw_plus=case.mw_plus_g_per_mol,
        sg_plus=case.sg_plus_60f,
        label="C7+",
        n_start=7,
    )
    return resolved, plus


def _characterize_case(
    case: PlusFractionBubbleCase,
    *,
    lumping_enabled: bool,
):
    """Characterize a plus-fraction case with or without SCN lumping."""
    resolved, plus = _normalize_plus_fraction_case(case)
    config = CharacterizationConfig(
        n_end=case.max_carbon_number,
        split_mw_model="table",
        lumping_enabled=lumping_enabled,
        lumping_n_groups=case.lumping_n_groups,
    )
    return characterize_fluid(resolved, plus_fraction=plus, config=config), resolved, plus


@pytest.mark.parametrize("case", PLUS_FRACTION_BUBBLE_CASES, ids=lambda case: case.case_id)
def test_plus_fraction_bubble_path_preserves_balances_and_lumped_pressure(case: PlusFractionBubbleCase) -> None:
    """Split/lump/delump should preserve feed balances and bubble pressure closely."""
    characterized_full, resolved, plus = _characterize_case(case, lumping_enabled=False)
    characterized_lumped, _, _ = _characterize_case(case, lumping_enabled=True)

    assert characterized_full.split_result is not None
    assert characterized_lumped.lumping is not None
    assert len(characterized_lumped.component_ids) == len(resolved) + case.lumping_n_groups
    assert len(characterized_full.component_ids) > len(characterized_lumped.component_ids)

    heavy_offset = len(resolved)
    assert float(characterized_full.composition[heavy_offset:].sum()) == pytest.approx(plus.z_plus, abs=1e-12)
    assert float(characterized_lumped.composition[heavy_offset:].sum()) == pytest.approx(plus.z_plus, abs=1e-12)
    assert float(characterized_full.split_result.z.sum()) == pytest.approx(plus.z_plus, abs=1e-12)

    delumped_feed = characterized_lumped.lumping.delump_scn(characterized_lumped.lumping.lump_z)
    np.testing.assert_allclose(
        delumped_feed,
        characterized_lumped.lumping.scn_z,
        atol=1e-14,
        rtol=0.0,
    )

    full_result = calculate_bubble_point(
        case.temperature_k,
        np.asarray(characterized_full.composition, dtype=float),
        characterized_full.components,
        PengRobinsonEOS(characterized_full.components),
        post_check_stability_flip=True,
    )
    assert full_result.converged
    assert float(full_result.pressure) == pytest.approx(case.unlumped_pressure_pa, abs=case.lumped_pressure_atol_pa)

    shared_count = len(resolved)
    for guess in case.guess_pressures_pa:
        lumped_result = calculate_bubble_point(
            case.temperature_k,
            np.asarray(characterized_lumped.composition, dtype=float),
            characterized_lumped.components,
            PengRobinsonEOS(characterized_lumped.components),
            pressure_initial=guess,
            post_check_stability_flip=True,
        )

        assert lumped_result.converged
        assert float(lumped_result.pressure) == pytest.approx(case.lumped_pressure_pa, abs=case.lumped_pressure_atol_pa)
        assert float(lumped_result.pressure) == pytest.approx(full_result.pressure, abs=case.lumped_pressure_atol_pa)

        np.testing.assert_allclose(
            lumped_result.vapor_composition[:shared_count],
            full_result.vapor_composition[:shared_count],
            atol=case.shared_composition_atol,
            rtol=0.0,
        )

        lumped_heavy_total = float(np.sum(lumped_result.vapor_composition[shared_count:]))
        full_heavy_total = float(np.sum(full_result.vapor_composition[shared_count:]))
        assert lumped_heavy_total == pytest.approx(full_heavy_total, abs=case.heavy_total_atol)
