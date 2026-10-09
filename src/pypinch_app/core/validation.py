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
        if not math.isfinite(stream.cp_kw_per_c):
            issues.append(ValidationIssue(f"{prefix}.cp_kw_per_c", "CP muss endlich sein."))
        elif stream.cp_kw_per_c <= 0:
            issues.append(ValidationIssue(f"{prefix}.cp_kw_per_c", "CP muss größer als 0 sein."))
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
