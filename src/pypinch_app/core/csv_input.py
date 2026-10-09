"""Parse the original PyPinch CSV format from text or bytes."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from .models import AnalysisInput, ProcessStream


@dataclass(frozen=True)
class CsvParseError(ValueError):
    line: int
    message: str

    def __str__(self) -> str:
        return f"CSV-Zeile {self.line}: {self.message}"


def _number(value: str, line: int, label: str) -> float:
    if not value.strip():
        raise CsvParseError(line, f"{label} fehlt.")
    try:
        return float(value)
    except ValueError as exc:
        raise CsvParseError(line, f"{label} muss eine Zahl sein.") from exc


def parse_streams_csv(data: bytes | str) -> AnalysisInput:
    if isinstance(data, bytes):
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise CsvParseError(1, "Datei muss UTF-8-kodiert sein.") from exc
    elif isinstance(data, str):
        text = data.lstrip("\ufeff")
    else:
        raise TypeError("CSV-Daten müssen bytes oder str sein.")

    try:
        rows = list(csv.reader(io.StringIO(text, newline="")))
    except csv.Error as exc:
        raise CsvParseError(1, "CSV konnte nicht gelesen werden.") from exc
    if not rows:
        raise CsvParseError(1, "Die Datei ist leer.")
    # The upstream examples use ``Tmin, 20, `` with one empty trailing cell.
    first_row = list(rows[0])
    while len(first_row) > 2 and not first_row[-1].strip():
        first_row.pop()
    if len(first_row) != 2 or first_row[0].strip() != "Tmin":
        raise CsvParseError(1, "Erwartet: Tmin,<Wert>.")
    delta_t_min_c = _number(first_row[1], 1, "Tmin")
    if len(rows) < 2 or [cell.strip() for cell in rows[1]] != ["CP", "TSUPPLY", "TTARGET"]:
        raise CsvParseError(2, "Erwartete Spalten: CP, TSUPPLY, TTARGET.")

    streams: list[ProcessStream] = []
    for line, row in enumerate(rows[2:], start=3):
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) != 3:
            raise CsvParseError(line, "Jede Stream-Zeile braucht genau drei Werte.")
        streams.append(
            ProcessStream(
                cp_kw_per_c=_number(row[0], line, "CP"),
                supply_c=_number(row[1], line, "TSUPPLY"),
                target_c=_number(row[2], line, "TTARGET"),
            )
        )
    return AnalysisInput(tuple(streams), delta_t_min_c)
