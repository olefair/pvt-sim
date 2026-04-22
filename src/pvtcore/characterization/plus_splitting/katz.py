"""Katz plus-fraction split."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np


####################
# HELPER FUNCTIONS
####################
def _mw(Cn: np.ndarray) -> np.ndarray:
    return 14.0 * Cn.astype(float) - 4.0


def _Zn(A: float, B: float, Cn: np.ndarray) -> np.ndarray:
    return A * np.exp(np.clip(-B * Cn.astype(float), -700.0, 700.0))


def _norm(z: np.ndarray, zP: float) -> np.ndarray:
    s = float(z.sum())
    if not np.isfinite(s) or s <= 0.0:
        raise RuntimeError("Katz split produced a non-positive total mole fraction")
    return z * (float(zP) / s)


def _fit(
    *,
    zP: float,
    MWP: float,
    Cn: np.ndarray,
    MW: np.ndarray,
    tol: float,
    itmax: int,
) -> tuple[float, float, np.ndarray]:
    A = 1.38205 * float(zP)
    B = 0.25903
    t1 = float(zP)
    t2 = float(zP) * float(MWP)
    Cf = Cn.astype(float)

    def F(a: float, b: float) -> tuple[np.ndarray, float, float]:
        z = _Zn(a, b, Cn)
        return z, float(z.sum()) - t1, float((z * MW).sum()) - t2

    for _ in range(itmax):
        z, f1, f2 = F(A, B)
        if abs(f1) < tol and abs(f2) < tol:
            break

        d1a = float(z.sum()) / A if A != 0.0 else 1.0e10
        d1b = -float((Cf * z).sum())
        d2a = float((z * MW).sum()) / A if A != 0.0 else 1.0e10
        d2b = -float((Cf * z * MW).sum())
        J = np.array([[d1a, d1b], [d2a, d2b]], dtype=float)
        rhs = np.array([f1, f2], dtype=float)
        try:
            dA, dB = np.linalg.solve(J, -rhs)
        except np.linalg.LinAlgError as exc:
            raise RuntimeError("Katz split Newton step failed (singular Jacobian)") from exc

        step = 1.0
        err = float(np.hypot(f1, f2))
        ok = False
        for _ in range(25):
            A1 = A + step * float(dA)
            B1 = max(0.01, B + step * float(dB))
            if A1 <= 0.0:
                step *= 0.5
                continue
            _, g1, g2 = F(A1, B1)
            err1 = float(np.hypot(g1, g2))
            if np.isfinite(err1) and err1 <= err:
                A, B = A1, B1
                ok = True
                break
            step *= 0.5
        if not ok:
            raise RuntimeError(f"Katz split failed to reduce residual (residual={err:.3e})")

    z = _norm(_Zn(A, B, Cn), zP)
    if not np.isfinite(z).all() or np.any(z <= 0.0):
        raise RuntimeError("Katz split produced non-finite or non-positive z_n")
    return float(A), float(B), z


####################
# KATZ SPLIT
####################
@dataclass(frozen=True)
class KatzSplitResult:
    n: np.ndarray
    MW: np.ndarray
    z: np.ndarray
    A: float
    B: float


def plus_frac_split_katz(
    *,
    zP: float,
    MWP: float,
    Cn0: int = 7,
    CnN: int = 45,
    mw_fn: Callable[[np.ndarray], np.ndarray] | None = None,
    tol: float = 1e-10,
    itmax: int = 100,
) -> KatzSplitResult:
    if not (zP > 0.0):
        raise ValueError(f"z_plus must be > 0, got {zP}")
    if not (MWP > 0.0):
        raise ValueError(f"MW_plus must be > 0, got {MWP}")
    if CnN < Cn0:
        raise ValueError("n_end must be >= n_start")

    Cn = np.arange(Cn0, CnN + 1, dtype=int)
    MW = np.asarray((mw_fn or _mw)(Cn), dtype=float)
    if MW.shape != Cn.shape:
        raise ValueError("scn_mw_fn must return array same shape as n")
    if not np.isfinite(MW).all() or np.any(MW <= 0.0):
        raise ValueError("MW_n must be finite and > 0 for all SCNs")

    A, B, z = _fit(zP=zP, MWP=MWP, Cn=Cn, MW=MW, tol=tol, itmax=itmax)
    return KatzSplitResult(n=Cn, MW=MW, z=z, A=A, B=B)


def split_plus_fraction_katz(
    *,
    z_plus: float,
    MW_plus: float,
    n_start: int = 7,
    n_end: int = 45,
    scn_mw_fn: Callable[[np.ndarray], np.ndarray] | None = None,
    tol: float = 1e-10,
    max_iter: int = 100,
) -> KatzSplitResult:
    return plus_frac_split_katz(
        zP=z_plus,
        MWP=MW_plus,
        Cn0=n_start,
        CnN=n_end,
        mw_fn=scn_mw_fn,
        tol=tol,
        itmax=max_iter,
    )


def katz_classic_split(
    *,
    z_plus: float,
    n_start: int = 7,
    n_end: int = 45,
    scn_mw_fn: Callable[[np.ndarray], np.ndarray] | None = None,
) -> KatzSplitResult:
    if not (z_plus > 0.0):
        raise ValueError(f"z_plus must be > 0, got {z_plus}")

    Cn = np.arange(n_start, n_end + 1, dtype=int)
    MW = np.asarray((scn_mw_fn or _mw)(Cn), dtype=float)
    A = 1.38205 * float(z_plus)
    B = 0.25903
    z = _norm(_Zn(A, B, Cn), z_plus)
    return KatzSplitResult(n=Cn, MW=MW, z=z, A=A, B=B)
