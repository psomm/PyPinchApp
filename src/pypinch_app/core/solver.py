"""Original PyPinch interval and cascade calculations, without I/O or plots."""

from __future__ import annotations

import math
from collections.abc import Sequence

from .models import (
    AnalysisInput,
    CascadeRow,
    CompositeCurves,
    CurvePoint,
    PinchResult,
    ProblemRow,
    ProcessStream,
    ShiftedStream,
    StreamType,
    TemperatureInterval,
)
from .validation import InvalidInputError, ValidationIssue, validate_input


def _finite(value: float, field: str) -> float:
    if not math.isfinite(value):
        raise InvalidInputError(
            (ValidationIssue(field, "Werte sind für eine stabile Berechnung zu groß."),)
        )
    return value


def solve_pinch(streams: Sequence[ProcessStream], delta_t_min_c: float) -> PinchResult:
    """Return all PyPinch targets; temperatures are °C and heat flows are kW.

    The legacy pinch value deliberately remains in shifted temperature space.
    Golden tests protect the original arithmetic and interval ordering.
    """
    data = AnalysisInput(tuple(streams), delta_t_min_c)
    issues = validate_input(data)
    if issues:
        raise InvalidInputError(issues)

    shifted: list[ShiftedStream] = []
    for index, stream in enumerate(data.streams):
        sign = -1 if stream.stream_type is StreamType.HOT else 1
        offset = sign * data.delta_t_min_c / 2
        supply = _finite(stream.supply_c + offset, f"streams[{index}].supply_c")
        target = _finite(stream.target_c + offset, f"streams[{index}].target_c")
        if supply == target:
            raise InvalidInputError(
                (
                    ValidationIssue(
                        "delta_t_min_c",
                        "ΔTmin ist im Verhältnis zur Temperaturspanne zu groß; "
                        "die verschobenen Temperaturen sind nicht mehr unterscheidbar.",
                    ),
                )
            )
        shifted.append(ShiftedStream(stream, supply, target))

    boundaries = sorted(
        {
            temperature
            for stream in shifted
            for temperature in (stream.supply_shifted_c, stream.target_shifted_c)
        },
        reverse=True,
    )
    intervals: list[TemperatureInterval] = []
    for upper, lower in zip(boundaries, boundaries[1:]):
        active: list[int] = []
        for index, item in enumerate(shifted):
            if item.stream.stream_type is StreamType.HOT:
                if item.supply_shifted_c >= upper and item.target_shifted_c <= lower:
                    active.append(index)
            elif item.target_shifted_c >= upper and item.supply_shifted_c <= lower:
                active.append(index)
        intervals.append(TemperatureInterval(upper, lower, tuple(active)))

    problem: list[ProblemRow] = []
    for interval in intervals:
        delta_t = _finite(interval.upper_shifted_c - interval.lower_shifted_c, "streams")
        delta_cp = 0.0
        for index in interval.stream_indices:
            cp = shifted[index].stream.cp_kw_per_c
            delta_cp += cp if shifted[index].stream.stream_type is StreamType.HOT else -cp
        problem.append(
            ProblemRow(
                delta_t,
                _finite(delta_cp, "streams"),
                _finite(delta_t * delta_cp, "streams"),
            )
        )

    infeasible: list[CascadeRow] = []
    exit_h = 0.0
    lowest_exit_h = 0.0
    pinch_interval = 0
    for index, row in enumerate(problem):
        exit_h = _finite(exit_h + row.delta_h_kw, "streams")
        infeasible.append(CascadeRow(row.delta_h_kw, exit_h))
        if exit_h < lowest_exit_h:
            lowest_exit_h = exit_h
            pinch_interval = index

    hot_utility = -lowest_exit_h
    feasible: list[CascadeRow] = []
    exit_h = hot_utility
    for row in problem:
        exit_h = _finite(exit_h + row.delta_h_kw, "streams")
        feasible.append(CascadeRow(row.delta_h_kw, exit_h))
    cold_utility = exit_h
    legacy_pinch = intervals[pinch_interval].lower_shifted_c

    hot_deltas: list[float] = []
    cold_deltas: list[float] = []
    for interval in intervals:
        hot_cp = 0.0
        cold_cp = 0.0
        for index in interval.stream_indices:
            stream = shifted[index].stream
            if stream.stream_type is StreamType.HOT:
                hot_cp += stream.cp_kw_per_c
            else:
                cold_cp += stream.cp_kw_per_c
        width = interval.upper_shifted_c - interval.lower_shifted_c
        hot_deltas.append(_finite(hot_cp * width, "streams"))
        cold_deltas.append(_finite(cold_cp * width, "streams"))

    def composite_points(deltas: list[float], initial_h: float) -> tuple[CurvePoint, ...]:
        points: list[CurvePoint] = []
        total_h = initial_h
        for interval, delta_h in zip(reversed(intervals), reversed(deltas), strict=True):
            if delta_h != 0:
                lower = CurvePoint(total_h, interval.lower_shifted_c)
                if not points or points[-1] != lower:
                    points.append(lower)
                total_h = _finite(total_h + delta_h, "streams")
                points.append(CurvePoint(total_h, interval.upper_shifted_c))
        return tuple(points)

    hot_points = composite_points(hot_deltas, 0.0)
    cold_points = composite_points(cold_deltas, cold_utility)
    shifted_composite = CompositeCurves(hot_points, cold_points)
    composite = CompositeCurves(
        tuple(CurvePoint(p.h_kw, p.temperature_c + data.delta_t_min_c / 2) for p in hot_points),
        tuple(CurvePoint(p.h_kw, p.temperature_c - data.delta_t_min_c / 2) for p in cold_points),
    )
    grand = [CurvePoint(hot_utility, boundaries[0])]
    grand.extend(
        CurvePoint(row.exit_h_kw, temperature)
        for row, temperature in zip(feasible, boundaries[1:], strict=True)
    )
    return PinchResult(
        streams=tuple(shifted),
        delta_t_min_c=data.delta_t_min_c,
        temperature_boundaries_shifted_c=tuple(boundaries),
        temperature_intervals=tuple(intervals),
        problem_table=tuple(problem),
        infeasible_cascade=tuple(infeasible),
        feasible_cascade=tuple(feasible),
        hot_utility_kw=hot_utility,
        cold_utility_kw=cold_utility,
        legacy_pinch_shifted_c=legacy_pinch,
        shifted_composite=shifted_composite,
        composite=composite,
        grand_composite=tuple(grand),
    )
