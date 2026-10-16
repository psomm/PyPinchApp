"""Field-addressable validation without UI dependencies."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .models import AnalysisInput


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    message: str


class InvalidInputError(ValueError):
    def __init__(self, issues: tuple[ValidationIssue, ...]):
        self.issues = issues
        super().__init__("; ".join(f"{issue.field}: {issue.message}" for issue in issues))


def validate_input(data: AnalysisInput) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []
    if len(data.streams) < 2:
        issues.append(
            ValidationIssue("streams", "Mindestens zwei Prozessströme sind erforderlich.")
        )
    if not math.isfinite(data.delta_t_min_c):
        issues.append(ValidationIssue("delta_t_min_c", "ΔTmin muss eine endliche Zahl sein."))
    elif data.delta_t_min_c < 0:
        issues.append(ValidationIssue("delta_t_min_c", "ΔTmin darf nicht negativ sein."))

    for index, stream in enumerate(data.streams):
        prefix = f"streams[{index}]"
        cp_field = f"{prefix}.cp_kw_per_c"
        if stream.mass_flow_kg_s is not None or stream.specific_heat_kj_per_kg_k is not None:
            # CP = ṁ·c_p is derived, so report problems on the fields the user edits.
            cp_field = f"{prefix}.mass_flow_kg_s"
            for field, label in (
                ("mass_flow_kg_s", "Massenstrom"),
                ("specific_heat_kj_per_kg_k", "c_p"),
            ):
                value = getattr(stream, field)
                if value is None or not math.isfinite(value):
                    issues.append(
                        ValidationIssue(f"{prefix}.{field}", f"{label} muss endlich sein.")
                    )
                    cp_field = None
                elif value <= 0:
                    issues.append(
                        ValidationIssue(f"{prefix}.{field}", f"{label} muss größer als 0 sein.")
                    )
                    cp_field = None
        if cp_field is None:
            pass  # The component error already explains why CP is unusable.
        elif not math.isfinite(stream.cp_kw_per_c):
            issues.append(ValidationIssue(cp_field, "CP muss endlich sein."))
        elif stream.cp_kw_per_c <= 0:
            issues.append(ValidationIssue(cp_field, "CP muss größer als 0 sein."))
        for field in ("supply_c", "target_c"):
            if not math.isfinite(getattr(stream, field)):
                issues.append(ValidationIssue(f"{prefix}.{field}", "Temperatur muss endlich sein."))
        if math.isfinite(stream.supply_c) and math.isfinite(stream.target_c):
            if stream.supply_c == stream.target_c:
                issues.append(
                    ValidationIssue(
                        f"{prefix}.target_c", "Supply und Target müssen verschieden sein."
                    )
                )
    return tuple(issues)
