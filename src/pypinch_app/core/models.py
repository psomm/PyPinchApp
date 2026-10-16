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
    """CP is the heat capacity flow rate ṁ·c_p; 1 kg/s · 1 kJ/(kg·K) = 1 kW/°C.

    Mass flow, specific heat capacity, and medium are optional provenance of CP.
    The solver only uses CP, so legacy CP-only streams behave unchanged.
    """

    cp_kw_per_c: float
    supply_c: float
    target_c: float
    mass_flow_kg_s: float | None = None
    specific_heat_kj_per_kg_k: float | None = None
    medium: str | None = None

    @classmethod
    def from_mass_flow(
        cls,
        mass_flow_kg_s: float,
        specific_heat_kj_per_kg_k: float,
        supply_c: float,
        target_c: float,
        medium: str | None = None,
    ) -> ProcessStream:
        return cls(
            mass_flow_kg_s * specific_heat_kj_per_kg_k,
            supply_c,
            target_c,
            mass_flow_kg_s,
            specific_heat_kj_per_kg_k,
            medium,
        )

    @property
    def heat_flow_kw(self) -> float:
        """Enthalpy flow change |ΔḢ| = ṁ·c_p·|ΔT| = CP·|ΔT| (constant c_p, no phase change)."""
        return self.cp_kw_per_c * abs(self.target_c - self.supply_c)

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
    def hot_duty_kw(self) -> float:
        """Heat released by all hot streams; cold utility without heat recovery."""
        return sum(
            item.stream.heat_flow_kw
            for item in self.streams
            if item.stream.stream_type is StreamType.HOT
        )

    @property
    def cold_duty_kw(self) -> float:
        """Heat absorbed by all cold streams; hot utility without heat recovery."""
        return sum(
            item.stream.heat_flow_kw
            for item in self.streams
            if item.stream.stream_type is StreamType.COLD
        )

    @property
    def heat_recovery_kw(self) -> float:
        """Maximum internal heat exchange at ΔTmin."""
        return self.cold_duty_kw - self.hot_utility_kw

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
