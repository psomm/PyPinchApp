"""One mutable state object per Flet page; no module-level mutable data."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from pypinch_app.core import (
    AnalysisInput,
    InvalidInputError,
    PinchResult,
    ProcessStream,
    StreamType,
    ValidationIssue,
    solve_pinch,
    validate_input,
)

EXAMPLE_STREAMS = (
    ProcessStream(1, 350, 120),
    ProcessStream(3, 260, 150),
    ProcessStream(2, 65, 310),
    ProcessStream(0.5, 100, 170),
)

FIELD_MODEL_NAMES = {"cp": "cp_kw_per_c", "supply": "supply_c", "target": "target_c"}


@dataclass
class StreamDraft:
    id: int
    cp: str = ""
    supply: str = ""
    target: str = ""

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
        self.drafts.append(StreamDraft(self._next_id))
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

    def import_data(self, data: AnalysisInput) -> None:
        self.drafts = [
            StreamDraft(self._next_id + index, str(s.cp_kw_per_c), str(s.supply_c), str(s.target_c))
            for index, s in enumerate(data.streams)
        ]
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
            values = []
            for field_name, label in (("cp", "CP"), ("supply", "Supply"), ("target", "Target")):
                value, issue = _number(
                    getattr(draft, field_name),
                    f"streams[{index}].{FIELD_MODEL_NAMES[field_name]}",
                    label,
                )
                if issue:
                    issues.append(issue)
                values.append(value)
            if all(value is not None for value in values):
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
