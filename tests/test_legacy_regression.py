"""Golden checks against the isolated original solver."""

import json
from pathlib import Path

import pytest

from scripts.capture_legacy import capture

FIXTURES = Path(__file__).parent / "fixtures"


def assert_close(actual, expected):
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            assert_close(actual[key], expected[key])
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for observed, wanted in zip(actual, expected, strict=True):
            assert_close(observed, wanted)
    elif isinstance(expected, float):
        assert actual == pytest.approx(expected, rel=1e-10, abs=1e-10)
    else:
        assert actual == expected


@pytest.mark.parametrize("name", ["streams", "manystreams"])
def test_original_solver_matches_frozen_results(name):
    expected = json.loads((FIXTURES / f"{name}.golden.json").read_text(encoding="utf-8"))
    assert_close(capture(FIXTURES / f"{name}.csv"), expected)
