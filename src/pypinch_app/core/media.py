"""Reference specific heat capacities for common process media.

Values are mean c_p in kJ/(kg·K) near ambient pressure and typical process
temperatures. They are starting points for the input; c_p stays editable
because it depends on temperature, pressure, and composition.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Medium:
    key: str
    label: str
    specific_heat_kj_per_kg_k: float | None
    note: str = ""


CP_DIRECT = "cp_direct"
CUSTOM = "custom"

MEDIA = (
    Medium("water", "Wasser", 4.19, "flüssig, 20–100 °C"),
    Medium("milk", "Milch", 3.93, "Vollmilch, flüssig"),
    Medium("glycol_30", "Glykol-Wasser 30 %", 3.70, "Ethylenglykol, 20 °C"),
    Medium("thermal_oil", "Thermoöl", 2.20, "Mineralöl, 100–250 °C"),
    Medium("steam", "Wasserdampf", 2.03, "überhitzt, ~1 bar"),
    Medium("air", "Luft", 1.006, "trocken, ~1 bar"),
    Medium("flue_gas", "Rauchgas", 1.10, "Erdgasfeuerung"),
    Medium(CUSTOM, "Benutzerdefiniert", None, "c_p manuell eingeben"),
    Medium(CP_DIRECT, "CP direkt", None, "CP in kW/°C ohne ṁ und c_p"),
)

_BY_KEY = {medium.key: medium for medium in MEDIA}


def medium_by_key(key: str | None) -> Medium | None:
    return _BY_KEY.get(key or "")


def find_medium(name: str) -> Medium | None:
    """Match a CSV value against medium keys or German labels, ignoring case."""
    wanted = name.strip().casefold()
    return next(
        (m for m in MEDIA if wanted in (m.key.casefold(), m.label.casefold())),
        None,
    )
