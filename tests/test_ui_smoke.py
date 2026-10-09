"""Construct the Flet page and exercise the example analysis without a Flutter build."""

from pathlib import Path
from types import SimpleNamespace

import flet as ft

from pypinch_app.ui.app import DETAIL_VIEWS, main


class FakePage:
    def __init__(self):
        self.width = 390
        self.services = []
        self.controls = []
        self.navigation_bar = None

    def add(self, *controls):
        self.controls.extend(controls)

    def update(self):
        pass


def walk(control):
    yield control
    child = getattr(control, "content", None)
    if isinstance(child, ft.Control):
        yield from walk(child)
    for child in getattr(control, "controls", ()):
        yield from walk(child)


def find_button(page, label):
    return next(
        control
        for root in page.controls
        for control in walk(root)
        if isinstance(control, ft.Button) and control.content == label
    )


def test_mobile_example_can_be_analyzed():
    page = FakePage()
    main(page)
    assert page.navigation_bar is not None
    find_button(page, "Analyse starten").on_click(None)
    assert any(
        isinstance(control, ft.Text) and "Bitte die markierten Eingaben" in (control.value or "")
        for root in page.controls
        for control in walk(root)
    )
    find_button(page, "Beispiel laden").on_click(None)
    assert not find_button(page, "Analyse starten").disabled
    find_button(page, "Analyse starten").on_click(None)
    assert page.navigation_bar.selected_index == 1
    assert any(
        isinstance(control, ft.Text) and "50 kW" in (control.value or "")
        for root in page.controls
        for control in walk(root)
    )


def test_desktop_details_construct_all_result_views():
    page = FakePage()
    page.width = 1100
    main(page)
    find_button(page, "Beispiel laden").on_click(None)
    find_button(page, "Analyse starten").on_click(None)
    rail = next(
        control
        for root in page.controls
        for control in walk(root)
        if isinstance(control, ft.NavigationRail)
    )
    rail.on_change(SimpleNamespace(control=SimpleNamespace(selected_index=2)))
    for view in DETAIL_VIEWS:
        selector = next(
            control
            for root in page.controls
            for control in walk(root)
            if isinstance(control, ft.Dropdown)
        )
        selector.on_select(SimpleNamespace(control=SimpleNamespace(value=view)))


def test_file_picker_result_populates_editor():
    page = FakePage()
    main(page)
    picker = page.services[0]
    csv_bytes = (Path(__file__).parent / "fixtures" / "streams.csv").read_bytes()
    picker.on_result(
        ft.FilePickerResultEvent(
            name="result",
            control=picker,
            files=[
                ft.FilePickerFile(id=1, name="streams.csv", size=len(csv_bytes), bytes=csv_bytes)
            ],
        )
    )
    values = [
        control.value
        for root in page.controls
        for control in walk(root)
        if isinstance(control, ft.TextField)
    ]
    assert "350.0" in values
    assert "310.0" in values
    assert len(values) == 13  # ΔTmin plus four editable three-field streams.


def test_resize_updates_editor_at_both_layout_breakpoints():
    page = FakePage()
    page.width = 1100
    main(page)
    find_button(page, "Beispiel laden").on_click(None)
    for width, expected_field_width, mobile in (
        (800, None, False),
        (390, None, True),
        (800, None, False),
        (1100, 140, False),
    ):
        page.width = width
        page.on_resize(None)
        fields = [
            c
            for root in page.controls
            for c in walk(root)
            if isinstance(c, ft.TextField) and c.key == "stream-1-cp"
        ]
        assert fields[0].width == expected_field_width
        assert (page.navigation_bar is not None) == mobile


def test_charts_construct_for_tiny_heat_flows_and_extreme_temperatures():
    from pypinch_app.core import ProcessStream, solve_pinch
    from pypinch_app.ui.charts import composite_chart, grand_composite_chart

    for streams in (
        (ProcessStream(1e-323, 2, 1), ProcessStream(1e-323, 0, 1)),
        (ProcessStream(1e-308, 1e308, 9e307), ProcessStream(1e-308, 8e307, 9e307)),
    ):
        result = solve_pinch(streams, 0)
        composite_chart(result.composite, False)
        grand_composite_chart(result)


def test_metrics_preserve_small_values_and_bound_large_number_width():
    from pypinch_app.ui.app import _format

    assert _format(1e-7) == "1e-07"
    assert _format(1e308) == "1e+308"
    assert _format(0) == "0"
