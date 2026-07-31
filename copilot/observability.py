from pydantic import BaseModel


class RuntimeStats(BaseModel):
    company_count: int = 0
    snapshot_fetch_count: int = 0

    def record_company(self) -> None:
        self.company_count += 1

    def record_snapshot_fetch(self) -> None:
        self.snapshot_fetch_count += 1

    def as_lines(self) -> list[str]:
        return [f"companies={self.company_count}", f"snapshot_fetches={self.snapshot_fetch_count}"]
