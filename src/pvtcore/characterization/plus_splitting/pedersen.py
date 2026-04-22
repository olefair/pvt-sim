"""Pedersen plus-fraction split."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np


@dataclass(frozen=True)
class PedersenTBPCutConstraint:
    name: str
    carbon_number: int
    carbon_number_end: int
    z: float
    mw: float
    tb_k: float | None = None


@dataclass(frozen=True)
class PedersenSplitResult:
    n: np.ndarray
    MW: np.ndarray
    z: np.ndarray
    A: float
    B: float
    solve_ab_from: str = "balances"
    tbp_cut_rms_relative_error: float | None = None


####################
# HELPER FUNCTIONS
####################
def _mw(Cn: np.ndarray) -> np.ndarray:
    return 14.0 * Cn.astype(float) - 4.0


def _Zn(A: float, B: float, MW: np.ndarray) -> np.ndarray:
    return np.exp(np.clip(A + B * MW, -700.0, 700.0))


def _norm(z: np.ndarray, zP: float) -> tuple[np.ndarray, float]:
    s = float(z.sum())
    if not np.isfinite(s) or s <= 0.0:
        raise RuntimeError("Pedersen split produced a non-positive total mole fraction")
    f = float(zP) / s
    return z * f, float(np.log(f))


def _bal(
    *,
    zP: float,
    MWP: float,
    MW: np.ndarray,
    tol: float,
    itmax: int,
) -> tuple[float, float, np.ndarray]:
    A = float(np.log(float(zP) / float(MW.size)))
    B = 0.0
    t1 = float(zP)
    t2 = float(zP) * float(MWP)

    def F(a: float, b: float) -> tuple[np.ndarray, float, float]:
        z = _Zn(a, b, MW)
        s1 = float(z.sum())
        s2 = float((z * MW).sum())
        return z, s1 - t1, s2 - t2

    for _ in range(itmax):
        z, f1, f2 = F(A, B)
        if abs(f1) < tol and abs(f2) < tol:
            break

        s1 = float(z.sum())
        sMW = float((z * MW).sum())
        sMW2 = float((z * MW * MW).sum())
        J = np.array([[s1, sMW], [sMW, sMW2]], dtype=float)
        rhs = np.array([f1, f2], dtype=float)
        try:
            dA, dB = np.linalg.solve(J, -rhs)
        except np.linalg.LinAlgError as exc:
            raise RuntimeError("Pedersen split Newton step failed (singular Jacobian)") from exc

        step = 1.0
        err = float(np.hypot(f1, f2))
        ok = False
        for _ in range(25):
            A1 = A + step * float(dA)
            B1 = B + step * float(dB)
            _, g1, g2 = F(A1, B1)
            err1 = float(np.hypot(g1, g2))
            if np.isfinite(err1) and err1 <= err:
                A, B = A1, B1
                ok = True
                break
            step *= 0.5
        if not ok:
            raise RuntimeError(
                "Pedersen split failed to reduce residual "
                f"(residual={err:.3e})"
            )

    z, _, _ = F(A, B)
    z, dA = _norm(z, zP)
    A += dA
    if not np.isfinite(z).all() or np.any(z <= 0.0):
        raise RuntimeError("Pedersen split produced non-finite or non-positive z_n")
    return float(A), float(B), z


def _cuts(
    rows: Sequence[PedersenTBPCutConstraint] | None,
    *,
    Cn0: int,
    CnN: int,
) -> tuple[PedersenTBPCutConstraint, ...]:
    if not rows:
        raise ValueError("fit_to_tbp requires non-empty tbp_cuts")

    out = tuple(rows)
    seen: set[str] = set()
    prev: int | None = None
    for row in out:
        if row.name in seen:
            raise ValueError("TBP cut names must be unique when fitting Pedersen to TBP data")
        if row.carbon_number < Cn0:
            raise ValueError("TBP fit cuts must not start below n_start")
        if row.carbon_number_end < row.carbon_number:
            raise ValueError("TBP fit cut carbon_number_end must be >= carbon_number")
        if row.carbon_number_end > CnN:
            raise ValueError("TBP fit cuts must not extend beyond n_end")
        if prev is None:
            if row.carbon_number != Cn0:
                raise ValueError("The first TBP fit cut must start at n_start")
        elif row.carbon_number <= prev:
            raise ValueError("TBP fit cuts must be ordered, non-overlapping, and strictly increasing")
        if not np.isfinite(row.z) or row.z <= 0.0:
            raise ValueError("TBP fit cut z must be finite and > 0")
        if not np.isfinite(row.mw) or row.mw <= 0.0:
            raise ValueError("TBP fit cut mw must be finite and > 0")
        prev = row.carbon_number_end
        seen.add(row.name)
    return out


def _z_from_B(*, B: float, zP: float, MW: np.ndarray) -> tuple[float, np.ndarray]:
    z, dA = _norm(_Zn(0.0, B, MW), zP)
    return dA, z


def _tbp_err(
    *,
    z: np.ndarray,
    MW: np.ndarray,
    Cn: np.ndarray,
    rows: Sequence[PedersenTBPCutConstraint],
    zP: float,
    MWP: float,
) -> np.ndarray:
    s = float(z.sum())
    if not np.isfinite(s) or s <= 0.0:
        return np.full(len(rows) + 2, 1.0e6, dtype=float)

    err: list[float] = []
    for row in rows:
        m = (Cn >= row.carbon_number) & (Cn <= row.carbon_number_end)
        zc = float(z[m].sum())
        err.append((zc - row.z) / max(row.z, 1.0e-12))
        if row.carbon_number_end > row.carbon_number and zc > 0.0:
            MWc = float((z[m] * MW[m]).sum() / zc)
            err.append(0.5 * ((MWc - row.mw) / max(row.mw, 1.0e-12)))

    MWm = float((z * MW).sum()) / s
    err.append((s - zP) / max(zP, 1.0e-12))
    err.append((MWm - MWP) / max(MWP, 1.0e-12))
    return np.asarray(err, dtype=float)


def _tbp_rms(
    *,
    z: np.ndarray,
    Cn: np.ndarray,
    rows: Sequence[PedersenTBPCutConstraint],
) -> float:
    err: list[float] = []
    for row in rows:
        m = (Cn >= row.carbon_number) & (Cn <= row.carbon_number_end)
        zc = float(z[m].sum())
        err.append((zc - row.z) / max(row.z, 1.0e-12))
    return float(np.sqrt(np.mean(np.square(err), dtype=float)))


def _tbp(
    *,
    zP: float,
    MWP: float,
    Cn: np.ndarray,
    MW: np.ndarray,
    rows: tuple[PedersenTBPCutConstraint, ...],
    tol: float,
    itmax: int,
) -> tuple[float, float, np.ndarray, float]:
    _, B0, _ = _bal(zP=zP, MWP=MWP, MW=MW, tol=tol, itmax=itmax)

    def err(B: float) -> np.ndarray:
        _, z = _z_from_B(B=B, zP=zP, MW=MW)
        return _tbp_err(z=z, MW=MW, Cn=Cn, rows=rows, zP=zP, MWP=MWP)

    best_B = float(B0)
    best_e = err(best_B)
    best_s = float(np.dot(best_e, best_e))
    span = max(0.05, abs(best_B) * 4.0 + 0.02)

    for _ in range(max(6, min(itmax, 10))):
        hit = False
        for B in np.linspace(best_B - span, best_B + span, 81):
            e = err(float(B))
            if not np.isfinite(e).all():
                continue
            s = float(np.dot(e, e))
            if s < best_s:
                best_B = float(B)
                best_e = e
                best_s = s
                hit = True
        if best_s < tol * tol:
            break
        span *= 0.5 if hit else 0.35

    A, z = _z_from_B(B=best_B, zP=zP, MW=MW)
    if not np.isfinite(z).all() or np.any(z <= 0.0):
        raise RuntimeError("Pedersen TBP fit produced non-finite or non-positive z_n")
    return float(A), float(best_B), z, _tbp_rms(z=z, Cn=Cn, rows=rows)


####################
# PEDERSEN SPLIT
####################
def plus_frac_split_pedersen(
    *,
    zP: float,
    MWP: float,
    Cn0: int = 7,
    CnN: int = 45,
    mw_fn: Callable[[np.ndarray], np.ndarray] | None = None,
    mode: str = "balances",
    cuts: Sequence[PedersenTBPCutConstraint] | None = None,
    tol: float = 1e-12,
    itmax: int = 50,
) -> PedersenSplitResult:
    if not (zP > 0.0):
        raise ValueError(f"z_plus must be > 0, got {zP}")
    if not (MWP > 0.0):
        raise ValueError(f"MW_plus must be > 0, got {MWP}")
    if CnN < Cn0:
        raise ValueError(f"n_end must be >= n_start, got n_start={Cn0}, n_end={CnN}")

    Cn = np.arange(Cn0, CnN + 1, dtype=int)
    MW = np.asarray((mw_fn or _mw)(Cn), dtype=float)
    if MW.shape != Cn.shape:
        raise ValueError("scn_mw_fn must return array same shape as n")
    if not np.isfinite(MW).all() or np.any(MW <= 0.0):
        raise ValueError("MW_n must be finite and > 0 for all SCNs")

    mode = mode.strip().lower()
    if mode == "balances":
        A, B, z = _bal(zP=zP, MWP=MWP, MW=MW, tol=tol, itmax=itmax)
        return PedersenSplitResult(n=Cn, MW=MW, z=z, A=A, B=B, solve_ab_from=mode)

    if mode == "fit_to_tbp":
        rows = _cuts(cuts, Cn0=Cn0, CnN=CnN)
        A, B, z, rms = _tbp(
            zP=zP,
            MWP=MWP,
            Cn=Cn,
            MW=MW,
            rows=rows,
            tol=tol,
            itmax=itmax,
        )
        return PedersenSplitResult(
            n=Cn,
            MW=MW,
            z=z,
            A=A,
            B=B,
            solve_ab_from=mode,
            tbp_cut_rms_relative_error=rms,
        )

    raise ValueError("solve_ab_from must be either 'balances' or 'fit_to_tbp'")


def split_plus_fraction_pedersen(
    *,
    z_plus: float,
    MW_plus: float,
    n_start: int = 7,
    n_end: int = 45,
    scn_mw_fn: Callable[[np.ndarray], np.ndarray] | None = None,
    solve_ab_from: str = "balances",
    tbp_cuts: Sequence[PedersenTBPCutConstraint] | None = None,
    tol: float = 1e-12,
    max_iter: int = 50,
) -> PedersenSplitResult:
    return plus_frac_split_pedersen(
        zP=z_plus,
        MWP=MW_plus,
        Cn0=n_start,
        CnN=n_end,
        mw_fn=scn_mw_fn,
        mode=solve_ab_from,
        cuts=tbp_cuts,
        tol=tol,
        itmax=max_iter,
    )
