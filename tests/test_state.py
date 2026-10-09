from pypinch_app.core import parse_streams_csv
from pypinch_app.ui.state import AppState


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
    assert "streams[0].cp_kw_per_c" in state.issues
