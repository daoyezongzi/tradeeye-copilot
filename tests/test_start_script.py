from pathlib import Path


def test_start_demo_bat_exists_and_launches_demo_app():
    script = Path("start_demo.bat")

    assert script.exists()
    content = script.read_text(encoding="utf-8")
    assert "uvicorn copilot.api.dev_app:app --reload" in content
    assert "http://127.0.0.1:8000/" in content
    assert "python -m pip install -e .[dev]" in content
