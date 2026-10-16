"""One mutable state object per Flet page; no module-level mutable data."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from pypinch_app.core import (
    CP_DIRECT,
    CUSTOM,
    AnalysisInput,
    InvalidInputError,
    PinchResult,
    ProcessStream,
    StreamType,
    ValidationIssue,
    medium_by_key,
    solve_pinch,
    validate_input,
)

EXAMPLE_STREAMS = (
    ProcessStream(1, 350, 120),
    ProcessStream(3, 260, 150),
    ProcessStream(2, 65, 310),
    ProcessStream(0.5, 100, 170),
)

# TLK Energy, "Pinch-Analyse": raw milk 15 → 95 °C, then cooled 95 → 5 °C,
# ṁ = 2 kg/s and c_p = 4 kJ/(kg·K) as stated in the article.
MILK_EXAMPLE_STREAMS = (
    ProcessStream.from_mass_flow(2, 4, 15, 95, "milk"),
    ProcessStream.from_mass_flow(2, 4, 95, 5, "milk"),
)

DEFAULT_MEDIUM = "water"

FIELD_MODEL_NAMES = {
    "cp": "cp_kw_per_c",
    "mass_flow": "mass_flow_kg_s",
    "specific_heat": "specific_heat_kj_per_kg_k",
    "supply": "supply_c",
    "target": "target_c",
}


def _parse(text: str) -> float | None:
    try:
        value = float(text.strip().replace(",", "."))
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _text(value: float | None) -> str:
    return "" if value is None else str(value)


def _default_specific_heat(medium: str) -> str:
    found = medium_by_key(medium)
    if found is None or found.specific_heat_kj_per_kg_k is None:
        return ""
    return str(found.specific_heat_kj_per_kg_k)


@dataclass
class StreamDraft:
    id: int
    cp: str = ""
    supply: str = ""
    target: str = ""
    medium: str = CP_DIRECT
    mass_flow: str = ""
    specific_heat: str = ""

    @property
    def uses_mass_flow(self) -> bool:
        return self.medium != CP_DIRECT

    @property
    def effective_cp(self) -> float | None:
        """CP = ṁ·c_p in kW/°C, or the directly entered CP."""
        if not self.uses_mass_flow:
            return _parse(self.cp)
        mass_flow = _parse(self.mass_flow)
        specific_heat = _parse(self.specific_heat)
        if mass_flow is None or specific_heat is None:
            return None
        return mass_flow * specific_heat

    @property
    def heat_flow_kw(self) -> float | None:
        """|ΔḢ| = CP·|T_target − T_supply| in kW."""
        cp = self.effective_cp
        supply = _parse(self.supply)
        target = _parse(self.target)
        if cp is None or supply is None or target is None:
            return None
        return cp * abs(target - supply)

    @property
    def type_label(self) -> str:
        try:
            supply = float(self.supply.replace(",", "."))
            target = float(self.target.replace(",", "."))
        except ValueError:
            return "—"
        if not math.isfinite(supply) or not math.isfinite(target):
            return "—"
        if supply > target:
            return StreamType.HOT.value
        if supply < target:
            return StreamType.COLD.value
        return "—"


def _number(text: str, field: str, label: str) -> tuple[float | None, ValidationIssue | None]:
    cleaned = text.strip().replace(",", ".")
    if not cleaned:
        return None, ValidationIssue(field, f"{label} fehlt.")
    try:
        value = float(cleaned)
    except ValueError:
        return None, ValidationIssue(field, f"{label} muss eine Zahl sein.")
    return value, None


@dataclass
class AppState:
    drafts: list[StreamDraft] = field(default_factory=list)
    delta_t_min_text: str = ""
    result: PinchResult | None = None
    result_stale: bool = False
    selected_section: int = 0
    selected_detail: str = "Problem Table"
    issues: dict[str, str] = field(default_factory=dict)
    status: str = ""
    _next_id: int = 1

    def add_stream(self) -> None:
        self.drafts.append(
            StreamDraft(
                self._next_id,
                medium=DEFAULT_MEDIUM,
                specific_heat=_default_specific_heat(DEFAULT_MEDIUM),
            )
        )
        self._next_id += 1
        self._mark_changed()

    def remove_stream(self, stream_id: int) -> None:
        self.drafts = [draft for draft in self.drafts if draft.id != stream_id]
        self._mark_changed()

    def update_stream(self, stream_id: int, field_name: str, value: str) -> None:
        for draft in self.drafts:
            if draft.id == stream_id:
                setattr(draft, field_name, value)
                self._mark_changed()
                return
        raise KeyError(stream_id)

    def update_medium(self, stream_id: int, medium: str) -> None:
        """Switch the medium and prefill its reference c_p, which stays editable."""
        for draft in self.drafts:
            if draft.id == stream_id:
                if medium != CP_DIRECT and not draft.uses_mass_flow and not draft.mass_flow:
                    # Keep the stream's CP when leaving direct input: CP = 1 kg/s · c_p.
                    cp = _parse(draft.cp)
                    default = _parse(_default_specific_heat(medium))
                    if cp is not None and default:
                        draft.mass_flow = str(cp / default)
                if medium == CP_DIRECT and draft.uses_mass_flow:
                    draft.cp = _text(draft.effective_cp)
                draft.medium = medium
                if medium not in (CP_DIRECT, CUSTOM):
                    draft.specific_heat = _default_specific_heat(medium)
                self._mark_changed()
                return
        raise KeyError(stream_id)

    def update_delta_t_min(self, value: str) -> None:
        self.delta_t_min_text = value
        self._mark_changed()

    def _mark_changed(self) -> None:
        if self.result is not None:
            self.result_stale = True
        self.issues.clear()
        self.status = ""

    def load_example(self) -> None:
        self.import_data(AnalysisInput(EXAMPLE_STREAMS, 20))

    def load_milk_example(self) -> None:
        self.import_data(AnalysisInput(MILK_EXAMPLE_STREAMS, 20))

    def import_data(self, data: AnalysisInput) -> None:
        self.drafts = []
        for index, s in enumerate(data.streams):
            draft = StreamDraft(
                self._next_id + index, str(s.cp_kw_per_c), str(s.supply_c), str(s.target_c)
            )
            if s.mass_flow_kg_s is not None:
                draft.medium = s.medium or CUSTOM
                draft.mass_flow = str(s.mass_flow_kg_s)
                draft.specific_heat = _text(s.specific_heat_kj_per_kg_k)
            self.drafts.append(draft)
        self._next_id += len(data.streams)
        self.delta_t_min_text = str(data.delta_t_min_c)
        self.result = None
        self.result_stale = False
        self.issues.clear()
        self.status = f"{len(data.streams)} Streams geladen. Werte können bearbeitet werden."
        self.selected_section = 0

    def parsed_input(self) -> tuple[AnalysisInput | None, tuple[ValidationIssue, ...]]:
        issues: list[ValidationIssue] = []
        delta, issue = _number(self.delta_t_min_text, "delta_t_min_c", "ΔTmin")
        if issue:
            issues.append(issue)
        streams: list[ProcessStream] = []
        for index, draft in enumerate(self.drafts):
            if draft.uses_mass_flow:
                fields = (
                    ("mass_flow", "Massenstrom"),
                    ("specific_heat", "c_p"),
                    ("supply", "Supply"),
                    ("target", "Target"),
                )
            else:
                fields = (("cp", "CP"), ("supply", "Supply"), ("target", "Target"))
            values = []
            for field_name, label in fields:
                value, issue = _number(
                    getattr(draft, field_name),
                    f"streams[{index}].{FIELD_MODEL_NAMES[field_name]}",
                    label,
                )
                if issue:
                    issues.append(issue)
                values.append(value)
            if all(value is not None for value in values):
                if draft.uses_mass_flow:
                    medium = None if draft.medium == CUSTOM else draft.medium
                    streams.append(ProcessStream.from_mass_flow(*values, medium))
                else:
                    streams.append(ProcessStream(*values))
        if issues:
            if len(self.drafts) < 2:
                issues.append(
                    ValidationIssue("streams", "Mindestens zwei Prozessströme sind erforderlich.")
                )
            return None, tuple(issues)
        assert delta is not None
        data = AnalysisInput(tuple(streams), delta)
        issues.extend(validate_input(data))
        return (data if not issues else None), tuple(issues)

    @property
    def can_analyze(self) -> bool:
        _, issues = self.parsed_input()
        return not issues

    def analyze(self) -> bool:
        data, issues = self.parsed_input()
        self.issues = {issue.field: issue.message for issue in issues}
        if data is None:
            self.status = "Bitte die markierten Eingaben korrigieren."
            return False
        try:
            self.result = solve_pinch(data.streams, data.delta_t_min_c)
        except InvalidInputError as exc:
            self.issues = {issue.field: issue.message for issue in exc.issues}
            self.status = "Analyse nicht möglich: Eingaben prüfen."
            return False
        self.result_stale = False
        self.selected_section = 1
        self.status = "Analyse abgeschlossen."
        return True
