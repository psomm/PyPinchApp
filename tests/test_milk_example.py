"""Validate mass-flow input against the TLK Energy milk pasteurisation example.

Source: https://tlk-energy.de/blog/pinch-analyse — raw milk 15 → 95 °C, then
95 → 5 °C, ṁ = 2 kg/s, c_p = 4 kJ/(kg·K). Article values: CP = 8 kW/K,
heating 640 kW and cooling 720 kW without heat recovery, and at ΔT = 0 K a
maximum recovery of 640 kW with 80 kW cold utility remaining.
"""

from pathlib import Path

import pytest

from pypinch_app.core import ProcessStream, StreamType, parse_streams_csv, solve_pinch
from pypinch_app.ui.state import MILK_EXAMPLE_STREAMS, AppState

FIXTURES = Path(__file__).parent / "fixtures"


def test_cp_is_mass_flow_times_specific_heat():
    cold, hot = MILK_EXAMPLE_STREAMS
    assert cold.cp_kw_per_c == hot.cp_kw_per_c == 8
    assert cold.stream_type is StreamType.COLD
    assert hot.stream_type is StreamType.HOT
    # ΔḢ = ṁ·c_p·ΔT
    assert cold.heat_flow_kw == 2 * 4 * (95 - 15) == 640
    assert hot.heat_flow_kw == 2 * 4 * (95 - 5) == 720


def test_article_values_without_and_with_maximum_recovery():
    result = solve_pinch(MILK_EXAMPLE_STREAMS, 0)
    assert result.cold_duty_kw == 640  # hot utility without heat recovery
    assert result.hot_duty_kw == 720  # cold utility without heat recovery
    assert result.heat_recovery_kw == 640
    assert result.hot_utility_kw == 0
    assert result.cold_utility_kw == 80


def test_article_curve_shift_of_20_k():
    # Equal CP keeps ΔT = 20 K across the whole exchange range (pinch region).
    result = solve_pinch(MILK_EXAMPLE_STREAMS, 20)
    assert result.hot_utility_kw == 160
    assert result.cold_utility_kw == 240
    assert result.heat_recovery_kw == 480
    assert result.hot_utility_kw - result.cold_utility_kw == pytest.approx(640 - 720)


def test_mass_flow_csv_matches_example():
    data = parse_streams_csv((FIXTURES / "milk.csv").read_bytes())
    assert data.streams == MILK_EXAMPLE_STREAMS
    assert solve_pinch(data.streams, 0).cold_utility_kw == 80


def test_mass_flow_csv_uses_medium_reference_cp_when_cell_empty():
    data = parse_streams_csv("Tmin,10\nMEDIUM,MDOT,CPSPEC,TSUPPLY,TTARGET\nwasser,2,,20,80\n")
    assert data.streams[0].specific_heat_kj_per_kg_k == 4.19
    assert data.streams[0].cp_kw_per_c == pytest.approx(8.38)
    assert data.streams[0].medium == "water"


def test_editor_milk_example_and_medium_switch():
    state = AppState()
    state.load_example("Beispiel Milch")
    assert [d.medium for d in state.drafts] == ["milk", "milk"]
    assert state.drafts[0].effective_cp == 8
    assert state.drafts[0].heat_flow_kw == 640
    assert state.analyze()
    assert state.result.hot_utility_kw == 160
    state.update_medium(state.drafts[0].id, "water")
    assert state.drafts[0].specific_heat == "4.19"
    assert state.drafts[0].effective_cp == pytest.approx(8.38)
    state.update_medium(state.drafts[0].id, "cp_direct")
    assert float(state.drafts[0].cp) == pytest.approx(8.38)


def test_switching_legacy_stream_to_medium_keeps_cp():
    state = AppState()
    state.import_data(parse_streams_csv("Tmin,0\nCP,TSUPPLY,TTARGET\n8,95,5\n8,15,95\n"))
    state.update_medium(state.drafts[0].id, "milk")
    assert state.drafts[0].effective_cp == pytest.approx(8)
    assert state.drafts[0].specific_heat == "3.93"


def test_invalid_mass_flow_is_reported_on_its_field():
    state = AppState()
    state.add_stream()
    state.add_stream()
    state.update_delta_t_min("10")
    for draft, (mdot, ts, tt) in zip(state.drafts, (("0", "90", "20"), ("1", "10", "60"))):
        state.update_stream(draft.id, "mass_flow", mdot)
        state.update_stream(draft.id, "supply", ts)
        state.update_stream(draft.id, "target", tt)
    assert not state.analyze()
    assert set(state.issues) == {"streams[0].mass_flow_kg_s"}


def test_legacy_streams_keep_direct_cp_semantics():
    assert ProcessStream(1, 350, 120).mass_flow_kg_s is None
    assert ProcessStream(1, 350, 120).heat_flow_kw == 230
