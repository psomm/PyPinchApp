"""Capture reference values from the unmodified upstream PyPinch solver."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY_PATH = ROOT / "vendor" / "original" / "PyPinch.py"


def load_legacy_class():
    spec = importlib.util.spec_from_file_location("legacy_pypinch", LEGACY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {LEGACY_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PyPinch


def capture(path: Path) -> dict:
    legacy_class = load_legacy_class()
    analysis = legacy_class(str(path))
    analysis.solve()
    return {
        "delta_t_min_c": analysis.tmin,
        "streams": analysis.streams.streamsData,
        "temperatures": analysis._temperatures,
        "temperature_intervals": analysis.temperatureInterval,
        "problem_table": analysis.problemTable,
        "infeasible_cascade": analysis.unfeasibleHeatCascade,
        "feasible_cascade": analysis.heatCascade,
        "hot_utility_kw": analysis.hotUtility,
        "cold_utility_kw": analysis.coldUtility,
        "legacy_pinch_shifted_c": analysis.pinchTemperature,
        "shifted_composite": analysis.shiftedCompositeDiagram,
        "composite": analysis.compositeDiagram,
        "grand_composite": analysis.grandCompositeCurve,
    }


if __name__ == "__main__":
    fixture_dir = ROOT / "tests" / "fixtures"
    for name in ("streams", "manystreams"):
        output = fixture_dir / f"{name}.golden.json"
        output.write_text(
            json.dumps(capture(fixture_dir / f"{name}.csv"), indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        print(output.relative_to(ROOT))
