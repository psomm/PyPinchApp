import json
from pathlib import Path

import pytest

from pypinch_app.core import parse_streams_csv
from pypinch_app.ui.state import EXAMPLES, AppState

FIXTURES = Path(__file__).parent / "fixtures"


def test_csv_import_is_editable_and_reanalysis_marks_old_result_stale():
    state = AppState()
    imported = parse_streams_csv(
        "Tmin,20\nCP,TSUPPLY,TTARGET\n1,350,120\n3,260,150\n2,65,310\n0.5,100,170\n"
    )
    state.import_data(imported)
    assert len(state.drafts) == 4
    assert state.analyze()
    assert state.result.hot_utility_kw == 50
    state.update_stream(state.drafts[0].id, "cp", "1.5")
    assert state.result_stale
    assert state.analyze()
    assert not state.result_stale
    assert state.result.hot_utility_kw != 50


def test_incomplete_manual_rows_report_field_errors():
    state = AppState()
    state.add_stream()
    state.add_stream()
    state.update_delta_t_min("20")
    assert not state.can_analyze
    assert not state.analyze()
    # New streams default to water: c_p is prefilled, the mass flow is missing.
    assert "streams[0].mass_flow_kg_s" in state.issues
    assert "streams[0].specific_heat_kj_per_kg_k" not in state.issues


@pytest.mark.parametrize(
    ("name", "fixture"),
    [("Beispiel 4 Ströme", "streams"), ("Beispiel 14 Ströme", "manystreams")],
)
def test_builtin_examples_match_upstream_files_and_golden_results(name, fixture):
    expected = json.loads((FIXTURES / f"{fixture}.golden.json").read_text(encoding="utf-8"))
    assert EXAMPLES[name] == parse_streams_csv((FIXTURES / f"{fixture}.csv").read_bytes())
    state = AppState()
    state.load_example(name)
    assert len(state.drafts) == len(expected["streams"])
    assert state.analyze()
    assert state.result.hot_utility_kw == pytest.approx(expected["hot_utility_kw"])
    assert state.result.cold_utility_kw == pytest.approx(expected["cold_utility_kw"])
    assert state.result.legacy_pinch_shifted_c == expected["legacy_pinch_shifted_c"]
