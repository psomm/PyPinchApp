"""Responsive Flet interface for local PyPinch analysis."""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from pypinch_app.core import CsvParseError, parse_streams_csv, validate_input
from pypinch_app.core.models import PinchResult
from pypinch_app.export import ExportKind, export_result_csv
from pypinch_app.ui.charts import (
    composite_chart,
    grand_composite_chart,
    temperature_interval_chart,
)
from pypinch_app.ui.state import AppState, StreamDraft

MOBILE_MAX_WIDTH = 720
TABLE_MIN_WIDTH = 900
CONTENT_MAX_WIDTH = 1200
DETAIL_VIEWS = (
    "Problem Table",
    "Heat Cascade",
    "Composite Curves",
    "Grand Composite Curve",
    "Temperature Intervals",
)
EXPORTS = (
    ("Problem Table", ExportKind.PROBLEM_TABLE),
    ("Heat Cascade", ExportKind.HEAT_CASCADE),
    ("Shifted Composite", ExportKind.SHIFTED_COMPOSITE),
    ("Composite", ExportKind.COMPOSITE),
    ("Grand Composite", ExportKind.GRAND_COMPOSITE),
)


def _format(value: float) -> str:
    if value != 0 and (abs(value) < 0.001 or abs(value) >= 1e9):
        return f"{value:.3g}"
    if round(value, 3) == 0:
        return "0"
    return f"{value:,.3f}".replace(",", " ").rstrip("0").rstrip(".")


def _card(content: ft.Control, *, padding: int = 18) -> ft.Control:
    return ft.Container(
        content=content,
        padding=padding,
        bgcolor=ft.Colors.WHITE,
        border_radius=16,
    )


def _metric(label: str, value: str) -> ft.Control:
    return ft.Container(
        content=ft.Column(
            [
                ft.Text(label, size=13, color=ft.Colors.BLUE_GREY_600),
                ft.Text(value, size=24, weight=ft.FontWeight.BOLD),
            ],
            spacing=4,
        ),
        padding=16,
        bgcolor=ft.Colors.WHITE,
        border_radius=14,
        col={
            ft.ResponsiveRowBreakpoint.XS: 6,
            ft.ResponsiveRowBreakpoint.MD: 4,
            ft.ResponsiveRowBreakpoint.LG: 3,
        },
    )


def _data_view(
    page: ft.Page, headers: tuple[str, ...], rows: list[tuple[str, ...]], *, title: str
) -> ft.Control:
    if (page.width or 0) < TABLE_MIN_WIDTH:
        return ft.Column(
            [
                _card(
                    ft.Column(
                        [ft.Text(f"{title} {index}", weight=ft.FontWeight.BOLD)]
                        + [
                            ft.Row(
                                [
                                    ft.Text(header, color=ft.Colors.BLUE_GREY_600),
                                    ft.Text(value, selectable=True),
                                ]
                            )
                            for header, value in zip(headers, row, strict=True)
                        ],
                        spacing=8,
                    )
                )
                for index, row in enumerate(rows, start=1)
            ],
            spacing=10,
        )
    return _card(
        ft.DataTable(
            columns=[ft.DataColumn(label=header) for header in headers],
            rows=[
                ft.DataRow(cells=[ft.DataCell(ft.Text(value, selectable=True)) for value in row])
                for row in rows
            ],
            column_spacing=25,
        )
    )


def _overview(result: PinchResult) -> ft.Control:
    pinch = (
        f"{_format(result.hot_pinch_c)} / {_format(result.cold_pinch_c)} °C"
        if result.hot_pinch_c is not None and result.cold_pinch_c is not None
        else "Kein interner Pinch"
    )
    return ft.Column(
        [
            ft.Text("Ergebnisübersicht", size=24, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Hot / Cold Pinch sind tatsächliche Temperaturen. Der Legacy-Wert ist verschoben.",
                size=12,
            ),
            ft.ResponsiveRow(
                controls=[
                    _metric("QH,min", f"{_format(result.hot_utility_kw)} kW"),
                    _metric("QC,min", f"{_format(result.cold_utility_kw)} kW"),
                    _metric("Hot / Cold Pinch", pinch),
                    _metric("ΔTmin", f"{_format(result.delta_t_min_c)} °C"),
                    _metric("Streams", str(len(result.streams))),
                ],
                run_spacing=12,
                spacing=12,
            ),
            _card(
                ft.Column(
                    [
                        ft.Text("Berechnungshinweis", weight=ft.FontWeight.BOLD),
                        ft.Text(
                            f"Original-PyPinch meldet den verschobenen Pinch-Wert "
                            f"S = {_format(result.legacy_pinch_shifted_c)} °C."
                        ),
                    ]
                )
            ),
        ],
        spacing=18,
    )


