"""Flet chart controls fed only by solver result values."""

from __future__ import annotations

import math

import flet as ft
import flet_charts as fch

from pypinch_app.core.models import CompositeCurves, CurvePoint, PinchResult, StreamType

HOT_COLOR = ft.Colors.RED_600
COLD_COLOR = ft.Colors.BLUE_600


def _series(points: tuple[CurvePoint, ...], color: ft.Colors) -> fch.LineChartData:
    return fch.LineChartData(
        color=color,
        stroke_width=3,
        point=True,
        points=[fch.LineChartDataPoint(point.h_kw, point.temperature_c) for point in points],
    )


def _axis(values: list[float]) -> tuple[float, float, float, list[fch.ChartAxisLabel]]:
    minimum, maximum = min(values), max(values)
    if minimum == maximum:
        padding = max(abs(minimum) * 0.1, 1)
        minimum -= padding
        maximum += padding
    rough_step = (maximum - minimum) / 4
    magnitude = 10 ** math.floor(math.log10(rough_step))
    step = next(factor * magnitude for factor in (1, 2, 5, 10) if factor * magnitude >= rough_step)
    lower = math.floor(minimum / step) * step
    upper = math.ceil(maximum / step) * step
    ticks = round((upper - lower) / step)
    labels = [
        fch.ChartAxisLabel(value=lower + index * step, label=f"{lower + index * step:.4g}")
        for index in range(ticks + 1)
    ]
    return lower, upper, step, labels


def _line_chart(
    series: list[fch.LineChartData],
    y_label: str,
    height: int = 340,
    x_label: str = "Enthalpie / Wärmestrom (kW)",
) -> ft.Control:
    points = [point for item in series for point in item.points]
    if not points:
        return ft.Text("Keine Prozessströme für diese Kurve vorhanden.")

    def display_scale(values: list[float]) -> float:
        largest = max(abs(value) for value in values)
        if largest == 0 or 1e-6 <= largest <= 1e9:
            return 1.0
        return 10.0 ** math.floor(math.log10(largest)) or largest

    x_scale = display_scale([point.x for point in points])
    y_scale = display_scale([point.y for point in points])
    for item in series:
        item.points = [
            fch.LineChartDataPoint(point.x / x_scale, point.y / y_scale) for point in item.points
        ]
    min_x, max_x, _, x_labels = _axis([point.x / x_scale for point in points])
    min_y, max_y, y_step, y_labels = _axis([point.y / y_scale for point in points])
    if x_scale != 1:
        x_label += f" · Achsenwerte × {x_scale:.4g}"
    if y_scale != 1:
        y_label += f" · Achsenwerte × {y_scale:.4g}"
    return ft.Column(
        controls=[
            ft.Text(f"{y_label} ↑ · {x_label} →", size=11, color=ft.Colors.BLUE_GREY_600),
            fch.LineChart(
                data_series=series,
                min_x=min_x,
                max_x=max_x,
                min_y=min_y,
                max_y=max_y,
                left_axis=fch.ChartAxis(
                    labels=y_labels,
                    label_size=45,
                    title_size=0,
                    show_min=False,
                    show_max=False,
                ),
                bottom_axis=fch.ChartAxis(
                    labels=x_labels,
                    label_size=28,
                    title_size=0,
                    show_min=False,
                    show_max=False,
                ),
                horizontal_grid_lines=fch.ChartGridLines(interval=y_step),
                interactive=True,
                expand=True,
            ),
        ],
        height=height,
    )


def composite_chart(curves: CompositeCurves, shifted: bool) -> ft.Control:
    label = "Verschobene Temperatur (°C)" if shifted else "Temperatur (°C)"
    series = []
    if curves.hot:
        series.append(_series(curves.hot, HOT_COLOR))
    if curves.cold:
        series.append(_series(curves.cold, COLD_COLOR))
    return ft.Column(
        controls=[
            ft.Row(
                controls=[
                    ft.Text("● Hot", color=HOT_COLOR),
                    ft.Text("● Cold", color=COLD_COLOR),
                ],
                spacing=20,
            ),
            _line_chart(series, label),
        ]
    )


def grand_composite_chart(result: PinchResult) -> ft.Control:
    return _line_chart(
        [_series(result.grand_composite, ft.Colors.TEAL_700)],
        "Verschobene Temperatur (°C)",
    )


def temperature_interval_chart(result: PinchResult) -> ft.Control:
    """Show each shifted stream as a vertical segment at its stream number."""
    series = [
        fch.LineChartData(
            color=HOT_COLOR if stream.stream.stream_type is StreamType.HOT else COLD_COLOR,
            stroke_width=4,
            point=True,
            points=[
                fch.LineChartDataPoint(index, stream.supply_shifted_c),
                fch.LineChartDataPoint(index, stream.target_shifted_c),
            ],
        )
        for index, stream in enumerate(result.streams, start=1)
    ]
    return ft.Column(
        [
            ft.Row(
                [ft.Text("● Hot", color=HOT_COLOR), ft.Text("● Cold", color=COLD_COLOR)],
                spacing=20,
            ),
            _line_chart(
                series,
                "Verschobene Temperatur (°C)",
                x_label="Streamnummer",
            ),
        ]
    )
