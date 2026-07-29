from typing import Protocol

from copilot.models import Context, PeriodSnapshot


class SnapshotSource(Protocol):
    def get_snapshot(self, ts_code: str, period: str) -> PeriodSnapshot | None: ...


_QUARTER_ENDS = ["0331", "0630", "0930", "1231"]


def prior_quarter_period(period: str) -> str:
    year = int(period[:4])
    suffix = period[4:]
    index = _QUARTER_ENDS.index(suffix)
    if index == 0:
        return f"{year - 1}1231"
    return f"{year}{_QUARTER_ENDS[index - 1]}"


def prior_year_period(period: str) -> str:
    return f"{int(period[:4]) - 1}{period[4:]}"


def assemble_context(source: SnapshotSource, ts_code: str, period: str) -> Context:
    current = source.get_snapshot(ts_code, period)
    if current is None:
        raise ValueError(f"current snapshot missing: {ts_code} {period}")
    return Context(
        ts_code=ts_code,
        current=current,
        prior_quarter=source.get_snapshot(ts_code, prior_quarter_period(period)),
        prior_year=source.get_snapshot(ts_code, prior_year_period(period)),
    )
