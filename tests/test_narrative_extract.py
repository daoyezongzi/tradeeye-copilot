from copilot.narrative.extract import extract_management_section_from_text, pdf_cache_path


def test_pdf_cache_path_uses_ts_code_and_period(tmp_path):
    path = pdf_cache_path(tmp_path, "000001.SZ", "20250630")

    assert path == tmp_path / "000001.SZ_20250630.pdf"


def test_extract_management_section_from_text_prefers_management_discussion():
    text = "一、公司简介\n二、管理层讨论与分析\n经营承压但订单改善。\n三、公司治理\n治理内容"

    section = extract_management_section_from_text(text, max_chars=100)

    assert section == "管理层讨论与分析\n经营承压但订单改善。"


def test_extract_management_section_from_text_falls_back_to_future_outlook():
    text = "第一节 释义\n未来展望\n公司将提升现金回款。\n第十节 财务报告\n报表"

    section = extract_management_section_from_text(text, max_chars=100)

    assert section == "未来展望\n公司将提升现金回款。"


def test_extract_management_section_from_text_limits_chars():
    text = "管理层讨论与分析\n" + "经营" * 100

    section = extract_management_section_from_text(text, max_chars=11)

    assert section == "管理层讨论与分析\n经营"
