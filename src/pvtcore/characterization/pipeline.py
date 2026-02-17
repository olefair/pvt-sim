"""End-to-end fluid characterization pipeline.

This module converts lab-style composition inputs (resolved components + optional
plus fraction) into an EOS-ready component list and composition vector.

This is an *additive* pipeline API that co-exists with `CharacterizedFluid`.
It is primarily used by the schema-driven loader in `pvtcore.io.fluid_definition`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence
import re

import numpy as np

from ..core.errors import CharacterizationError, CompositionError, ValidationError
from ..models.component import Component, get_components_cached
from .plus_splitting.pedersen import PedersenSplitResult, split_plus_fraction_pedersen
from .scn_properties import SCNProperties, get_scn_properties
from .pseudo_correlations import (
    ParaffinFitCorrelation,
    PseudoComponentCorrelation,
    RiaziDaubertCorrelation,
)


@dataclass(frozen=True)
class PlusFractionSpec:
    """Input specification for a plus fraction (Cn+)."""

    z_plus: float
    mw_plus: float  # g/mol
    sg_plus: float | None = None
    label: str = "C7+"
    n_start: int = 7


@dataclass(frozen=True)
class BinaryInteractionOverride:
    """Override for a single kij pair."""

    component_i: str
    component_j: str
    kij: float


@dataclass(frozen=True)
class CharacterizationConfig:
    """Configuration options for characterization."""

    n_end: int = 45
    extrapolate_scn: bool = True
    split_method: str = "pedersen"
    split_mw_model: str = "paraffin"  # "paraffin" (14n-4) or "table"
    normalize_composition: bool = True
    normalization_tol: float = 1e-6
    correlation: PseudoComponentCorrelation | str | None = "riazi_daubert"
    kij_overrides: Sequence[BinaryInteractionOverride] | None = None
    kij_default: float = 0.0
    lumping_enabled: bool = False
    lumping_n_groups: int = 8
    lumping_method: str = "contiguous"


@dataclass(frozen=True)
class SCNLumpingResult:
    """SCN lumping result + delumping helpers."""

    scn_component_ids: list[str]
    scn_components: list[Component]
    scn_z: np.ndarray
    scn_props: SCNProperties

    lump_component_ids: list[str]
    lump_components: list[Component]
    lump_z: np.ndarray

    scn_to_lump: np.ndarray          # shape (N_scn,), entries in [0, n_lumps)
    lump_members: list[np.ndarray]   # each element: indices into SCN arrays
    lump_weights: list[np.ndarray]   # each element: weights aligned to lump_members (sum=1)

    def delump_scn(self, lumped_z: np.ndarray) -> np.ndarray:
        """Expand a lumped SCN composition back to SCN resolution."""
        lumped_z = np.asarray(lumped_z, dtype=float)
        if lumped_z.shape != self.lump_z.shape:
            raise CharacterizationError(
                "lumped_z shape mismatch for delumping.",
                n_lumps_expected=int(self.lump_z.size),
                n_lumps_got=int(lumped_z.size),
            )

        z_scn = np.zeros_like(self.scn_z, dtype=float)
        for g, members in enumerate(self.lump_members):
            z_scn[members] = lumped_z[g] * self.lump_weights[g]
        return z_scn


@dataclass(frozen=True)
class CharacterizationResult:
    """Result of fluid characterization."""

    component_ids: list[str]
    components: list[Component]
    composition: np.ndarray
    binary_interaction: np.ndarray
    scn_properties: SCNProperties | None = None
    split_result: PedersenSplitResult | None = None
    plus_fraction: PlusFractionSpec | None = None
    lumping: SCNLumpingResult | None = None


def _carbon_number_from_id(component_id: str) -> int | None:
    match = re.search(r"C(\d+)", component_id, re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _normalize_component_input(
    components: Mapping[str, float] | Sequence[tuple[str, float]],
) -> list[tuple[str, float]]:
    if isinstance(components, Mapping):
        items = list(components.items())
    else:
        items = list(components)

    z_by_id: dict[str, float] = {}
    for comp_id, z in items:
        if z < 0.0:
            raise CompositionError("Negative component mole fraction.", composition={comp_id: z})
        z_by_id[comp_id] = z_by_id.get(comp_id, 0.0) + float(z)

    if isinstance(components, Mapping):
        ordered = sorted(z_by_id.items(), key=lambda kv: kv[0])
    else:
        seen = set()
        ordered = []
        for comp_id, _ in items:
            if comp_id in seen:
                continue
            ordered.append((comp_id, z_by_id[comp_id]))
            seen.add(comp_id)

    return ordered


def _resolve_correlation(
    corr: PseudoComponentCorrelation | str | None,
) -> PseudoComponentCorrelation:
    if corr is None:
        raise CharacterizationError(
            "No pseudo-component correlation configured. Provide a correlation implementation."
        )
    if isinstance(corr, str):
        if corr == "paraffin_fit":
            return ParaffinFitCorrelation()
        if corr == "riazi_daubert":
            return RiaziDaubertCorrelation(prefer_tb_form=True)
        if corr == "riazi_daubert_mw":
            return RiaziDaubertCorrelation(prefer_tb_form=False)
        raise CharacterizationError(f"Unknown pseudo-component correlation '{corr}'.")
    return corr


def _build_kij_matrix(
    component_ids: Sequence[str],
    overrides: Sequence[BinaryInteractionOverride] | None,
    default_kij: float,
    *,
    plus_fraction: PlusFractionSpec | None = None,
    pseudo_component_ids: Sequence[str] | None = None,
) -> np.ndarray:
    n = len(component_ids)
    kij = np.full((n, n), float(default_kij), dtype=float)

    if overrides is None:
        return kij

    id_to_idx = {cid: i for i, cid in enumerate(component_ids)}

    pseudo_indices: list[int] = []
    pseudo_hi: list[int] = []
    if plus_fraction is not None and pseudo_component_ids is not None:
        for cid in pseudo_component_ids:
            if cid not in id_to_idx:
                continue
            pseudo_indices.append(id_to_idx[cid])

            if cid.startswith("SCN"):
                try:
                    pseudo_hi.append(int(cid[3:]))
                except ValueError:
                    pseudo_hi.append(plus_fraction.n_start)
            else:
                m = re.match(r"^LUMP\d+_C(\d+)_C(\d+)$", cid)
                if m:
                    pseudo_hi.append(int(m.group(2)))
                else:
                    pseudo_hi.append(plus_fraction.n_start)

    def resolve_targets(token: str) -> list[int]:
        if token in id_to_idx:
            return [id_to_idx[token]]

        if plus_fraction is None or pseudo_component_ids is None:
            return []

        if token == plus_fraction.label:
            return list(pseudo_indices)

        m = re.match(r"^C(\d+)\+$", token)
        if m:
            cut = int(m.group(1))
            return [idx for idx, hi in zip(pseudo_indices, pseudo_hi) if hi >= cut]

        return []

    for override in overrides:
        targets_i = resolve_targets(override.component_i)
        targets_j = resolve_targets(override.component_j)
        if not targets_i or not targets_j:
            raise CharacterizationError(
                "kij override references unknown component id.",
                component=f"{override.component_i}-{override.component_j}",
            )
        for i in targets_i:
            for j in targets_j:
                kij[i, j] = override.kij
                kij[j, i] = override.kij

    return kij


def _lump_scns_contiguous(
    *,
    scn_props: SCNProperties,
    scn_components: Sequence[Component],
    scn_component_ids: Sequence[str],
    scn_z: np.ndarray,
    n_groups: int,
    correlation: PseudoComponentCorrelation,
) -> SCNLumpingResult:
    scn_z = np.asarray(scn_z, dtype=float)
    if scn_z.ndim != 1:
        raise CharacterizationError("scn_z must be 1D for lumping.")

    n_scn = int(scn_props.n.size)
    if len(scn_components) != n_scn or len(scn_component_ids) != n_scn or scn_z.size != n_scn:
        raise CharacterizationError(
            "SCN arrays length mismatch for lumping.",
            n_scn=n_scn,
            n_components=len(scn_components),
            n_ids=len(scn_component_ids),
            n_z=int(scn_z.size),
        )

    if not (1 <= n_groups <= n_scn):
        raise CharacterizationError(
            "n_groups must be between 1 and number of SCNs.",
            n_groups=n_groups,
            n_scn=n_scn,
        )

    partitions = np.array_split(np.arange(n_scn, dtype=int), n_groups)
    lump_members: list[np.ndarray] = [p.astype(int) for p in partitions]

    scn_to_lump = np.empty(n_scn, dtype=int)
    for g, members in enumerate(lump_members):
        scn_to_lump[members] = g

    lump_z = np.array([float(scn_z[m].sum()) for m in lump_members], dtype=float)

    lump_weights: list[np.ndarray] = []
    for m in lump_members:
        z_g = scn_z[m]
        s = float(z_g.sum())
        if s <= 0.0:
            lump_weights.append(np.full_like(z_g, 1.0 / float(z_g.size), dtype=float))
        else:
            lump_weights.append(z_g / s)

    mw_lump = np.array(
        [float(np.dot(lump_weights[g], scn_props.mw[m])) for g, m in enumerate(lump_members)],
        dtype=float,
    )
    sg_lump = np.array(
        [float(np.dot(lump_weights[g], scn_props.sg_6060[m])) for g, m in enumerate(lump_members)],
        dtype=float,
    )
    tb_lump = np.array(
        [float(np.dot(lump_weights[g], scn_props.tb_k[m])) for g, m in enumerate(lump_members)],
        dtype=float,
    )

    n_lo = np.array([int(scn_props.n[m][0]) for m in lump_members], dtype=int)
    n_hi = np.array([int(scn_props.n[m][-1]) for m in lump_members], dtype=int)
    n_rep = n_hi.copy()

    lump_props = SCNProperties(n=n_rep, mw=mw_lump, sg_6060=sg_lump, tb_k=tb_lump)
    pseudo = correlation.estimate(lump_props)

    lump_component_ids: list[str] = []
    lump_components: list[Component] = []
    for g in range(n_groups):
        cid = f"LUMP{g+1}_C{int(n_lo[g])}_C{int(n_hi[g])}"
        lump_component_ids.append(cid)
        lump_components.append(
            Component(
                name=cid,
                formula=cid,
                Tc=float(pseudo.Tc[g]),
                Pc=float(pseudo.Pc[g]),
                Vc=float(pseudo.Vc[g]),
                omega=float(pseudo.omega[g]),
                MW=float(mw_lump[g]),
                Tb=float(tb_lump[g]),
                note=f"SCN lump: C{int(n_lo[g])}-C{int(n_hi[g])}",
            )
        )

    return SCNLumpingResult(
        scn_component_ids=list(scn_component_ids),
        scn_components=list(scn_components),
        scn_z=scn_z.copy(),
        scn_props=scn_props,
        lump_component_ids=lump_component_ids,
        lump_components=lump_components,
        lump_z=lump_z,
        scn_to_lump=scn_to_lump,
        lump_members=lump_members,
        lump_weights=lump_weights,
    )


def characterize_fluid(
    components: Mapping[str, float] | Sequence[tuple[str, float]],
    *,
    plus_fraction: PlusFractionSpec | None = None,
    config: CharacterizationConfig | None = None,
) -> CharacterizationResult:
    cfg = config or CharacterizationConfig()
    resolved = _normalize_component_input(components)

    if plus_fraction is not None:
        if plus_fraction.z_plus <= 0.0:
            raise ValidationError(
                "plus_fraction.z_plus must be > 0.", parameter="z_plus", value=plus_fraction.z_plus
            )
        if plus_fraction.mw_plus <= 0.0:
            raise ValidationError(
                "plus_fraction.mw_plus must be > 0.", parameter="mw_plus", value=plus_fraction.mw_plus
            )
        if cfg.n_end < plus_fraction.n_start:
            raise ValidationError(
                "n_end must be >= n_start for plus fraction.",
                parameter="n_end",
                value=cfg.n_end,
            )

        for comp_id, _ in resolved:
            carbon_number = _carbon_number_from_id(comp_id)
            if carbon_number is not None and carbon_number >= plus_fraction.n_start:
                raise CompositionError(
                    "Resolved components overlap plus-fraction cut. "
                    f"Component '{comp_id}' is >= C{plus_fraction.n_start}.",
                    composition={comp_id: dict(resolved).get(comp_id)},
                )

    z_resolved = np.array([z for _, z in resolved], dtype=float)
    total = float(z_resolved.sum()) + (plus_fraction.z_plus if plus_fraction else 0.0)

    if abs(total - 1.0) > cfg.normalization_tol:
        if cfg.normalize_composition:
            z_resolved = z_resolved / total
            if plus_fraction is not None:
                plus_fraction = PlusFractionSpec(
                    z_plus=plus_fraction.z_plus / total,
                    mw_plus=plus_fraction.mw_plus,
                    sg_plus=plus_fraction.sg_plus,
                    label=plus_fraction.label,
                    n_start=plus_fraction.n_start,
                )
        else:
            raise CompositionError(
                "Composition does not sum to 1.0 and normalize_composition is False.",
                composition=dict(resolved),
            )

    components_db = get_components_cached()
    resolved_components: list[Component] = []
    resolved_ids: list[str] = []
    for comp_id, _ in resolved:
        if comp_id not in components_db:
            raise CompositionError(
                f"Unknown component id '{comp_id}'.",
                composition={comp_id: dict(resolved).get(comp_id)},
            )
        resolved_ids.append(comp_id)
        resolved_components.append(components_db[comp_id])

    if plus_fraction is None:
        composition = z_resolved.copy()
        kij = _build_kij_matrix(resolved_ids, cfg.kij_overrides, cfg.kij_default)
        return CharacterizationResult(
            component_ids=resolved_ids,
            components=resolved_components,
            composition=composition,
            binary_interaction=kij,
        )

    if cfg.split_method.lower() != "pedersen":
        raise CharacterizationError(f"Unsupported split method '{cfg.split_method}'.")

    scn_props = get_scn_properties(
        n_start=plus_fraction.n_start,
        n_end=cfg.n_end,
        extrapolate=cfg.extrapolate_scn,
    )

    if cfg.split_mw_model == "table":
        n_start = plus_fraction.n_start

        def scn_mw_fn(n: np.ndarray) -> np.ndarray:
            idx = n.astype(int) - n_start
            if np.any(idx < 0) or np.any(idx >= scn_props.mw.size):
                raise CharacterizationError("SCN MW lookup out of range.")
            return scn_props.mw[idx]

        split = split_plus_fraction_pedersen(
            z_plus=plus_fraction.z_plus,
            MW_plus=plus_fraction.mw_plus,
            n_start=plus_fraction.n_start,
            n_end=cfg.n_end,
            scn_mw_fn=scn_mw_fn,
        )
    elif cfg.split_mw_model == "paraffin":
        split = split_plus_fraction_pedersen(
            z_plus=plus_fraction.z_plus,
            MW_plus=plus_fraction.mw_plus,
            n_start=plus_fraction.n_start,
            n_end=cfg.n_end,
        )
    else:
        raise CharacterizationError(
            f"Unknown split_mw_model '{cfg.split_mw_model}'. Use 'paraffin' or 'table'."
        )

    corr = _resolve_correlation(cfg.correlation)
    pseudo_props = corr.estimate(scn_props)

    pseudo_components: list[Component] = []
    pseudo_ids: list[str] = []
    for idx, n in enumerate(scn_props.n):
        comp_id = f"SCN{int(n)}"
        pseudo_ids.append(comp_id)
        pseudo_components.append(
            Component(
                name=comp_id,
                formula=comp_id,
                Tc=float(pseudo_props.Tc[idx]),
                Pc=float(pseudo_props.Pc[idx]),
                Vc=float(pseudo_props.Vc[idx]),
                omega=float(pseudo_props.omega[idx]),
                MW=float(scn_props.mw[idx]),
                Tb=float(scn_props.tb_k[idx]),
                note="Pseudo-component from SCN characterization",
            )
        )

    lumping_result: SCNLumpingResult | None = None
    z_pseudo = split.z
    pseudo_ids_final = pseudo_ids
    pseudo_components_final = pseudo_components

    if cfg.lumping_enabled:
        if cfg.lumping_method != "contiguous":
            raise CharacterizationError(
                f"Unsupported lumping_method '{cfg.lumping_method}'.",
                method=cfg.lumping_method,
            )

        lumping_result = _lump_scns_contiguous(
            scn_props=scn_props,
            scn_components=pseudo_components,
            scn_component_ids=pseudo_ids,
            scn_z=split.z,
            n_groups=cfg.lumping_n_groups,
            correlation=corr,
        )
        z_pseudo = lumping_result.lump_z
        pseudo_ids_final = lumping_result.lump_component_ids
        pseudo_components_final = lumping_result.lump_components

    component_ids = resolved_ids + list(pseudo_ids_final)
    components_full = resolved_components + list(pseudo_components_final)
    z_full = np.concatenate([z_resolved, z_pseudo])

    if not np.allclose(np.sum(z_full), 1.0, atol=cfg.normalization_tol):
        raise CharacterizationError(
            "Final composition does not sum to 1.0 after plus-fraction splitting.",
            composition_sum=float(z_full.sum()),
        )

    kij = _build_kij_matrix(
        component_ids,
        cfg.kij_overrides,
        cfg.kij_default,
        plus_fraction=plus_fraction,
        pseudo_component_ids=list(pseudo_ids_final),
    )

    return CharacterizationResult(
        component_ids=component_ids,
        components=components_full,
        composition=z_full,
        binary_interaction=kij,
        scn_properties=scn_props,
        split_result=split,
        plus_fraction=plus_fraction,
        lumping=lumping_result,
    )
