"""Lohrenz plus-fraction split."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np


####################
# HELPER FUNCTIONS
####################
def _mw(Cn: np.ndarray) -> np.ndarray:
    return 14.0 * Cn.astype(float) - 4.0


def _Zn(zR: float, A: float, B: float, dCn: np.ndarray) -> np.ndarray:
    u = A * dCn * dCn + B * dCn
    return zR * np.exp(np.clip(u, -700.0, 700.0))


def _norm(z: np.ndarray, zP: float) -> np.ndarray:
    s = float(z.sum())
    if not np.isfinite(s) or s <= 0.0:
        raise RuntimeError("Lohrenz split produced a non-positive total mole fraction")
    return z * (float(zP) / s)


def _fit(
    *,
    zR: float,
    A0: float,
    B0: float,
    dCn: np.ndarray,
    MW: np.ndarray,
    zP: float,
    MWP: float,
    tol: float,
    itmax: int,
) -> tuple[float, float, float, np.ndarray]:
    zR = float(zR)
    A = float(A0)
    B = float(B0)
    t1 = float(zP)
    t2 = float(zP) * float(MWP)

    def F(zr: float, a: float, b: float) -> tuple[np.ndarray, float, float]:
        z = _Zn(zr, a, b, dCn)
        return z, float(z.sum()) - t1, float((z * MW).sum()) - t2

    for _ in range(itmax):
        ok = False
        for _ in range(itmax):
            z, f1, f2 = F(zR, A, B)
            if abs(f1) < tol and abs(f2) < tol:
                ok = True
                break

            dA = z * dCn * dCn
            dB = z * dCn
            J = np.array(
                [
                    [float(dA.sum()), float(dB.sum())],
                    [float((dA * MW).sum()), float((dB * MW).sum())],
                ],
                dtype=float,
            )
            if abs(float(np.linalg.det(J))) < 1.0e-20:
                break

            rhs = np.array([f1, f2], dtype=float)
            try:
                d1, d2 = np.linalg.solve(J, -rhs)
            except np.linalg.LinAlgError:
                break

            step = 1.0
            err = float(np.hypot(f1, f2))
            hit = False
            for _ in range(25):
                A1 = A + step * float(d1)
                B1 = B + step * float(d2)
                _, g1, g2 = F(zR, A1, B1)
                err1 = float(np.hypot(g1, g2))
                if np.isfinite(err1) and err1 <= err:
                    A, B = A1, B1
                    hit = True
                    break
                step *= 0.5
            if not hit:
                break
        if ok:
            z = _norm(_Zn(zR, A, B, dCn), zP)
            if not np.isfinite(z).all() or np.any(z <= 0.0):
                raise RuntimeError("Lohrenz split produced non-finite or non-positive z_n")
            return zR, float(A), float(B), z
        zR *= 1.1
        A = -0.001
        B = -0.3

    raise RuntimeError(f"Lohrenz split did not converge after {itmax} outer iterations")


####################
# LOHRENZ SPLIT
####################
@dataclass(frozen=True)
class LohrenzSplitResult:
    n: np.ndarray
    MW: np.ndarray
    z: np.ndarray
    A: float
    B: float
    z_ref: float


def plus_frac_split_lohrenz(
    *,
    zP: float,
    MWP: float,
    zR: float | None = None,
    n_ref: int = 6,
    Cn0: int = 7,
    CnN: int = 45,
    mw_fn: Callable[[np.ndarray], np.ndarray] | None = None,
    tol: float = 1e-10,
    itmax: int = 100,
) -> LohrenzSplitResult:
    if not (zP > 0.0):
        raise ValueError(f"z_plus must be > 0, got {zP}")
    if not (MWP > 0.0):
        raise ValueError(f"MW_plus must be > 0, got {MWP}")
    if CnN < Cn0:
        raise ValueError("n_end must be >= n_start")

    Cn = np.arange(Cn0, CnN + 1, dtype=int)
    dCn = Cn.astype(float) - float(n_ref)
    MW = np.asarray((mw_fn or _mw)(Cn), dtype=float)
    if MW.shape != Cn.shape:
        raise ValueError("scn_mw_fn must return array same shape as n")
    if not np.isfinite(MW).all() or np.any(MW <= 0.0):
        raise ValueError("MW_n must be finite and > 0 for all SCNs")

    zR0 = float(zR) if zR is not None else float(zP) * 3.0 / float(Cn.size)
    zR1, A, B, z = _fit(
        zR=zR0,
        A0=-0.001,
        B0=-0.3,
        dCn=dCn,
        MW=MW,
        zP=zP,
        MWP=MWP,
        tol=tol,
        itmax=itmax,
    )
    return LohrenzSplitResult(n=Cn, MW=MW, z=z, A=A, B=B, z_ref=zR1)


def split_plus_fraction_lohrenz(
    *,
    z_plus: float,
    MW_plus: float,
    z_ref: float | None = None,
    n_ref: int = 6,
    n_start: int = 7,
    n_end: int = 45,
    scn_mw_fn: Callable[[np.ndarray], np.ndarray] | None = None,
    tol: float = 1e-10,
    max_iter: int = 100,
) -> LohrenzSplitResult:
    return plus_frac_split_lohrenz(
        zP=z_plus,
        MWP=MW_plus,
        zR=z_ref,
        n_ref=n_ref,
        Cn0=n_start,
        CnN=n_end,
        mw_fn=scn_mw_fn,
        tol=tol,
        itmax=max_iter,
    )


def lohrenz_classic_coefficients(
    *,
    z_6: float,
    n_start: int = 7,
    n_end: int = 45,
    A: float = -0.001,
    B: float = -0.25,
    scn_mw_fn: Callable[[np.ndarray], np.ndarray] | None = None,
) -> LohrenzSplitResult:
    if not (z_6 > 0.0):
        raise ValueError(f"z_6 must be > 0, got {z_6}")

    Cn = np.arange(n_start, n_end + 1, dtype=int)
    dCn = Cn.astype(float) - 6.0
    MW = np.asarray((scn_mw_fn or _mw)(Cn), dtype=float)
    z = _Zn(float(z_6), float(A), float(B), dCn)
    return LohrenzSplitResult(n=Cn, MW=MW, z=z, A=float(A), B=float(B), z_ref=float(z_6))
