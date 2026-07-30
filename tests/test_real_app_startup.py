from pathlib import Path

from copilot.api.real_app import app


def test_real_app_exports_fastapi_app():
    assert app.title == "TradeEye Copilot"


def test_start_real_bat_launches_real_app():
    content = Path("start_real.bat").read_text(encoding="utf-8")

    assert "python -m pip install -e .[dev]" in content
    assert "uvicorn copilot.api.real_app:app --reload" in content
    assert "http://127.0.0.1:8000/" in content
