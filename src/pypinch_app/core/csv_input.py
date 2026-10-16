"""Parse PyPinch CSV from text or bytes.

Row 2 selects the stream columns. The original format is ``CP, TSUPPLY, TTARGET``.
The mass-flow format is ``MEDIUM, MDOT, CPSPEC, TSUPPLY, TTARGET`` with MDOT in kg/s
and CPSPEC in kJ/(kg·K); MEDIUM or CPSPEC may be omitted, and an empty CPSPEC
cell uses the medium's reference value.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from .media import find_medium
from .models import AnalysisInput, ProcessStream

LEGACY_COLUMNS = ["CP", "TSUPPLY", "TTARGET"]
MASS_FLOW_COLUMNS = {"MEDIUM", "MDOT", "CPSPEC", "TSUPPLY", "TTARGET"}


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
    header = [cell.strip().upper() for cell in rows[1]] if len(rows) >= 2 else []
    mass_flow_format = (
        header != LEGACY_COLUMNS
        and set(header) <= MASS_FLOW_COLUMNS
        and len(set(header)) == len(header)
        and {"MDOT", "TSUPPLY", "TTARGET"} <= set(header)
        and bool({"MEDIUM", "CPSPEC"} & set(header))
    )
    if header != LEGACY_COLUMNS and not mass_flow_format:
        raise CsvParseError(
            2,
            "Erwartete Spalten: CP, TSUPPLY, TTARGET oder MEDIUM, MDOT, CPSPEC, TSUPPLY, TTARGET.",
        )

    streams: list[ProcessStream] = []
    for line, row in enumerate(rows[2:], start=3):
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) != len(header):
            raise CsvParseError(line, f"Jede Stream-Zeile braucht genau {len(header)} Werte.")
        if not mass_flow_format:
            streams.append(
                ProcessStream(
                    cp_kw_per_c=_number(row[0], line, "CP"),
                    supply_c=_number(row[1], line, "TSUPPLY"),
                    target_c=_number(row[2], line, "TTARGET"),
                )
            )
            continue
        cells = dict(zip(header, row, strict=True))
        medium = None
        if cells.get("MEDIUM", "").strip():
            medium = find_medium(cells["MEDIUM"])
            if medium is None:
                raise CsvParseError(line, f"Unbekanntes Medium: {cells['MEDIUM'].strip()}.")
        if cells.get("CPSPEC", "").strip():
            specific_heat = _number(cells["CPSPEC"], line, "CPSPEC")
        elif medium is not None and medium.specific_heat_kj_per_kg_k is not None:
            specific_heat = medium.specific_heat_kj_per_kg_k
        else:
            raise CsvParseError(line, "CPSPEC fehlt und das Medium hat keinen Richtwert.")
        streams.append(
            ProcessStream.from_mass_flow(
                _number(cells["MDOT"], line, "MDOT"),
                specific_heat,
                _number(cells["TSUPPLY"], line, "TSUPPLY"),
                _number(cells["TTARGET"], line, "TTARGET"),
                medium.key if medium is not None else None,
            )
        )
    return AnalysisInput(tuple(streams), delta_t_min_c)