def _detail(page: ft.Page, result: PinchResult, selected: str) -> ft.Control:
    if selected == "Problem Table":
        rows = [
            (
                _format(interval.upper_shifted_c),
                _format(interval.lower_shifted_c),
                _format(row.delta_t_c),
                _format(row.delta_cp_kw_per_c),
                _format(row.delta_h_kw),
            )
            for interval, row in zip(
                result.temperature_intervals, result.problem_table, strict=True
            )
        ]
        return _data_view(
            page,
            ("Oben °C", "Unten °C", "ΔT °C", "ΔCP kW/°C", "ΔH kW"),
            rows,
            title="Intervall",
        )
    if selected == "Heat Cascade":
        return ft.Column(
            [
                ft.Text("Unzulässige Kaskade", size=18, weight=ft.FontWeight.BOLD),
                _data_view(
                    page,
                    ("ΔH kW", "Austritt kW"),
                    [
                        (_format(row.delta_h_kw), _format(row.exit_h_kw))
                        for row in result.infeasible_cascade
                    ],
                    title="Intervall",
                ),
                ft.Text("Zulässige Kaskade", size=18, weight=ft.FontWeight.BOLD),
                _data_view(
                    page,
                    ("ΔH kW", "Austritt kW"),
                    [
                        (_format(row.delta_h_kw), _format(row.exit_h_kw))
                        for row in result.feasible_cascade
                    ],
                    title="Intervall",
                ),
            ],
            spacing=14,
        )
    if selected == "Composite Curves":
        return ft.Column(
            [
                ft.Text("Composite Curves", size=18, weight=ft.FontWeight.BOLD),
                _card(composite_chart(result.composite, shifted=False)),
                ft.Text("Shifted Composite Curves", size=18, weight=ft.FontWeight.BOLD),
                _card(composite_chart(result.shifted_composite, shifted=True)),
            ],
            spacing=14,
        )
    if selected == "Grand Composite Curve":
        return ft.Column(
            [
                ft.Text("Grand Composite Curve", size=18, weight=ft.FontWeight.BOLD),
                _card(grand_composite_chart(result)),
            ],
            spacing=14,
        )
    return ft.Column(
        [
            _card(temperature_interval_chart(result)),
            _data_view(
                page,
                ("Oben verschoben °C", "Unten verschoben °C", "Aktive Streams"),
                [
                    (
                        _format(row.upper_shifted_c),
                        _format(row.lower_shifted_c),
                        ", ".join(str(index + 1) for index in row.stream_indices) or "—",
                    )
                    for row in result.temperature_intervals
                ],
                title="Intervall",
            ),
        ],
        spacing=14,
    )


