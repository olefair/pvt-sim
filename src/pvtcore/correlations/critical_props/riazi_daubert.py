"""Riazi-Daubert (1987) critical property correlations.

This module implements the generalized correlations presented by
Riazi & Daubert (1987) and reproduced in standard petroleum PVT texts.

Form 1 (Tb, SG):
    θ = a * Tb^b * SG^c * exp(d*Tb + e*SG + f*Tb*SG)

Form 2 (MW, SG):
    θ = a * MW^b * SG^c * exp(d*MW + e*SG + f*MW*SG)

Where θ is one of {Tc, Pc, Vc, Tb, MW} depending on the coefficient set.

Units for the base correlations:
    Tb : °R
    Tc : °R
    Pc : psia
    Vc : ft³/lb
    MW : g/mol
    SG : dimensionless (60/60°F)
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, Iterable, Mapping, Tuple

import numpy as np


@dataclass(frozen=True)
class RiaziDaubertCoefficients:
    a: float
    b: float
    c: float
    d: float
    e: float
    f: float


_TB_SG_COEFFICIENTS: Dict[str, RiaziDaubertCoefficients] = {
    # Table 2-4 (Tb, SG) form
    "Tc": RiaziDaubertCoefficients(
        a=10.6443, b=0.81067, c=0.53691, d=-5.17470e-4, e=-0.54444, f=3.59950e-4
    ),
    "Pc": RiaziDaubertCoefficients(
        a=6.16200e6, b=-0.48440, c=4.08460, d=-4.72500e-3, e=-4.80140, f=3.19390e-3
    ),
    "Vc": RiaziDaubertCoefficients(
        a=6.23300e-4, b=0.75060, c=-1.20280, d=-1.46790e-3, e=-0.26404, f=1.09500e-3
    ),
    "MW": RiaziDaubertCoefficients(
        a=581.96000, b=-0.97476, c=6.51274, d=5.43076e-4, e=9.53384, f=1.11056e-3
    ),
}

_MW_SG_COEFFICIENTS: Dict[str, RiaziDaubertCoefficients] = {
    # Table 2-5 (MW, SG) form
    "Tc": RiaziDaubertCoefficients(
        a=544.40000, b=0.299800, c=1.05550, d=-1.34780e-4, e=-0.616410, f=0.0
    ),
    "Pc": RiaziDaubertCoefficients(
        a=4.52030e4, b=-0.806300, c=1.60150, d=-1.80780e-3, e=-0.308400, f=0.0
    ),
    "Vc": RiaziDaubertCoefficients(
        a=1.20600e-2, b=0.203780, c=-1.30360, d=-2.65700e-3, e=0.528700, f=2.60120e-3
    ),
    "Tb": RiaziDaubertCoefficients(
        a=6.77857, b=0.401673, c=-1.58262, d=3.77409e-3, e=2.984036, f=-4.25288e-3
    ),
}


def _evaluate_correlation(
    x: np.ndarray,
    sg: np.ndarray,
    coeffs: RiaziDaubertCoefficients,
) -> np.ndarray:
    return (
        coeffs.a
        * np.power(x, coeffs.b)
        * np.power(sg, coeffs.c)
        * np.exp(coeffs.d * x + coeffs.e * sg + coeffs.f * x * sg)
    )


def estimate_from_tb_sg(
    tb_r: np.ndarray,
    sg: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Estimate Tc, Pc, Vc from normal boiling point and specific gravity.

    Parameters
    ----------
    tb_r : array_like
        Normal boiling point in °R.
    sg : array_like
        Specific gravity (60/60°F).

    Returns
    -------
    Tc_r, Pc_psia, Vc_ft3_per_lb
        Estimated properties in the correlation's native units.
    """
    tb_r = np.asarray(tb_r, dtype=float)
    sg = np.asarray(sg, dtype=float)

    Tc_r = _evaluate_correlation(tb_r, sg, _TB_SG_COEFFICIENTS["Tc"])
    Pc_psia = _evaluate_correlation(tb_r, sg, _TB_SG_COEFFICIENTS["Pc"])
    Vc_ft3_per_lb = _evaluate_correlation(tb_r, sg, _TB_SG_COEFFICIENTS["Vc"])

    return Tc_r, Pc_psia, Vc_ft3_per_lb


def estimate_from_mw_sg(
    mw_g_per_mol: np.ndarray,
    sg: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Estimate Tc, Pc, Vc, Tb from molecular weight and specific gravity.

    Parameters
    ----------
    mw_g_per_mol : array_like
        Molecular weight in g/mol.
    sg : array_like
        Specific gravity (60/60°F).

    Returns
    -------
    Tc_r, Pc_psia, Vc_ft3_per_lb, Tb_r
        Estimated properties in the correlation's native units.
    """
    mw_g_per_mol = np.asarray(mw_g_per_mol, dtype=float)
    sg = np.asarray(sg, dtype=float)

    Tc_r = _evaluate_correlation(mw_g_per_mol, sg, _MW_SG_COEFFICIENTS["Tc"])
    Pc_psia = _evaluate_correlation(mw_g_per_mol, sg, _MW_SG_COEFFICIENTS["Pc"])
    Vc_ft3_per_lb = _evaluate_correlation(mw_g_per_mol, sg, _MW_SG_COEFFICIENTS["Vc"])
    Tb_r = _evaluate_correlation(mw_g_per_mol, sg, _MW_SG_COEFFICIENTS["Tb"])

    return Tc_r, Pc_psia, Vc_ft3_per_lb, Tb_r


def edmister_acentric_factor(
    Tc_r: np.ndarray,
    Pc_psia: np.ndarray,
    Tb_r: np.ndarray,
) -> np.ndarray:
    """Compute acentric factor using the Edmister correlation.

    omega = (3/7) * (Tbr / (1 - Tbr)) * log10(Pc / 14.7) - 1
    where Tbr = Tb / Tc
    """
    Tc_r = np.asarray(Tc_r, dtype=float)
    Pc_psia = np.asarray(Pc_psia, dtype=float)
    Tb_r = np.asarray(Tb_r, dtype=float)

    Tbr = Tb_r / Tc_r
    return (3.0 / 7.0) * (Tbr / (1.0 - Tbr)) * np.log10(Pc_psia / 14.7) - 1.0
