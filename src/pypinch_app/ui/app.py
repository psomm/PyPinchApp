"""Responsive Flet interface for local PyPinch analysis."""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from pypinch_app.core import (
    MEDIA,
    CsvParseError,
    medium_by_key,
    parse_streams_csv,
    validate_input,
)
from pypinch_app.core.models import PinchResult, StreamType
from pypinch_app.export import ExportKind, export_result_csv
from pypinch_app.ui.charts import (
    composite_chart,
    grand_composite_chart,
    temperature_interval_chart,
)
from pypinch_app.ui.state import FIELD_MODEL_NAMES, AppState, StreamDraft

MOBILE_MAX_WIDTH = 720
TABLE_MIN_WIDTH = 900
EDITOR_TABLE_MIN_WIDTH = 1200
CONTENT_MAX_WIDTH = 1200
DETAIL_VIEWS = (
    "Problem Table",
    "Heat Cascade",
    "Composite Curves",
    "Grand Composite Curve",
    "Temperature Intervals",
)
EXAMPLE_BUTTONS = (
    ("Beispiel 4 Ströme", ft.Icons.AUTO_AWESOME, "Original-PyPinch: streams.csv"),
    ("Beispiel 14 Ströme", ft.Icons.AUTO_AWESOME_MOTION, "Original-PyPinch: manystreams.csv"),
    (
        "Beispiel Milch",
        ft.Icons.LOCAL_DRINK,
        "Milchpasteurisation nach TLK Energy: ṁ = 2 kg/s, c_p = 4",
    ),
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


def _optional(value: float | None, unit: str) -> str:
    return "—" if value is None else f"{_format(value)} {unit}"


def _medium_label(key: str | None) -> str:
    medium = medium_by_key(key)
    return medium.label if medium is not None else "Benutzerdefiniert"


def _stream_table(page: ft.Page, result: PinchResult) -> ft.Control:
    rows = []
    for index, item in enumerate(result.streams, start=1):
        stream = item.stream
        sign = "−" if stream.stream_type is StreamType.HOT else "+"
        rows.append(
            (
                str(index),
                stream.stream_type.value,
                _medium_label(stream.medium) if stream.mass_flow_kg_s is not None else "CP direkt",
                _optional(stream.mass_flow_kg_s, "kg/s"),
                _optional(stream.specific_heat_kj_per_kg_k, "kJ/(kg·K)"),
                f"{_format(stream.cp_kw_per_c)} kW/°C",
                f"{_format(stream.supply_c)} → {_format(stream.target_c)} °C",
                f"{sign}{_format(stream.heat_flow_kw)} kW",
            )
        )
    return _data_view(
        page,
        ("Stream", "Typ", "Medium", "ṁ", "c_p", "CP = ṁ·c_p", "Supply → Target", "ΔḢ"),
        rows,
        title="Stream",
    )


def _overview(page: ft.Page, result: PinchResult) -> ft.Control:
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
                    _metric("Wärmerückgewinnung", f"{_format(result.heat_recovery_kw)} kW"),
                    _metric("Heizbedarf ohne WRG", f"{_format(result.cold_duty_kw)} kW"),
                    _metric("Kühlbedarf ohne WRG", f"{_format(result.hot_duty_kw)} kW"),
                ],
                run_spacing=12,
                spacing=12,
            ),
            ft.Text("Energiebilanz der Ströme", size=18, weight=ft.FontWeight.BOLD),
            ft.Text(
                "ΔḢ = ṁ · c_p · (T_target − T_supply) = CP · ΔT. Kalte Ströme nehmen "
                "Wärme auf (+), heiße geben Wärme ab (−). Konstantes c_p, kein Phasenwechsel.",
                size=12,
            ),
            _stream_table(page, result),
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

    def stream_labels(draft: StreamDraft, labels: dict[str, ft.Text]) -> None:
        labels["type"].value = draft.type_label
        if draft.uses_mass_flow:
            labels["cp"].value = _optional(draft.effective_cp, "kW/°C")
        labels["duty"].value = _optional(draft.heat_flow_kw, "kW")

    def make_stream_field(
        draft: StreamDraft,
        index: int,
        name: str,
        label: str,
        labels: dict[str, ft.Text],
        width: int | None,
    ) -> ft.TextField:
        issue_key = f"streams[{index}].{FIELD_MODEL_NAMES[name]}"

        def changed(e: ft.Event[ft.TextField]) -> None:
            state.update_stream(draft.id, name, e.control.value)
            e.control.error = None
            stream_labels(draft, labels)
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

    def make_medium_field(draft: StreamDraft, width: int | None) -> ft.Dropdown:
        def selected(e) -> None:
            state.update_medium(draft.id, e.control.value)
            render()

        return ft.Dropdown(
            label="Medium",
            value=draft.medium,
            options=[ft.DropdownOption(key=m.key, text=m.label) for m in MEDIA],
            on_select=selected,
            width=width,
            dense=True,
            key=f"stream-{draft.id}-medium",
        )

    def medium_hint(draft: StreamDraft) -> str:
        medium = medium_by_key(draft.medium)
        if medium is None:
            return ""
        if medium.specific_heat_kj_per_kg_k is None:
            return medium.note
        return f"Richtwert c_p = {medium.specific_heat_kj_per_kg_k} kJ/(kg·K), {medium.note}"

    def stream_inputs(
        draft: StreamDraft, index: int, labels: dict[str, ft.Text], width: int | None
    ) -> tuple[list[ft.Control], list[ft.Control]]:
        """Return (heat capacity inputs, temperature inputs) for one stream.

        Table rows (fixed width) use short labels; the header carries the units.
        """
        names = (
            ("ṁ", "c_p", "CP", "Supply", "Target")
            if width
            else ("ṁ (kg/s)", "c_p (kJ/(kg·K))", "CP (kW/°C)", "Supply (°C)", "Target (°C)")
        )
        if draft.uses_mass_flow:
            flow = [
                make_stream_field(draft, index, "mass_flow", names[0], labels, width),
                make_stream_field(draft, index, "specific_heat", names[1], labels, width),
            ]
        else:
            flow = [make_stream_field(draft, index, "cp", names[2], labels, width)]
        temperatures = [
            make_stream_field(draft, index, "supply", names[3], labels, width),
            make_stream_field(draft, index, "target", names[4], labels, width),
        ]
        return flow, temperatures

    def build_streams() -> ft.Control:
        if not state.drafts:
            return _card(
                ft.Text("Noch keine Streams. Füge einen hinzu oder importiere eine CSV-Datei.")
            )
        if (page.width or 1024) < EDITOR_TABLE_MIN_WIDTH:
            cards = []
            for index, draft in enumerate(state.drafts):
                labels = {
                    "type": ft.Text(color=ft.Colors.TEAL_700, weight=ft.FontWeight.BOLD),
                    "cp": ft.Text(),
                    "duty": ft.Text(),
                }
                stream_labels(draft, labels)
                summary = [ft.Text("Q̇ = |ΔḢ|:", color=ft.Colors.BLUE_GREY_600), labels["duty"]]
                if draft.uses_mass_flow:
                    summary = [
                        ft.Text("CP = ṁ·c_p:", color=ft.Colors.BLUE_GREY_600),
                        labels["cp"],
                        *summary,
                    ]
                flow, temperatures = stream_inputs(draft, index, labels, None)
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
                                        labels["type"],
                                    ]
                                ),
                                make_medium_field(draft, None),
                                ft.Text(medium_hint(draft), size=12),
                                *flow,
                                *temperatures,
                                ft.Row(summary, wrap=True),
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
                    ft.Text("Stream", width=50),
                    ft.Text("Medium", width=170),
                    ft.Text("ṁ (kg/s) · c_p (kJ/(kg·K))", width=232),
                    ft.Text("CP (kW/°C)", width=100),
                    ft.Text("Supply (°C)", width=110),
                    ft.Text("Target (°C)", width=110),
                    ft.Text("Typ", width=60),
                    ft.Text("Q̇ (kW)", width=90),
                ],
                spacing=12,
            )
        ]
        for index, draft in enumerate(state.drafts):
            labels = {
                "type": ft.Text(width=60, color=ft.Colors.TEAL_700),
                "cp": ft.Text(width=100),
                "duty": ft.Text(width=90),
            }
            stream_labels(draft, labels)
            flow, temperatures = stream_inputs(draft, index, labels, 110)
            if draft.uses_mass_flow:
                flow.append(labels["cp"])
            else:
                # Direct CP spans the ṁ, c_p and derived CP columns.
                flow[0].width = 344
            rows.append(
                ft.Row(
                    [
                        ft.Text(str(index + 1), width=50),
                        make_medium_field(draft, 170),
                        *flow,
                        *temperatures,
                        labels["type"],
                        labels["duty"],
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            tooltip="Löschen",
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

    def load_example(name: str) -> None:
        state.load_example(name)
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
                    "Je Strom Medium, Massenstrom ṁ und spezifische Wärmekapazität c_p angeben; "
                    "die App rechnet CP = ṁ · c_p (kg/s · kJ/(kg·K) = kW/°C). Das Medium füllt "
                    "einen c_p-Richtwert vor, der editierbar bleibt. Mit „CP direkt“ wird CP "
                    "ohne ṁ eingegeben. Temperaturen in °C; der Typ ergibt sich aus Supply "
                    "und Target."
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
                        *(
                            ft.Button(
                                content=name,
                                icon=icon,
                                tooltip=tooltip,
                                on_click=lambda _e, name=name: load_example(name),
                            )
                            for name, icon, tooltip in EXAMPLE_BUTTONS
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
            return _overview(page, state.result)
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

    def layout_mode() -> tuple[bool, bool, bool]:
        width = page.width or 1024
        return is_mobile(), width < TABLE_MIN_WIDTH, width < EDITOR_TABLE_MIN_WIDTH

    current_layout = layout_mode()

    def resized(_e) -> None:
        nonlocal current_layout
        current = layout_mode()
        if current != current_layout:
            current_layout = current
            render()

    page.on_resize = resized
    render()
