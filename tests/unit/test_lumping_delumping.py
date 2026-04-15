import numpy as np
import pytest

from pvtcore.characterization import (
    CharacterizationConfig,
    PlusFractionSpec,
    characterize_fluid,
)
from pvtcore.core.errors import CharacterizationError


def test_lumping_reduces_component_count_and_preserves_balances() -> None:
    resolved = [
        ("C1", 0.50),
        ("C2", 0.10),
        ("C3", 0.05),
        ("C4", 0.05),
        ("C5", 0.03),
        ("C6", 0.02),
    ]
    plus = PlusFractionSpec(z_plus=0.25, mw_plus=215.0, n_start=7)
    cfg = CharacterizationConfig(lumping_enabled=True, lumping_n_groups=8)

    result = characterize_fluid(resolved, plus_fraction=plus, config=cfg)

    assert result.lumping is not None
    assert len(result.component_ids) == len(resolved) + 8
    assert np.isclose(float(result.composition.sum()), 1.0)

    # Pseudo-part (lumped) should sum to the plus fraction
    z_pseudo = result.composition[len(resolved):]
    assert np.isclose(float(z_pseudo.sum()), plus.z_plus)

    # MW balance preserved across SCN -> lumps by construction
    scn_z = result.lumping.scn_z
    scn_mw = result.lumping.scn_props.mw
    lump_z = result.lumping.lump_z
    lump_mw = np.array([c.MW for c in result.lumping.lump_components], dtype=float)

    mw_scn = float(np.dot(scn_z, scn_mw))
    mw_lump = float(np.dot(lump_z, lump_mw))
    assert mw_lump == pytest.approx(mw_scn, abs=1e-12)

    # Delumping should exactly reconstruct the original SCN distribution (feed-based weights)
    scn_recon = result.lumping.delump_scn(lump_z)
    assert np.allclose(scn_recon, scn_z, atol=1e-14, rtol=0.0)


def test_lumping_rejects_too_many_groups() -> None:
    resolved = [("C1", 0.75)]
    plus = PlusFractionSpec(z_plus=0.25, mw_plus=215.0, n_start=7)
    cfg = CharacterizationConfig(lumping_enabled=True, lumping_n_groups=100)

    with pytest.raises(CharacterizationError):
        characterize_fluid(resolved, plus_fraction=plus, config=cfg)


def test_lumping_accepts_legacy_contiguous_method() -> None:
    resolved = [("C1", 0.50), ("C2", 0.25)]
    plus = PlusFractionSpec(z_plus=0.25, mw_plus=215.0, n_start=7)
    cfg = CharacterizationConfig(
        lumping_enabled=True,
        lumping_n_groups=4,
        lumping_method="contiguous",
    )

    result = characterize_fluid(resolved, plus_fraction=plus, config=cfg)

    assert result.lumping is not None
    assert len(result.lumping.lump_component_ids) == 4
