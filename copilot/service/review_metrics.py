from copilot.eval.manual_review import PrecisionBreakdown, ReviewLabel, compute_precision_breakdown
from copilot.service.review_store import ReviewLabelStore, StoredReviewLabel


def _to_review_label(label: StoredReviewLabel) -> ReviewLabel:
    return ReviewLabel(
        ts_code=label.ts_code,
        period=label.period,
        rule_id=label.rule_id,
        label=label.label,
        notes=label.notes,
        severity=label.severity,
        industry=label.industry,
    )


class ReviewMetricsService:
    def __init__(self, store: ReviewLabelStore):
        self.store = store

    def compute_breakdown(self, ts_code: str | None = None, period: str | None = None) -> PrecisionBreakdown:
        labels = [_to_review_label(label) for label in self.store.list_labels(ts_code=ts_code, period=period)]
        return compute_precision_breakdown(labels)
