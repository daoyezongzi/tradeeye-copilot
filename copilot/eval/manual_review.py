from pathlib import Path
import csv

from pydantic import BaseModel


class ReviewLabel(BaseModel):
    ts_code: str
    period: str
    rule_id: str
    label: str
    notes: str = ""
    severity: str | None = None
    industry: str | None = None


class PrecisionResult(BaseModel):
    reviewed_count: int
    true_positive_count: int
    false_positive_count: int
    precision_pct: float | None


class PrecisionBreakdown(BaseModel):
    overall: PrecisionResult
    by_rule: dict[str, PrecisionResult]
    by_severity: dict[str, PrecisionResult]
    by_industry: dict[str, PrecisionResult]


def load_review_labels(path: str | Path) -> list[ReviewLabel]:
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        return [ReviewLabel(**row) for row in csv.DictReader(f)]


def compute_precision(labels: list[ReviewLabel]) -> PrecisionResult:
    reviewed = [label for label in labels if label.label in {"TRUE", "FALSE"}]
    true_positive_count = sum(1 for label in reviewed if label.label == "TRUE")
    false_positive_count = sum(1 for label in reviewed if label.label == "FALSE")
    precision = None if not reviewed else true_positive_count / len(reviewed) * 100.0
    return PrecisionResult(
        reviewed_count=len(reviewed),
        true_positive_count=true_positive_count,
        false_positive_count=false_positive_count,
        precision_pct=None if precision is None else round(precision, 1),
    )


def _group_precision(labels: list[ReviewLabel], attr: str) -> dict[str, PrecisionResult]:
    grouped: dict[str, list[ReviewLabel]] = {}
    for label in labels:
        key = getattr(label, attr)
        if key:
            grouped.setdefault(str(key), []).append(label)
    return {key: compute_precision(group) for key, group in sorted(grouped.items())}


def compute_precision_breakdown(labels: list[ReviewLabel]) -> PrecisionBreakdown:
    return PrecisionBreakdown(
        overall=compute_precision(labels),
        by_rule=_group_precision(labels, "rule_id"),
        by_severity=_group_precision(labels, "severity"),
        by_industry=_group_precision(labels, "industry"),
    )
