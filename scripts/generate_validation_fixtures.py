"""Generate frozen PT flash outputs for validation fixtures."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root / "src"))

    from pvtcore.models.component import load_components
    from pvtcore.eos.peng_robinson import PengRobinsonEOS
    from pvtcore.flash.pt_flash import pt_flash

    fluids_dir = project_root / "tests" / "fixtures" / "fluids"
    expected_dir = project_root / "tests" / "fixtures" / "expected"
    expected_dir.mkdir(parents=True, exist_ok=True)

    components_db = load_components()

    for fluid_path in sorted(fluids_dir.glob("*.json")):
        with open(fluid_path, "r", encoding="utf-8") as f:
            fluid = json.load(f)

        comp_ids = [c["component_id"] for c in fluid["components"]]
        z = np.array([c["mole_fraction"] for c in fluid["components"]], dtype=float)
        comps = [components_db[cid] for cid in comp_ids]
        eos = PengRobinsonEOS(comps)

        points_out = []
        for point in fluid["pt_points"]:
            res = pt_flash(
                pressure=float(point["pressure_pa"]),
                temperature=float(point["temperature_k"]),
                composition=z,
                components=comps,
                eos=eos,
                binary_interaction=None,
            )
            points_out.append({
                "pressure_pa": float(point["pressure_pa"]),
                "temperature_k": float(point["temperature_k"]),
                "phase": res.phase,
                "vapor_fraction": float(res.vapor_fraction),
                "liquid_composition": [float(v) for v in res.liquid_composition],
                "vapor_composition": [float(v) for v in res.vapor_composition],
                "K_values": [float(v) for v in res.K_values],
                "status": getattr(res.status, "name", str(res.status)),
                "residual": float(res.residual),
            })

        out = {
            "fluid_id": fluid["fluid_id"],
            "component_ids": comp_ids,
            "points": points_out,
        }

        out_path = expected_dir / f"{fluid['fluid_id']}_pt_flash.json"
        out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"Wrote {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
