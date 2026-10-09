"""Compare the new pure solver with captured original results."""

import json
from pathlib import Path

import pytest

from pypinch_app.core import parse_streams_csv, solve_pinch

FIXTURES = Path(__file__).parent / "fixtures"


def curve_dict(points):
    return {"H": [point.h_kw for point in points], "T": [point.temperature_c for point in points]}


def legacy_shape(result):
    return {
        "delta_t_min_c": result.delta_t_min_c,
        "streams": [
            {
                "type": item.stream.stream_type.value,
                "cp": item.stream.cp_kw_per_c,
                "ts": item.stream.supply_c,
                "tt": item.stream.target_c,
                "ss": item.supply_shifted_c,
                "st": item.target_shifted_c,
            }
            for item in result.streams
        ],
        "temperatures": list(result.temperature_boundaries_shifted_c),
        "temperature_intervals": [
            {
                "t1": row.upper_shifted_c,
                "t2": row.lower_shifted_c,
                "streamNumbers": list(row.stream_indices),
            }
            for row in result.temperature_intervals
        ],
        "problem_table": [
            {"deltaS": row.delta_t_c, "deltaCP": row.delta_cp_kw_per_c, "deltaH": row.delta_h_kw}
            for row in result.problem_table
        ],
        "infeasible_cascade": [
            {"deltaH": row.delta_h_kw, "exitH": row.exit_h_kw} for row in result.infeasible_cascade
        ],
        "feasible_cascade": [
            {"deltaH": row.delta_h_kw, "exitH": row.exit_h_kw} for row in result.feasible_cascade
        ],
        "hot_utility_kw": result.hot_utility_kw,
        "cold_utility_kw": result.cold_utility_kw,
        "legacy_pinch_shifted_c": result.legacy_pinch_shifted_c,
        "shifted_composite": {
            "hot": curve_dict(result.shifted_composite.hot),
            "cold": curve_dict(result.shifted_composite.cold),
        },
        "composite": {
            "hot": curve_dict(result.composite.hot),
            "cold": curve_dict(result.composite.cold),
        },
        "grand_composite": curve_dict(result.grand_composite),
    }


def assert_close(actual, expected):
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            assert_close(actual[key], expected[key])
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for observed, wanted in zip(actual, expected, strict=True):
            assert_close(observed, wanted)
    elif isinstance(expected, (float, int)) and not isinstance(expected, bool):
        assert actual == pytest.approx(expected, rel=1e-10, abs=1e-10)
    else:
        assert actual == expected


@pytest.mark.parametrize("name", ["streams", "manystreams"])
def test_solver_matches_full_golden_fixture(name):
    data = parse_streams_csv((FIXTURES / f"{name}.csv").read_bytes())
    result = solve_pinch(data.streams, data.delta_t_min_c)
    expected = json.loads((FIXTURES / f"{name}.golden.json").read_text(encoding="utf-8"))
    if name == "streams":
        # Original PyPinch incorrectly starts the hot curve below every hot stream.
        # Its other curve points and all cascade/utility values remain unchanged.
        expected["shifted_composite"]["hot"]["T"][0] = 110
        expected["composite"]["hot"]["T"][0] = 120
    assert_close(legacy_shape(result), expected)
    assert result == solve_pinch(data.streams, data.delta_t_min_c)


def test_small_case_actual_pinch_temperatures():
    data = parse_streams_csv((FIXTURES / "streams.csv").read_bytes())
    result = solve_pinch(data.streams, data.delta_t_min_c)
    assert result.legacy_pinch_shifted_c == 250
    assert result.hot_pinch_c == 260
    assert result.cold_pinch_c == 240
