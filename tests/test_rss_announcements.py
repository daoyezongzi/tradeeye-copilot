from copilot.rss.announcements import AnnouncementEvent, classify_announcement, parse_rss_entries


def test_classify_announcement_accepts_half_year_report():
    event = classify_announcement(
        title="平安银行：2025年半年度报告",
        link="https://example.com/a",
        company_to_ts_code={"平安银行": "000001.SZ"},
    )

    assert event == AnnouncementEvent(
        ts_code="000001.SZ",
        title="平安银行：2025年半年度报告",
        link="https://example.com/a",
        period="20250630",
        status="SEEN",
    )


def test_classify_announcement_excludes_summary_and_corrections():
    company_to_ts_code = {"平安银行": "000001.SZ"}

    assert classify_announcement("平安银行：2025年半年度报告摘要", "u", company_to_ts_code) is None
    assert classify_announcement("平安银行：2025年半年度报告更正公告", "u", company_to_ts_code) is None


def test_classify_announcement_infers_common_periods():
    company_to_ts_code = {"平安银行": "000001.SZ"}

    assert classify_announcement("平安银行：2025年年度报告", "u", company_to_ts_code).period == "20251231"
    assert classify_announcement("平安银行：2025年第一季度报告", "u", company_to_ts_code).period == "20250331"
    assert classify_announcement("平安银行：2025年第三季度报告", "u", company_to_ts_code).period == "20250930"


def test_parse_rss_entries_extracts_title_and_link():
    xml = """
    <rss><channel>
      <item><title>平安银行：2025年半年度报告</title><link>https://example.com/a</link></item>
      <item><title>其他公告</title><link>https://example.com/b</link></item>
    </channel></rss>
    """

    entries = parse_rss_entries(xml, max_entries=10)

    assert entries == [
        ("平安银行：2025年半年度报告", "https://example.com/a"),
        ("其他公告", "https://example.com/b"),
    ]
