"""Pseudo-component property correlations for SCN-based characterization.

This module provides a pluggable interface for estimating pseudo-component
critical properties (Tc, Pc, Vc) and acentric factor (omega) from SCN-level
inputs (MW, SG, Tb).

NOTE
----
The default implementation here (`ParaffinFitCorrelation`) is a pragmatic
fit to the local n-alkane database (C1–C10) shipped with the repo. It is
*not* one of the published correlations (e.g., Riazi–Daubert or Kesler–Lee).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Protocol
import re

import numpy as np

from ..core.errors import CharacterizationError
from ..core.units import kelvin_to_rankine, rankine_to_kelvin, psi_to_pa
from ..core.constants import FT3_TO_M3, LB_TO_KG
from ..models.component import Component, get_components_cached
from .scn_properties import SCNProperties
from ..correlations.riazi_daubert import (
    estimate_from_tb_sg,
    estimate_from_mw_sg,
    edmister_acentric_factor,
)


@dataclass(frozen=True)
class PseudoComponentProperties:
    """Estimated pseudo-component properties."""

    Tc: np.ndarray     # K
    Pc: np.ndarray     # Pa
    Vc: np.ndarray     # m3/mol
    omega: np.ndarray  # dimensionless


class PseudoComponentCorrelation(Protocol):
    """Protocol for pseudo-component property correlations."""

    def estimate(self, scn_props: SCNProperties) -> PseudoComponentProperties:
        ...


def _carbon_number_from_id(component_id: str) -> int | None:
    match = re.search(r"C(\d+)", component_id, re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _select_n_alkanes(components: Mapping[str, Component]) -> Dict[int, Component]:
    n_alkanes: Dict[int, Component] = {}
    for comp_id, comp in components.items():
        if re.match(r"^C\d+$", comp_id):
            carbon_number = _carbon_number_from_id(comp_id)
            if carbon_number is not None:
                n_alkanes[carbon_number] = comp
    return dict(sorted(n_alkanes.items()))


class ParaffinFitCorrelation:
    """Interim SCN correlation based on a regression of n-alkane properties."""

    def __init__(
        self,
        components: Mapping[str, Component] | None = None,
        *,
        fit_degree: int = 1,
    ) -> None:
        if components is None:
            components = get_components_cached()
        self._n_alkanes = _select_n_alkanes(components)
        if len(self._n_alkanes) < 3:
            raise CharacterizationError(
                "ParaffinFitCorrelation requires at least 3 n-alkanes (C1..C10) in the database."
            )

        mw = np.array([c.MW for c in self._n_alkanes.values()], dtype=float)
        Tc = np.array([c.Tc for c in self._n_alkanes.values()], dtype=float)
        Pc = np.array([c.Pc for c in self._n_alkanes.values()], dtype=float)
        Vc = np.array([c.Vc for c in self._n_alkanes.values()], dtype=float)
        omega = np.array([c.omega for c in self._n_alkanes.values()], dtype=float)

        self._tc_coef = np.polyfit(mw, Tc, fit_degree)
        self._vc_coef = np.polyfit(mw, Vc, fit_degree)
        self._omega_coef = np.polyfit(mw, omega, fit_degree)
        self._ln_pc_coef = np.polyfit(mw, np.log(Pc), fit_degree)

    def estimate(self, scn_props: SCNProperties) -> PseudoComponentProperties:
        mw = np.asarray(scn_props.mw, dtype=float)

        Tc = np.polyval(self._tc_coef, mw)
        Vc = np.polyval(self._vc_coef, mw)
        omega = np.polyval(self._omega_coef, mw)
        Pc = np.exp(np.polyval(self._ln_pc_coef, mw))

        for idx, n in enumerate(scn_props.n):
            comp = self._n_alkanes.get(int(n))
            if comp is None:
                continue
            Tc[idx] = comp.Tc
            Pc[idx] = comp.Pc
            Vc[idx] = comp.Vc
            omega[idx] = comp.omega

        if (
            np.any(~np.isfinite(Tc))
            or np.any(~np.isfinite(Pc))
            or np.any(~np.isfinite(Vc))
            or np.any(~np.isfinite(omega))
        ):
            raise CharacterizationError("Non-finite pseudo-component properties from ParaffinFitCorrelation.")

        if np.any(Tc <= 0.0) or np.any(Pc <= 0.0) or np.any(Vc <= 0.0):
            raise CharacterizationError("Non-physical pseudo-component critical properties (<= 0).")

        omega = np.clip(omega, -0.2, 2.5)
        return PseudoComponentProperties(Tc=Tc, Pc=Pc, Vc=Vc, omega=omega)


class RiaziDaubertCorrelation:
    """Riazi-Daubert (1987) pseudo-component correlation."""

    def __init__(self, *, prefer_tb_form: bool = True) -> None:
        self._prefer_tb_form = prefer_tb_form

    def estimate(self, scn_props: SCNProperties) -> PseudoComponentProperties:
        mw = np.asarray(scn_props.mw, dtype=float)
        sg = np.asarray(scn_props.sg_6060, dtype=float)
        tb_k = np.asarray(scn_props.tb_k, dtype=float)

        use_tb = self._prefer_tb_form and np.isfinite(tb_k).all()
        if use_tb:
            tb_r = kelvin_to_rankine(tb_k)
            Tc_r, Pc_psia, Vc_ft3_per_lb = estimate_from_tb_sg(tb_r, sg)
            Tb_r = tb_r
        else:
            Tc_r, Pc_psia, Vc_ft3_per_lb, Tb_r = estimate_from_mw_sg(mw, sg)

        Tc_k = rankine_to_kelvin(Tc_r)
        Pc_pa = psi_to_pa(Pc_psia)

        Vc_m3_per_kg = Vc_ft3_per_lb * (FT3_TO_M3 / LB_TO_KG)
        Vc_m3_per_mol = Vc_m3_per_kg * (mw / 1000.0)

        omega = edmister_acentric_factor(Tc_r, Pc_psia, Tb_r)

        if np.any(~np.isfinite(Tc_k)) or np.any(~np.isfinite(Pc_pa)) or np.any(~np.isfinite(Vc_m3_per_mol)):
            raise CharacterizationError("Non-finite pseudo-component properties from Riazi-Daubert.")

        if np.any(Tc_k <= 0.0) or np.any(Pc_pa <= 0.0) or np.any(Vc_m3_per_mol <= 0.0):
            raise CharacterizationError("Non-physical pseudo-component critical properties (<= 0).")

        if np.any(~np.isfinite(omega)):
            raise CharacterizationError("Non-finite acentric factors from Edmister correlation.")

        return PseudoComponentProperties(Tc=Tc_k, Pc=Pc_pa, Vc=Vc_m3_per_mol, omega=omega)