def main(page: ft.Page) -> None:
    page.title = "PyPinch"
    page.bgcolor = ft.Colors.BLUE_GREY_50
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.TEAL_600)
    state = AppState()
    stale_notice = ft.Text(visible=False, color=ft.Colors.AMBER_900)
    status_text = ft.Text(size=13)
    analysis_button = ft.Button(content="Analyse starten", icon=ft.Icons.ANALYTICS)

    def is_mobile() -> bool:
        return (page.width or 1024) <= MOBILE_MAX_WIDTH

    def refresh_input_indicators() -> None:
        stale_notice.visible = state.result_stale
        stale_notice.value = "Eingaben geändert – Ergebnis veraltet. Bitte erneut analysieren."
        status_text.value = state.status
        analysis_button.disabled = not state.can_analyze
        page.update()

    def field_issue(field: str) -> str | None:
        _, issues = state.parsed_input()
        return next((issue.message for issue in issues if issue.field == field), None)

    def make_stream_field(
        draft: StreamDraft, index: int, name: str, label: str, type_text: ft.Text, width: int | None
    ) -> ft.TextField:
        model_name = {"cp": "cp_kw_per_c", "supply": "supply_c", "target": "target_c"}[name]
        issue_key = f"streams[{index}].{model_name}"

        def changed(e: ft.Event[ft.TextField]) -> None:
            state.update_stream(draft.id, name, e.control.value)
            e.control.error = None
            type_text.value = draft.type_label
            refresh_input_indicators()

        def blurred(e: ft.Event[ft.TextField]) -> None:
            e.control.error = field_issue(issue_key)
            page.update()

        return ft.TextField(
            label=label,
            value=getattr(draft, name),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=width,
            dense=True,
            on_change=changed,
            on_blur=blurred,
            error=state.issues.get(issue_key),
            key=f"stream-{draft.id}-{name}",
        )

    def build_streams() -> ft.Control:
        if not state.drafts:
            return _card(
                ft.Text("Noch keine Streams. Füge einen hinzu oder importiere eine CSV-Datei.")
            )
        if (page.width or 1024) < TABLE_MIN_WIDTH:
            cards = []
            for index, draft in enumerate(state.drafts):
                type_text = ft.Text(
                    draft.type_label, color=ft.Colors.TEAL_700, weight=ft.FontWeight.BOLD
                )
                cards.append(
                    _card(
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(
                                            f"Stream {index + 1}",
                                            weight=ft.FontWeight.BOLD,
                                            expand=True,
                                        ),
                                        type_text,
                                    ]
                                ),
                                make_stream_field(
                                    draft, index, "cp", "CP (kW/°C)", type_text, None
                                ),
                                make_stream_field(
                                    draft, index, "supply", "Supply (°C)", type_text, None
                                ),
                                make_stream_field(
                                    draft, index, "target", "Target (°C)", type_text, None
                                ),
                                ft.Button(
                                    content="Löschen",
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    on_click=lambda _e, sid=draft.id: remove_stream(sid),
                                ),
                            ],
                            spacing=10,
                        )
                    )
                )
            return ft.Column(cards, spacing=12)
        rows = [
            ft.Row(
                [
                    ft.Text("Stream", width=80),
                    ft.Text("CP (kW/°C)", width=140),
                    ft.Text("Supply (°C)", width=140),
                    ft.Text("Target (°C)", width=140),
                    ft.Text("Typ", width=70),
                ]
            )
        ]
        for index, draft in enumerate(state.drafts):
            type_text = ft.Text(draft.type_label, width=70, color=ft.Colors.TEAL_700)
            rows.append(
                ft.Row(
                    [
                        ft.Text(str(index + 1), width=80),
                        make_stream_field(draft, index, "cp", "CP", type_text, 140),
                        make_stream_field(draft, index, "supply", "Supply", type_text, 140),
                        make_stream_field(draft, index, "target", "Target", type_text, 140),
                        type_text,
                        ft.Button(
                            content="Löschen",
                            icon=ft.Icons.DELETE_OUTLINE,
                            on_click=lambda _e, sid=draft.id: remove_stream(sid),
                        ),
                    ],
                    spacing=12,
                )
            )
        return _card(ft.Column(rows, spacing=12))

    def delta_changed(e: ft.Event[ft.TextField]) -> None:
        state.update_delta_t_min(e.control.value)
        e.control.error = None
        refresh_input_indicators()

    def delta_blurred(e: ft.Event[ft.TextField]) -> None:
        e.control.error = field_issue("delta_t_min_c")
        page.update()

    def add_stream(_e=None) -> None:
        state.add_stream()
        render()

    def remove_stream(stream_id: int) -> None:
        state.remove_stream(stream_id)
        render()

    def analyze(_e=None) -> None:
        state.analyze()
        render()

    def load_example(_e=None) -> None:
        state.load_example()
        render()

    def import_result(e: ft.FilePickerResultEvent) -> None:
        if not e.files:
            return
        try:
            selected = e.files[0]
            if selected.bytes is None:
                raise CsvParseError(1, "Dateiinhalt konnte nicht gelesen werden.")
            data = parse_streams_csv(selected.bytes)
            issues = validate_input(data)
            if issues:
                raise CsvParseError(1, "; ".join(issue.message for issue in issues))
            state.import_data(data)
        except (CsvParseError, UnicodeError) as exc:
            state.status = str(exc)
        render()

    file_picker = ft.FilePicker(on_result=import_result)
    page.services.append(file_picker)

    def export_click(kind: ExportKind) -> Callable:
        async def handler(_e) -> None:
            if state.result is None or state.result_stale:
                return
            try:
                await file_picker.save_file(
                    file_name=f"pypinch_{kind.value}.csv",
                    file_type=ft.FilePickerFileType.CUSTOM,
                    allowed_extensions=["csv"],
                    src_bytes=export_result_csv(state.result, kind),
                )
                state.status = f"Export bereit: pypinch_{kind.value}.csv"
            except (OSError, ValueError) as exc:
                state.status = f"Export fehlgeschlagen: {exc}"
            render()

        return handler

    def build_editor() -> ft.Control:
        delta_field = ft.TextField(
            label="ΔTmin (°C)",
            value=state.delta_t_min_text,
            keyboard_type=ft.KeyboardType.NUMBER,
            width=220,
            on_change=delta_changed,
            on_blur=delta_blurred,
            error=state.issues.get("delta_t_min_c"),
            key="delta-t-min",
        )
        return ft.Column(
            [
                ft.Text("Prozessströme", size=24, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "CP in kW/°C, Temperaturen in °C. Der Typ ergibt sich aus Supply und Target."
                ),
                ft.Row(
                    [
                        ft.Button(
                            content="Stream hinzufügen", icon=ft.Icons.ADD, on_click=add_stream
                        ),
                        ft.Button(
                            content="CSV importieren",
                            icon=ft.Icons.UPLOAD_FILE,
                            action=ft.PickFiles(
                                file_picker,
                                file_type=ft.FilePickerFileType.CUSTOM,
                                allowed_extensions=["csv"],
                                with_data=True,
                            ),
                        ),
                        ft.Button(
                            content="Beispiel laden",
                            icon=ft.Icons.AUTO_AWESOME,
                            on_click=load_example,
                        ),
                    ],
                    wrap=True,
                    spacing=10,
                    run_spacing=10,
                ),
                delta_field,
                build_streams(),
                ft.Text(
                    state.issues.get("streams", ""),
                    color=ft.Colors.RED_600,
                    visible="streams" in state.issues,
                ),
                ft.Row([analysis_button], alignment=ft.MainAxisAlignment.END),
            ],
            spacing=16,
        )

    def set_section(index: int) -> None:
        state.selected_section = index
        render()

    def navigation(mobile: bool) -> ft.Control:
        destinations = [
            ft.NavigationRailDestination(icon=ft.Icons.EDIT, label="Eingabe"),
            ft.NavigationRailDestination(icon=ft.Icons.ANALYTICS, label="Übersicht"),
            ft.NavigationRailDestination(icon=ft.Icons.SHOW_CHART, label="Details"),
        ]
        if mobile:
            page.navigation_bar = ft.NavigationBar(
                destinations=[
                    ft.NavigationBarDestination(icon=ft.Icons.EDIT, label="Eingabe"),
                    ft.NavigationBarDestination(icon=ft.Icons.ANALYTICS, label="Übersicht"),
                    ft.NavigationBarDestination(icon=ft.Icons.SHOW_CHART, label="Details"),
                ],
                selected_index=state.selected_section,
                on_change=lambda e: set_section(e.control.selected_index),
            )
            return ft.Container()
        page.navigation_bar = None
        return ft.NavigationRail(
            destinations=destinations,
            selected_index=state.selected_section,
            on_change=lambda e: set_section(e.control.selected_index),
            label_type=ft.NavigationRailLabelType.ALL,
        )

    def build_content() -> ft.Control:
        if state.selected_section == 0:
            return build_editor()
        if state.result is None:
            return _card(ft.Text("Noch keine Analyse. Gib Streams ein oder lade ein Beispiel."))
        if state.selected_section == 1:
            return _overview(state.result)
        selector = ft.Dropdown(
            label="Ergebnisansicht",
            value=state.selected_detail,
            options=[ft.DropdownOption(key=name, text=name) for name in DETAIL_VIEWS],
            on_select=lambda e: select_detail(e.control.value),
            width=300 if not is_mobile() else None,
        )
        export_controls = [
            ft.Button(
                content=f"{label} CSV",
                icon=ft.Icons.DOWNLOAD,
                disabled=state.result_stale,
                on_click=export_click(kind),
            )
            for label, kind in EXPORTS
        ]
        return ft.Column(
            [
                ft.Text("Detaillierte Ergebnisse", size=24, weight=ft.FontWeight.BOLD),
                selector,
                _detail(page, state.result, state.selected_detail),
                ft.Text("CSV exportieren", size=18, weight=ft.FontWeight.BOLD),
                ft.Row(export_controls, wrap=True, spacing=8, run_spacing=8),
            ],
            spacing=18,
        )

    def select_detail(value: str) -> None:
        state.selected_detail = value
        render()

    def render() -> None:
        mobile = is_mobile()
        analysis_button.on_click = analyze
        analysis_button.disabled = not state.can_analyze
        stale_notice.visible = state.result_stale
        stale_notice.value = "Eingaben geändert – Ergebnis veraltet. Bitte erneut analysieren."
        status_text.value = state.status
        nav = navigation(mobile)
        body = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            "PyPinch", size=30, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800
                        )
                    ],
                ),
                stale_notice,
                status_text,
                build_content(),
                ft.Text(
                    "Nach PyPinch von Andrei Leonard Nicusan · GNU GPL v3",
                    size=11,
                    color=ft.Colors.BLUE_GREY_600,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            expand=True,
        )
        content = ft.Container(content=body, padding=16, expand=True)
        if not mobile:
            content = ft.Row([nav, ft.VerticalDivider(width=1), content], expand=True)
        page.controls.clear()
        page.add(ft.SafeArea(content=content, expand=True))
        page.update()

    def layout_mode() -> tuple[bool, bool]:
        return is_mobile(), (page.width or 1024) < TABLE_MIN_WIDTH

    current_layout = layout_mode()

    def resized(_e) -> None:
        nonlocal current_layout
        current = layout_mode()
        if current != current_layout:
            current_layout = current
            render()

    page.on_resize = resized
    render()
