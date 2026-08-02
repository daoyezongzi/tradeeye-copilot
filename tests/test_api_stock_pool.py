from fastapi.testclient import TestClient

from copilot.api.app import AppMeta, create_app
from copilot.service.stock_pool import StockPoolItem


class StockPoolApiService:
    def __init__(self):
        self.items = [StockPoolItem(ts_code="603026.SH", name="石大胜华", industry="generic")]

    def get_meta(self):
        return AppMeta(coverage_count=len(self.items), company_names={item.ts_code: item.name for item in self.items if item.name}, tushare_ready=True, feishu_ready=False)

    def list_stock_pool(self):
        return self.items

    def upsert_stock_pool_item(self, item):
        stored = StockPoolItem(ts_code=item.ts_code.upper(), name=item.name, industry=item.industry)
        self.items = [existing for existing in self.items if existing.ts_code != stored.ts_code]
        self.items.append(stored)
        return stored

    def remove_stock_pool_item(self, ts_code):
        before = len(self.items)
        self.items = [item for item in self.items if item.ts_code != ts_code]
        return len(self.items) < before


def test_stock_pool_routes_list_add_and_remove_items():
    service = StockPoolApiService()
    client = TestClient(create_app(service))

    listed = client.get("/api/stock-pool")
    added = client.post("/api/stock-pool", json={"ts_code": "000001.sz", "name": "平安银行", "industry": "bank"})
    removed = client.delete("/api/stock-pool/603026.SH")

    assert listed.status_code == 200
    assert listed.json() == [{"ts_code": "603026.SH", "name": "石大胜华", "industry": "generic"}]
    assert added.status_code == 200
    assert added.json() == {"ts_code": "000001.SZ", "name": "平安银行", "industry": "bank"}
    assert removed.status_code == 200
    assert removed.json() == {"deleted": True}
