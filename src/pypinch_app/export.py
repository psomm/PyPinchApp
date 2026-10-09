"""Create downloadable CSV content from an already computed result."""

from __future__ import annotations

import csv
import io
from enum import StrEnum

from .core.models import CompositeCurves, PinchResult


class ExportKind(StrEnum):
    PROBLEM_TABLE = "problem_table"
    HEAT_CASCADE = "heat_cascade"
    SHIFTED_COMPOSITE = "shifted_composite"
    COMPOSITE = "composite"
    GRAND_COMPOSITE = "grand_composite"


def _write_curve(writer: csv.writer, label: str, curves: CompositeCurves) -> None:
    for name, points in (("hot", curves.hot), ("cold", curves.cold)):
        writer.writerow([f"{label} {name}"])
        writer.writerow(["enthalpy_kw", "temperature_c"])
        writer.writerows((point.h_kw, point.temperature_c) for point in points)
        writer.writerow([])


def export_result_csv(result: PinchResult, kind: ExportKind) -> bytes:
    """Serialize result values to UTF-8 CSV bytes without filesystem access."""
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    if kind is ExportKind.PROBLEM_TABLE:
        writer.writerow(
            [
                "interval",
                "upper_shifted_c",
                "lower_shifted_c",
                "delta_t_c",
                "delta_cp_kw_per_c",
                "delta_h_kw",
            ]
        )
        for index, (interval, row) in enumerate(
            zip(result.temperature_intervals, result.problem_table, strict=True), start=1
        ):
            writer.writerow(
                [
                    index,
                    interval.upper_shifted_c,
                    interval.lower_shifted_c,
                    row.delta_t_c,
                    row.delta_cp_kw_per_c,
                    row.delta_h_kw,
                ]
            )
    elif kind is ExportKind.HEAT_CASCADE:
        writer.writerow(["cascade", "interval", "delta_h_kw", "exit_h_kw"])
        for label, rows in (
            ("infeasible", result.infeasible_cascade),
            ("feasible", result.feasible_cascade),
        ):
            writer.writerows(
                (label, index, row.delta_h_kw, row.exit_h_kw)
                for index, row in enumerate(rows, start=1)
            )
        writer.writerow(["hot_utility_kw", result.hot_utility_kw])
        writer.writerow(["cold_utility_kw", result.cold_utility_kw])
        writer.writerow(["legacy_pinch_shifted_c", result.legacy_pinch_shifted_c])
    elif kind is ExportKind.SHIFTED_COMPOSITE:
        _write_curve(writer, "shifted", result.shifted_composite)
    elif kind is ExportKind.COMPOSITE:
        _write_curve(writer, "actual", result.composite)
    elif kind is ExportKind.GRAND_COMPOSITE:
        writer.writerow(["net_enthalpy_kw", "shifted_temperature_c"])
        writer.writerows((point.h_kw, point.temperature_c) for point in result.grand_composite)
    else:
        raise ValueError(f"Unknown export kind: {kind}")
    return output.getvalue().encode("utf-8")
