"""Schema-driven fluid definition parsing.

This module implements the canonical input contract described in
`docs/input_schema.md` and converts it into a characterization request
(`characterize_fluid(...)`).

The parser is intentionally strict: unsupported options raise an explicit
error rather than silently substituting behavior.
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..characterization.pipeline import (
    BinaryInteractionOverride,
    CharacterizationConfig,
    CharacterizationResult,
    PlusFractionSpec,
    characterize_fluid,
)
from ..core.errors import ConfigurationError, ValidationError


def _as_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"Expected object at '{path}'.", parameter=path, value=type(value).__name__)
    return value


def _as_sequence(value: Any, path: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValidationError(f"Expected list at '{path}'.", parameter=path, value=type(value).__name__)
    return value


def _get_required(obj: Mapping[str, Any], key: str, path: str) -> Any:
    if key not in obj:
        raise ValidationError(f"Missing required field '{path}.{key}'.", parameter=f"{path}.{key}")
    return obj[key]


def _get_optional(obj: Mapping[str, Any], key: str, default: Any) -> Any:
    return obj.get(key, default)


def _as_str(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"Expected string at '{path}'.", parameter=path, value=value)
    return value


def _as_int(value: Any, path: str) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"Expected integer at '{path}'.", parameter=path, value=value)
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"Expected integer at '{path}'.", parameter=path, value=value)


def _as_float(value: Any, path: str) -> float:
    if isinstance(value, bool):
        raise ValidationError(f"Expected number at '{path}'.", parameter=path, value=value)
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"Expected number at '{path}'.", parameter=path, value=value)


def _derive_aggregate_plus_from_tbp_cuts(cuts: Sequence[Any]) -> tuple[float, float]:
    """Derive aggregate plus-fraction z+ and MW+ from TBP cuts."""
    cuts_seq = _as_sequence(cuts, "fluid.plus_fraction.tbp_data.cuts")
    if not cuts_seq:
        raise ValidationError(
            "Expected at least one TBP cut.",
            parameter="fluid.plus_fraction.tbp_data.cuts",
            value=0,
        )

    total_z = 0.0
    total_zw = 0.0
    for i, item in enumerate(cuts_seq):
        item_path = f"fluid.plus_fraction.tbp_data.cuts[{i}]"
        item = _as_mapping(item, item_path)
        z = _as_float(_get_required(item, "z", item_path), f"{item_path}.z")
        mw = _as_float(_get_required(item, "mw", item_path), f"{item_path}.mw")
        if z < 0.0:
            raise ValidationError(
                "TBP cut mole fractions must be non-negative.",
                parameter=f"{item_path}.z",
                value=z,
            )
        if mw <= 0.0:
            raise ValidationError(
                "TBP cut molecular weights must be positive.",
                parameter=f"{item_path}.mw",
                value=mw,
            )
        total_z += z
        total_zw += z * mw

    if total_z <= 0.0:
        raise ValidationError(
            "Aggregate TBP cut mole fraction must be positive.",
            parameter="fluid.plus_fraction.tbp_data.cuts",
            value=total_z,
        )

    return total_z, total_zw / total_z


def _parse_target_end(target_end: str) -> int:
    target_end = target_end.strip()
    if not (target_end.startswith("C") and target_end.endswith("+")):
        raise ValidationError(
            "target_end must look like 'C45+' if provided.",
            parameter="fluid.plus_fraction.splitting.target_end",
            value=target_end,
        )
    n_str = target_end[1:-1]
    return _as_int(n_str, "fluid.plus_fraction.splitting.target_end")


def _map_critical_props(corr: str) -> str:
    corr = corr.strip().lower()
    if corr in {"riazi_daubert_1987", "riazi-daubert-1987", "riazi_daubert"}:
        return "riazi_daubert"
    raise ConfigurationError(
        "Unsupported critical property correlation.",
        config_key="fluid.correlations.critical_props",
        value=corr,
        supported=["riazi_daubert_1987"],
    )


def _map_split_mw_model(mw_model: str) -> str:
    mw_model_l = mw_model.strip().lower()
    if mw_model_l in {"paraffin", "mw_n = 14n - 4", "mwn = 14n - 4", "mwn=14n-4"}:
        return "paraffin"
    if "14" in mw_model_l and "n" in mw_model_l and "- 4" in mw_model_l:
        return "paraffin"
    if "table" in mw_model_l:
        return "table"
    raise ConfigurationError(
        "Unsupported Pedersen MW model.",
        config_key="fluid.plus_fraction.splitting.pedersen.mw_model",
        value=mw_model,
        supported=["MWn = 14n - 4", "table"],
    )


def load_fluid_definition(path: str | Path) -> dict[str, Any]:
    """Load a fluid definition document from JSON (and YAML if available)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))

    suffix = path.suffix.lower()
    if suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))

    if suffix in {".yml", ".yaml"}:
        try:
            import yaml  # type: ignore
        except Exception as e:  # pragma: no cover
            raise ConfigurationError(
                "YAML parsing requested but PyYAML is not installed.",
                config_key="io.yaml",
                path=str(path),
            ) from e
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    raise ConfigurationError(
        "Unsupported fluid definition file type. Use .json (or .yaml if PyYAML is installed).",
        config_key="io.file_type",
        value=suffix,
    )


