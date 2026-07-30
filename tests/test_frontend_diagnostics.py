from pathlib import Path


def test_frontend_exposes_disclosure_scan_controls():
    html = Path("web/index.html").read_text(encoding="utf-8")
    js = Path("web/app.js").read_text(encoding="utf-8")

    assert "scan-disclosure-day" in html
    assert "diagnostic-status" in html
    assert "scanDisclosureDay(date)" in js
    assert "/api/scan/disclosure-day" in js
    assert "renderDiagnostics" in js
