"""Tests for the desktop assignment-case preset builder."""

from __future__ import annotations

import pytest

from pvtapp.assignment_case import build_assignment_desktop_preset
from pvtcore.validation.pete665_assignment import psia_to_pa


def test_build_assignment_desktop_preset_preserves_assignment_feed_and_exact_schedules() -> None:
    preset = build_assignment_desktop_preset(initials="TANS")

    assert preset.selected_initials == "TANS"
    assert preset.temperature_f == pytest.approx(125.0)
    assert preset.temperature_k > 0.0
    assert sum(entry.mole_fraction for entry in preset.composition.components) == pytest.approx(1.00001)
    assert [entry.component_id for entry in preset.composition.components][-1] == "PSEUDO_PLUS"
    assert len(preset.composition.inline_components) == 1
    assert preset.cce_config.pressure_points_pa == pytest.approx(
        [psia_to_pa(1500.0), psia_to_pa(1250.0), psia_to_pa(1000.0)]
    )
    assert preset.dl_config.pressure_points_pa == pytest.approx(
        [psia_to_pa(500.0), psia_to_pa(300.0), psia_to_pa(100.0)]
    )
    assert preset.bubble_point_config.pressure_initial_pa == pytest.approx(preset.bubble_pressure_pa)
    assert preset.dl_config.bubble_pressure_pa == pytest.approx(preset.bubble_pressure_pa)
    assert preset.dl_config.bubble_pressure_pa > max(preset.dl_config.pressure_points_pa)