def characterize_from_schema(doc: Mapping[str, Any]) -> CharacterizationResult:
    """Parse and characterize a fluid definition per `docs/input_schema.md`."""
    doc = _as_mapping(doc, "root")
    fluid = _as_mapping(_get_required(doc, "fluid", "root"), "fluid")

    basis = _as_str(_get_optional(fluid, "basis", "mole"), "fluid.basis")
    if basis != "mole":
        raise ConfigurationError(
            "Only mole-basis compositions are currently supported.",
            config_key="fluid.basis",
            value=basis,
            supported=["mole"],
        )

    comp_items = _as_sequence(_get_required(fluid, "components", "fluid"), "fluid.components")
    resolved: list[tuple[str, float]] = []
    for i, item in enumerate(comp_items):
        item_path = f"fluid.components[{i}]"
        item = _as_mapping(item, item_path)
        comp_id = _as_str(_get_required(item, "id", item_path), f"{item_path}.id")
        z = _as_float(_get_required(item, "z", item_path), f"{item_path}.z")
        resolved.append((comp_id, z))

    cfg = CharacterizationConfig()

    corr_block = _get_optional(fluid, "correlations", {})
    if corr_block:
        corr_block = _as_mapping(corr_block, "fluid.correlations")
        critical = _get_optional(corr_block, "critical_props", None)
        if critical is not None:
            cfg = replace(cfg, correlation=_map_critical_props(_as_str(critical, "fluid.correlations.critical_props")))

    plus_spec: PlusFractionSpec | None = None
    plus_block = _get_optional(fluid, "plus_fraction", None)
    if plus_block is not None:
        plus_block = _as_mapping(plus_block, "fluid.plus_fraction")
        label = _as_str(_get_optional(plus_block, "label", "C7+"), "fluid.plus_fraction.label")
        cut_start = _as_int(_get_required(plus_block, "cut_start", "fluid.plus_fraction"), "fluid.plus_fraction.cut_start")

        tbp_data = _get_optional(plus_block, "tbp_data", None)
        if tbp_data is None:
            z_plus = _as_float(
                _get_required(plus_block, "z_plus", "fluid.plus_fraction"),
                "fluid.plus_fraction.z_plus",
            )
            mw_plus = _as_float(
                _get_required(plus_block, "mw_plus_g_per_mol", "fluid.plus_fraction"),
                "fluid.plus_fraction.mw_plus_g_per_mol",
            )
        else:
            tbp_data = _as_mapping(tbp_data, "fluid.plus_fraction.tbp_data")
            tbp_cuts = _get_required(tbp_data, "cuts", "fluid.plus_fraction.tbp_data")
            z_plus, mw_plus = _derive_aggregate_plus_from_tbp_cuts(tbp_cuts)

            if "z_plus" in plus_block:
                explicit_z_plus = _as_float(plus_block["z_plus"], "fluid.plus_fraction.z_plus")
                if abs(explicit_z_plus - z_plus) > 1e-8:
                    raise ConfigurationError(
                        "Explicit z_plus conflicts with TBP-cut aggregate mole fraction.",
                        config_key="fluid.plus_fraction.z_plus",
                        value=explicit_z_plus,
                    )
            if "mw_plus_g_per_mol" in plus_block:
                explicit_mw_plus = _as_float(
                    plus_block["mw_plus_g_per_mol"],
                    "fluid.plus_fraction.mw_plus_g_per_mol",
                )
                if abs(explicit_mw_plus - mw_plus) > 1e-8:
                    raise ConfigurationError(
                        "Explicit mw_plus_g_per_mol conflicts with TBP-cut aggregate molecular weight.",
                        config_key="fluid.plus_fraction.mw_plus_g_per_mol",
                        value=explicit_mw_plus,
                    )

        sg_plus = None
        if "sg_plus_60F" in plus_block:
            sg_plus = _as_float(plus_block["sg_plus_60F"], "fluid.plus_fraction.sg_plus_60F")

        plus_spec = PlusFractionSpec(
            z_plus=z_plus,
            mw_plus=mw_plus,
            sg_plus=sg_plus,
            label=label,
            n_start=cut_start,
        )

        splitting = _get_optional(plus_block, "splitting", {})
        splitting = _as_mapping(splitting, "fluid.plus_fraction.splitting")

        split_method = _as_str(_get_optional(splitting, "method", "pedersen"), "fluid.plus_fraction.splitting.method")
        if split_method != "pedersen":
            raise ConfigurationError(
                "Unsupported plus-fraction splitting method.",
                config_key="fluid.plus_fraction.splitting.method",
                value=split_method,
                supported=["pedersen"],
            )
        cfg = replace(cfg, split_method=split_method)

        n_end = None
        if "max_carbon_number" in splitting:
            n_end = _as_int(splitting["max_carbon_number"], "fluid.plus_fraction.splitting.max_carbon_number")
        elif "target_end" in splitting:
            n_end = _parse_target_end(_as_str(splitting["target_end"], "fluid.plus_fraction.splitting.target_end"))
        if n_end is not None:
            cfg = replace(cfg, n_end=n_end)

        ped = _get_optional(splitting, "pedersen", {})
        ped = _as_mapping(ped, "fluid.plus_fraction.splitting.pedersen")
        mw_model = _as_str(
            _get_optional(ped, "mw_model", "MWn = 14n - 4"),
            "fluid.plus_fraction.splitting.pedersen.mw_model",
        )
        cfg = replace(cfg, split_mw_model=_map_split_mw_model(mw_model))

        solve_ab_from = _as_str(
            _get_optional(ped, "solve_AB_from", "balances"),
            "fluid.plus_fraction.splitting.pedersen.solve_AB_from",
        )
        if solve_ab_from.strip().lower() != "balances":
            raise ConfigurationError(
                "Unsupported Pedersen A/B solver option.",
                config_key="fluid.plus_fraction.splitting.pedersen.solve_AB_from",
                value=solve_ab_from,
                supported=["balances"],
            )

        lumping = _get_optional(plus_block, "lumping", {})
        lumping = _as_mapping(lumping, "fluid.plus_fraction.lumping")
        enabled = bool(_get_optional(lumping, "enabled", False))
        if enabled:
            n_groups = _as_int(
                _get_optional(lumping, "n_groups", cfg.lumping_n_groups),
                "fluid.plus_fraction.lumping.n_groups",
            )
            method = _as_str(_get_optional(lumping, "method", "contiguous"), "fluid.plus_fraction.lumping.method")
            if method != "contiguous":
                raise ConfigurationError(
                    "Unsupported lumping method.",
                    config_key="fluid.plus_fraction.lumping.method",
                    value=method,
                    supported=["contiguous"],
                )
            cfg = replace(cfg, lumping_enabled=True, lumping_n_groups=n_groups, lumping_method=method)
        else:
            cfg = replace(cfg, lumping_enabled=False)

    eos_block = _get_optional(fluid, "eos", {})
    eos_block = _as_mapping(eos_block, "fluid.eos")
    kij_block = _get_optional(eos_block, "kij", {})
    kij_block = _as_mapping(kij_block, "fluid.eos.kij")
    overrides = _get_optional(kij_block, "overrides", [])
    overrides_seq = _as_sequence(overrides, "fluid.eos.kij.overrides")
    kij_overrides: list[BinaryInteractionOverride] = []
    for i, o in enumerate(overrides_seq):
        o_path = f"fluid.eos.kij.overrides[{i}]"
        o = _as_mapping(o, o_path)
        pair = _as_sequence(_get_required(o, "pair", o_path), f"{o_path}.pair")
        if len(pair) != 2:
            raise ValidationError(
                "kij override pair must have two entries.",
                parameter=f"{o_path}.pair",
                value=len(pair),
            )
        a = _as_str(pair[0], f"{o_path}.pair[0]")
        b = _as_str(pair[1], f"{o_path}.pair[1]")
        kij_val = _as_float(_get_required(o, "kij", o_path), f"{o_path}.kij")
        kij_overrides.append(BinaryInteractionOverride(component_i=a, component_j=b, kij=kij_val))

    if kij_overrides:
        cfg = replace(cfg, kij_overrides=tuple(kij_overrides))

    return characterize_fluid(resolved, plus_fraction=plus_spec, config=cfg)
