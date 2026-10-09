"""Numerical and single-sided cases outside the two upstream examples."""

import math

import pytest

from pypinch_app.core import InvalidInputError, ProcessStream, solve_pinch


def test_only_hot_or_cold_streams_have_expected_utility():
    hot = solve_pinch((ProcessStream(2, 150, 50), ProcessStream(1, 120, 60)), 20)
    assert hot.hot_utility_kw == pytest.approx(0)
    assert hot.cold_utility_kw == pytest.approx(260)
    assert not hot.has_internal_pinch
    assert hot.composite.cold == ()

    cold = solve_pinch((ProcessStream(2, 50, 150), ProcessStream(1, 60, 120)), 20)
    assert cold.hot_utility_kw == pytest.approx(260)
    assert cold.cold_utility_kw == pytest.approx(0)
    assert not cold.has_internal_pinch
    assert cold.composite.hot == ()


@pytest.mark.parametrize("delta_t_min", [0, 20, 500])
def test_negative_temperatures_and_delta_t_extremes_conserve_heat(delta_t_min):
    streams = (ProcessStream(2, -10, -80), ProcessStream(1, -100, 0))
    result = solve_pinch(streams, delta_t_min)
    hot_duty = 2 * 70
    cold_duty = 1 * 100
    assert result.cold_utility_kw - result.hot_utility_kw == pytest.approx(hot_duty - cold_duty)
    assert all(math.isfinite(point.h_kw) for point in result.grand_composite)


def test_overflow_is_reported_as_invalid_input():
    streams = (ProcessStream(1e308, 1e308, -1e308), ProcessStream(1, -1, 1))
    with pytest.raises(InvalidInputError):
        solve_pinch(streams, 20)


def test_decimal_rounding_keeps_internal_pinch_visible():
    streams = (
        ProcessStream(0.3, 0.7, -1.7),
        ProcessStream(0.1, -1.1, 2.4),
        ProcessStream(0.2, -1.8, 1.6),
    )
    result = solve_pinch(streams, 0)
    assert result.feasible_cascade[2].exit_h_kw == pytest.approx(0, abs=1e-15)
    assert result.has_internal_pinch
    assert result.hot_pinch_c == pytest.approx(-1.1)


def test_internal_pinch_uses_actual_cascade_zero_without_hot_utility():
    result = solve_pinch(
        (ProcessStream(1, 300, 200), ProcessStream(1, 100, 200), ProcessStream(1, 100, 0)),
        0,
    )
    assert result.legacy_pinch_shifted_c == 200
    assert result.hot_pinch_c == 100
    assert result.cold_pinch_c == 100


def test_composite_curves_start_at_their_own_stream_temperatures():
    result = solve_pinch((ProcessStream(1, 200, 100), ProcessStream(1, 20, 80)), 20)
    assert [(p.h_kw, p.temperature_c) for p in result.composite.hot] == [(0, 100), (100, 200)]
    assert [(p.h_kw, p.temperature_c) for p in result.composite.cold] == [(40, 20), (100, 80)]


def test_composite_curve_preserves_temperature_gaps_at_constant_enthalpy():
    result = solve_pinch((ProcessStream(1, 300, 200), ProcessStream(1, 100, 0)), 0)
    assert [(p.h_kw, p.temperature_c) for p in result.composite.hot] == [
        (0, 0),
        (100, 100),
        (100, 200),
        (200, 300),
    ]
    assert result.composite.cold == ()


def test_collapsed_shifted_temperatures_are_reported_as_invalid_input():
    with pytest.raises(InvalidInputError) as error:
        solve_pinch((ProcessStream(1, 1, 0), ProcessStream(1, 1, 0)), 1e17)
    assert error.value.issues[0].field == "delta_t_min_c"
