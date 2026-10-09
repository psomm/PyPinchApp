"""Input format and domain validation at the shared core boundary."""

import math

import pytest

from pypinch_app.core import (
    CsvParseError,
    InvalidInputError,
    ProcessStream,
    StreamType,
    parse_streams_csv,
    solve_pinch,
    validate_input,
)
from pypinch_app.core.models import AnalysisInput


def test_csv_bytes_bom_and_derived_types():
    parsed = parse_streams_csv(
        b"\xef\xbb\xbfTmin, 0\r\nCP,TSUPPLY,TTARGET\r\n2,180,40\r\n1.5,20,150\r\n"
    )
    assert parsed.delta_t_min_c == 0
    assert [stream.stream_type for stream in parsed.streams] == [StreamType.HOT, StreamType.COLD]


def test_csv_accepts_upstream_tmin_trailing_empty_column():
    parsed = parse_streams_csv("Tmin, 20, \nCP, TSUPPLY, TTARGET\n1, 350, 120\n2, 65, 310\n")
    assert parsed.delta_t_min_c == 20
    assert len(parsed.streams) == 2


@pytest.mark.parametrize(
    ("data", "line"),
    [
        (b"", 1),
        (b"Tmin,20\nCP,TS,TT\n1,2,3", 2),
        (b"Tmin,20\nCP,TSUPPLY,TTARGET\n1,2", 3),
        (b"Tmin,20\nCP,TSUPPLY,TTARGET\nfoo,2,3", 3),
    ],
)
def test_csv_error_points_to_line(data, line):
    with pytest.raises(CsvParseError) as error:
        parse_streams_csv(data)
    assert error.value.line == line


def test_nonfinite_and_zero_span_are_field_errors():
    data = AnalysisInput((ProcessStream(math.nan, 100, 100), ProcessStream(1, math.inf, 5)), -1)
    fields = {issue.field for issue in validate_input(data)}
    assert fields == {
        "delta_t_min_c",
        "streams[0].cp_kw_per_c",
        "streams[0].target_c",
        "streams[1].supply_c",
    }
    with pytest.raises(InvalidInputError):
        solve_pinch(data.streams, data.delta_t_min_c)


def test_duplicate_streams_are_allowed():
    streams = (ProcessStream(2, 180, 40), ProcessStream(2, 180, 40))
    assert not validate_input(AnalysisInput(streams, 20))
    assert solve_pinch(streams, 20).cold_utility_kw > 0
