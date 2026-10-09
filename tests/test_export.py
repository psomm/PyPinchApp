import csv
import io
from pathlib import Path

from pypinch_app.core import parse_streams_csv, solve_pinch
from pypinch_app.export import ExportKind, export_result_csv


def test_csv_exports_retain_all_curve_points_and_utilities():
    source = Path(__file__).parent / "fixtures" / "streams.csv"
    data = parse_streams_csv(source.read_bytes())
    result = solve_pinch(data.streams, data.delta_t_min_c)
    grand = list(
        csv.reader(io.StringIO(export_result_csv(result, ExportKind.GRAND_COMPOSITE).decode()))
    )
    assert len(grand) == len(result.grand_composite) + 1
    assert grand[0] == ["net_enthalpy_kw", "shifted_temperature_c"]
    assert grand[1] == [str(result.hot_utility_kw), str(result.grand_composite[0].temperature_c)]

    cascade = list(
        csv.reader(io.StringIO(export_result_csv(result, ExportKind.HEAT_CASCADE).decode()))
    )
    assert ["hot_utility_kw", "50.0"] in cascade
    assert ["cold_utility_kw", "85.0"] in cascade

    for kind in ExportKind:
        assert export_result_csv(result, kind)


def test_export_uses_corrected_composite_start_temperature():
    from pypinch_app.core import ProcessStream

    result = solve_pinch((ProcessStream(1, 200, 100), ProcessStream(1, 20, 80)), 20)
    rows = list(csv.reader(io.StringIO(export_result_csv(result, ExportKind.COMPOSITE).decode())))
    assert rows[2] == ["0.0", "100.0"]
    assert rows[3] == ["100.0", "200.0"]
