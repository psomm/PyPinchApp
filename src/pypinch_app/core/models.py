"""Values and units shared by import, calculation, and presentation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class StreamType(StrEnum):
    HOT = "HOT"
    COLD = "COLD"


@dataclass(frozen=True)
class ProcessStream:
    cp_kw_per_c: float
    supply_c: float
    target_c: float

    @property
    def stream_type(self) -> StreamType | None:
        if self.supply_c > self.target_c:
            return StreamType.HOT
        if self.supply_c < self.target_c:
            return StreamType.COLD
        return None


@dataclass(frozen=True)
class AnalysisInput:
    streams: tuple[ProcessStream, ...]
    delta_t_min_c: float


@dataclass(frozen=True)
class ShiftedStream:
    stream: ProcessStream
    supply_shifted_c: float
    target_shifted_c: float


@dataclass(frozen=True)
class TemperatureInterval:
    upper_shifted_c: float
    lower_shifted_c: float
    stream_indices: tuple[int, ...]


@dataclass(frozen=True)
class ProblemRow:
    delta_t_c: float
    delta_cp_kw_per_c: float
    delta_h_kw: float


@dataclass(frozen=True)
class CascadeRow:
    delta_h_kw: float
    exit_h_kw: float


@dataclass(frozen=True)
class CurvePoint:
    h_kw: float
    temperature_c: float


@dataclass(frozen=True)
class CompositeCurves:
    hot: tuple[CurvePoint, ...]
    cold: tuple[CurvePoint, ...]


@dataclass(frozen=True)
class PinchResult:
    streams: tuple[ShiftedStream, ...]
    delta_t_min_c: float
    temperature_boundaries_shifted_c: tuple[float, ...]
    temperature_intervals: tuple[TemperatureInterval, ...]
    problem_table: tuple[ProblemRow, ...]
    infeasible_cascade: tuple[CascadeRow, ...]
    feasible_cascade: tuple[CascadeRow, ...]
    hot_utility_kw: float
    cold_utility_kw: float
    legacy_pinch_shifted_c: float
    shifted_composite: CompositeCurves
    composite: CompositeCurves
    grand_composite: tuple[CurvePoint, ...]

    @property
    def internal_pinch_shifted_c(self) -> float | None:
        """Use the legacy pinch only when it is an actual internal cascade zero."""
        scale = max(
            abs(self.hot_utility_kw),
            abs(self.cold_utility_kw),
            *(abs(row.delta_h_kw) for row in self.problem_table),
        )
        pinches = [
            temperature
            for row, temperature in zip(
                self.feasible_cascade[:-1], self.temperature_boundaries_shifted_c[1:-1], strict=True
            )
            if math.isclose(row.exit_h_kw, 0, rel_tol=0, abs_tol=scale * 1e-12)
        ]
        if self.legacy_pinch_shifted_c in pinches:
            return self.legacy_pinch_shifted_c
        return pinches[0] if pinches else None

    @property
    def has_internal_pinch(self) -> bool:
        return self.internal_pinch_shifted_c is not None

    @property
    def hot_pinch_c(self) -> float | None:
        pinch = self.internal_pinch_shifted_c
        return None if pinch is None else pinch + self.delta_t_min_c / 2

    @property
    def cold_pinch_c(self) -> float | None:
        pinch = self.internal_pinch_shifted_c
        return None if pinch is None else pinch - self.delta_t_min_c / 2
