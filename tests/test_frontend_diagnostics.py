from pathlib import Path


def test_frontend_keeps_disclosure_diagnostics_in_advanced_fold():
    html = Path("web/index.html").read_text(encoding="utf-8")
    js = Path("web/app.js").read_text(encoding="utf-8")

    # 诊断从顶级 tab 降为工作台折叠区，能力保留：容器与渲染函数都还在
    assert '<details id="adv-diagnostics"' in html
    assert 'id="diagnostic-status"' in html
    assert "renderDiagnostics" in js
    # 诊断数据随扫描 job 的 bundle 一起回来，不再单独调扫描接口
    assert "scanDisclosureDay(date)" not in js
    assert "/api/scan/disclosure-day" not in js


def test_old_diagnostics_hash_still_resolves():
    js = Path("web/app.js").read_text(encoding="utf-8")

    # 旧的 #/diagnostics 链接不失效：落到工作台并展开折叠区
    assert 'parts[0] === "diagnostics"' in js
    assert "expandDiagnostics" in js
    assert 'el("adv-diagnostics").open = true' in js
    assert "scrollIntoView" in js
