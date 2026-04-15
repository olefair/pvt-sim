#!/usr/bin/env python3
"""Populate numbered DWSIM streams from the canonical roster and export envelopes.

This helper is intentionally local and exploratory. DWSIM remains excluded from
the repo's active validation engine by policy; use this script for convenience
batching and spot-checking, not as the sole release authority.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Iterable, Mapping, Sequence


DEFAULT_DLL_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "DWSIM"
DEFAULT_ROSTER_PATH = Path(__file__).resolve().parent / "data" / "phase_envelope_breadth_roster.json"
DEFAULT_OUT_DIR = Path.home() / "Desktop" / "dwsim_phase_envelope_batch"

TABLE_COLUMNS = (
    "Tb_K",
    "Pb_Pa",
    "Hb_kJ_per_kg",
    "Sb_kJ_per_kgK",
    "Vb_m3_per_mol",
    "Td_K",
    "Pd_Pa",
    "Hd_kJ_per_kg",
    "Sd_kJ_per_kgK",
    "Vd_m3_per_mol",
)

SUMMARY_COLUMNS = (
    "tag",
    "name",
    "display_name",
    "family",
    "csv_path",
    "critical_T_K",
    "critical_P_Pa",
    "critical_V_m3_per_mol",
    "cricondenbar_T_K",
    "cricondenbar_P_Pa",
    "cricondentherm_T_K",
    "cricondentherm_P_Pa",
)

KNOWN_DWSIM_NAME_TO_COMPONENT_ID = {
    "Nitrogen": "N2",
    "Carbon dioxide": "CO2",
    "Hydrogen sulfide": "H2S",
    "Water": "H2O",
    "Methane": "C1",
    "Ethane": "C2",
    "Propane": "C3",
    "Isobutane": "iC4",
    "N-butane": "C4",
    "Isopentane": "iC5",
    "N-pentane": "C5",
    "Neopentane": "neoC5",
    "N-hexane": "C6",
    "N-heptane": "C7",
    "N-octane": "C8",
    "N-nonane": "C9",
    "N-decane": "C10",
    "N-undecane": "C11",
    "N-dodecane": "C12",
    "N-tridecane": "C13",
    "N-tetradecane": "C14",
    "N-pentadecane": "C15",
    "N-hexadecane": "C16",
    "N-heptadecane": "C17",
    "N-octadecane": "C18",
    "N-nonadecane": "C19",
    "N-eicosane": "C20",
}


@dataclass(frozen=True)
class RosterCase:
    tag: int
    name: str
    display_name: str
    family: str
    composition: dict[str, float]


def _load_runtime(dll_dir: Path):
    from pythonnet import load

    load("netfx")
    sys.path.append(str(dll_dir))

    import clr  # type: ignore

    clr.AddReference("System.Windows.Forms")
    for assembly_name in (
        "System",
        "DWSIM.Interfaces",
        "DWSIM.SharedClasses",
        "DWSIM.GlobalSettings",
        "DWSIM.Automation",
        "DWSIM.Thermodynamics",
    ):
        clr.AddReference(assembly_name)

    from System import Array, Double  # type: ignore
    from DWSIM.Automation import Automation3  # type: ignore
    from DWSIM.Thermodynamics.PropertyPackages import PhaseEnvelopeOptions  # type: ignore

    return Array, Double, Automation3, PhaseEnvelopeOptions


def _load_roster(path: Path) -> tuple[dict[str, str], list[RosterCase]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    dwsim_name_to_component_id = {
        str(entry["dwsim_name"]): str(entry["component_id"])
        for entry in raw["component_order"]
    }
    dwsim_name_to_component_id.update(KNOWN_DWSIM_NAME_TO_COMPONENT_ID)

    cases = [
        RosterCase(
            tag=int(case["tag"]),
            name=str(case["name"]),
            display_name=str(case["display_name"]),
            family=str(case["family"]),
            composition={str(key): float(value) for key, value in dict(case["composition"]).items()},
        )
        for case in raw["cases"]
    ]
    cases.sort(key=lambda case: case.tag)
    return dwsim_name_to_component_id, cases


def _invoke(obj, method_name: str, args: Sequence[object] = ()):
    method = obj.GetType().GetMethod(method_name)
    if method is None:
        raise AttributeError(f"{obj.GetType().FullName} has no method {method_name}")
    return method.Invoke(obj, list(args))


def _find_numeric_streams(flowsheet) -> dict[int, object]:
    found: dict[int, object] = {}
    for key in list(flowsheet.SimulationObjects.Keys):
        obj = flowsheet.SimulationObjects[key]
        tag = str(obj.GraphicObject.Tag)
        if tag.isdigit():
            found[int(tag)] = obj
    return found


def _find_property_package(flowsheet, package_name: str):
    for key in list(flowsheet.PropertyPackages.Keys):
        package = flowsheet.PropertyPackages[key]
        tag = str(package.Tag or "")
        if package_name.lower() in tag.lower():
            return package
    available = [str(flowsheet.PropertyPackages[key].Tag) for key in list(flowsheet.PropertyPackages.Keys)]
    raise RuntimeError(
        f"Could not find property package containing {package_name!r}. "
        f"Available tags: {available}"
    )


def _build_options(phase_envelope_options_type):
    options = phase_envelope_options_type()
    options.OperatingPoint = True
    options.QualityLine = False
    options.StabilityCurve = False
    options.PhaseIdentificationCurve = False
    options.Hydrate = False
    options.ImmiscibleWater = False
    options.BubbleUseCustomParameters = False
    options.DewUseCustomParameters = False
    return options


def _as_list(value) -> list:
    if value is None:
        return []
    return list(value)


def _phase_envelope_rows(raw_result) -> list[dict[str, float | None]]:
    arrays = [_as_list(item) for item in _as_list(raw_result)]
    if not arrays:
        return []
    max_rows = max(len(arrays[idx]) for idx in range(min(10, len(arrays))))
    rows: list[dict[str, float | None]] = []
    for row_index in range(max_rows):
        row: dict[str, float | None] = {}
        for col_index, column_name in enumerate(TABLE_COLUMNS):
            values = arrays[col_index] if col_index < len(arrays) else []
            row[column_name] = values[row_index] if row_index < len(values) else None
        rows.append(row)
    return rows


def _critical_tuple(raw_result) -> tuple[float | None, float | None, float | None]:
    arrays = [_as_list(item) for item in _as_list(raw_result)]
    if len(arrays) <= 15 or not arrays[15]:
        return (None, None, None)
    triple = list(arrays[15][0])
    return (
        float(triple[0]) if len(triple) > 0 else None,
        float(triple[1]) if len(triple) > 1 else None,
        float(triple[2]) if len(triple) > 2 else None,
    )


def _criconden_points(
    rows: Iterable[Mapping[str, float | None]],
) -> tuple[tuple[float | None, float | None], tuple[float | None, float | None]]:
    points: list[tuple[float, float]] = []
    for row in rows:
        if row["Tb_K"] is not None and row["Pb_Pa"] is not None:
            points.append((float(row["Tb_K"]), float(row["Pb_Pa"])))
        if row["Td_K"] is not None and row["Pd_Pa"] is not None:
            points.append((float(row["Td_K"]), float(row["Pd_Pa"])))
    if not points:
        return ((None, None), (None, None))
    cricondenbar = max(points, key=lambda pair: pair[1])
    cricondentherm = max(points, key=lambda pair: pair[0])
    return cricondenbar, cricondentherm


def _write_csv(path: Path, rows: Sequence[Mapping[str, float | None]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(TABLE_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)


def _case_vector(
    case: RosterCase,
    stream_compound_names: Sequence[str],
    dwsim_name_to_component_id: Mapping[str, str],
) -> list[float]:
    vector: list[float] = []
    present_component_ids: set[str] = set()
    for compound_name in stream_compound_names:
        component_id = dwsim_name_to_component_id.get(compound_name)
        if component_id is None:
            vector.append(0.0)
            continue
        value = float(case.composition.get(component_id, 0.0))
        vector.append(value)
        if value > 0.0:
            present_component_ids.add(component_id)

    missing = sorted(
        component_id
        for component_id, value in case.composition.items()
        if value > 0.0 and component_id not in present_component_ids
    )
    if missing:
        raise RuntimeError(
            f"Stream {case.tag} is missing components required by {case.name}: {missing}. "
            f"Loaded compounds: {list(stream_compound_names)}"
        )
    return vector


def _write_stream_composition(stream, composition: Sequence[float], array_type, double_type) -> None:
    _invoke(stream, "SetOverallComposition", [array_type[double_type](composition)])
    _invoke(stream, "NormalizeOverallMoleComposition")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Populate numbered DWSIM material streams from the canonical "
            "phase-envelope breadth roster and export local phase-envelope CSVs."
        )
    )
    parser.add_argument("--flowsheet", required=True, help="Path to a saved DWSIM .dwxmz/.xml flowsheet")
    parser.add_argument(
        "--dll-dir",
        default=str(DEFAULT_DLL_DIR),
        help="Directory containing the DWSIM .NET assemblies (defaults to %%LOCALAPPDATA%%\\DWSIM)",
    )
    parser.add_argument(
        "--roster",
        default=str(DEFAULT_ROSTER_PATH),
        help="Path to the canonical roster JSON file",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT_DIR),
        help="Output directory for CSV exports",
    )
    parser.add_argument(
        "--package",
        default="Peng-Robinson (PR)",
        help="Substring match for the flowsheet property package tag to use",
    )
    parser.add_argument(
        "--tags",
        nargs="*",
        help="Optional subset of numeric stream tags to process, for example --tags 2 4 11",
    )
    parser.add_argument(
        "--write-streams",
        action="store_true",
        help="Overwrite the selected numeric streams from the canonical roster before exporting envelopes",
    )
    parser.add_argument(
        "--save-flowsheet",
        help="Optional path to save the populated flowsheet after --write-streams",
    )
    parser.add_argument(
        "--populate-only",
        action="store_true",
        help="Write roster compositions and optionally save the flowsheet without exporting envelopes",
    )
    args = parser.parse_args()

    dll_dir = Path(args.dll_dir).expanduser().resolve()
    roster_path = Path(args.roster).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    flowsheet_path = Path(args.flowsheet).expanduser().resolve()

    dwsim_name_to_component_id, roster_cases = _load_roster(roster_path)
    selected_tags = {int(tag) for tag in args.tags} if args.tags else None
    selected_cases = [
        case for case in roster_cases if selected_tags is None or case.tag in selected_tags
    ]
    if not selected_cases:
        raise SystemExit("No roster cases selected.")

    array_type, double_type, automation_type, phase_envelope_options_type = _load_runtime(dll_dir)

    os.makedirs(out_dir, exist_ok=True)

    automation = automation_type()
    flowsheet = automation.LoadFlowsheet(str(flowsheet_path))
    numeric_streams = _find_numeric_streams(flowsheet)

    missing_streams = sorted(case.tag for case in selected_cases if case.tag not in numeric_streams)
    if missing_streams:
        raise SystemExit(
            f"Flowsheet is missing numeric material streams required by the roster: {missing_streams}"
        )

    if args.write_streams:
        for case in selected_cases:
            stream = numeric_streams[case.tag]
            stream_compound_names = [str(name) for name in _invoke(stream, "GetCompoundNames")]
            composition = _case_vector(case, stream_compound_names, dwsim_name_to_component_id)
            _write_stream_composition(stream, composition, array_type, double_type)
            print(f"wrote stream {case.tag:>2} {case.name}")

        if args.save_flowsheet:
            save_path = Path(args.save_flowsheet).expanduser().resolve()
            save_path.parent.mkdir(parents=True, exist_ok=True)
            automation.SaveFlowsheet2(flowsheet, str(save_path))
            print(f"saved populated flowsheet -> {save_path}")

    if args.populate_only:
        return 0

    package = _find_property_package(flowsheet, args.package)
    options = _build_options(phase_envelope_options_type)

    summary_rows: list[dict[str, object]] = []
    failure_rows: list[dict[str, object]] = []

    for case in selected_cases:
        stream = numeric_streams[case.tag]
        stream.PropertyPackage = package
        try:
            _invoke(package, "SetMaterial", [stream])
            raw_result = _invoke(package, "DW_ReturnPhaseEnvelope", [options, None])
            rows = _phase_envelope_rows(raw_result)

            csv_path = out_dir / f"{case.tag:02d}_{case.name}_phase_envelope.csv"
            _write_csv(csv_path, rows)

            critical_t, critical_p, critical_v = _critical_tuple(raw_result)
            cricondenbar, cricondentherm = _criconden_points(rows)
            summary_rows.append(
                {
                    "tag": case.tag,
                    "name": case.name,
                    "display_name": case.display_name,
                    "family": case.family,
                    "csv_path": str(csv_path),
                    "critical_T_K": critical_t,
                    "critical_P_Pa": critical_p,
                    "critical_V_m3_per_mol": critical_v,
                    "cricondenbar_T_K": cricondenbar[0],
                    "cricondenbar_P_Pa": cricondenbar[1],
                    "cricondentherm_T_K": cricondentherm[0],
                    "cricondentherm_P_Pa": cricondentherm[1],
                }
            )
            print(f"exported {case.tag:>2} {case.name} -> {csv_path}")
        except Exception as exc:  # pragma: no cover - depends on local DWSIM backend
            failure_rows.append(
                {
                    "tag": case.tag,
                    "name": case.name,
                    "display_name": case.display_name,
                    "family": case.family,
                    "error": str(exc),
                }
            )
            print(f"FAILED   {case.tag:>2} {case.name}: {exc}")

    summary_path = out_dir / "phase_envelope_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(SUMMARY_COLUMNS))
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"summary -> {summary_path}")

    if failure_rows:
        failure_path = out_dir / "phase_envelope_failures.csv"
        with failure_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["tag", "name", "display_name", "family", "error"],
            )
            writer.writeheader()
            writer.writerows(failure_rows)
        print(f"failures -> {failure_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
