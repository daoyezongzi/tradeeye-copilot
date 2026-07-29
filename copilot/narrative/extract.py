from pathlib import Path
import re

import fitz


_START_PATTERNS = [
    r"管理层讨论与分析",
    r"经营情况讨论与分析",
    r"未来展望",
    r"公司未来发展的展望",
]

_END_PATTERNS = [
    r"三、公司治理",
    r"公司治理",
    r"重要事项",
    r"财务报告",
    r"第十节",
]


def pdf_cache_path(cache_dir: str | Path, ts_code: str, period: str) -> Path:
    return Path(cache_dir) / f"{ts_code}_{period}.pdf"


def extract_text_from_pdf(path: str | Path) -> str:
    document = fitz.open(path)
    try:
        return "\n".join(page.get_text("text") for page in document)
    finally:
        document.close()


def extract_management_section_from_text(text: str, max_chars: int) -> str | None:
    start_match = None
    for pattern in _START_PATTERNS:
        match = re.search(pattern, text)
        if match and (start_match is None or match.start() < start_match.start()):
            start_match = match
    if start_match is None:
        return None

    tail = text[start_match.start():]
    end_index = len(tail)
    search_start = start_match.end() - start_match.start()
    for pattern in _END_PATTERNS:
        match = re.search(pattern, tail[search_start:])
        if match:
            candidate = search_start + match.start()
            end_index = min(end_index, candidate)
    section = tail[:end_index].strip()
    return section[:max_chars]


def extract_management_section_from_pdf(path: str | Path, max_chars: int) -> str | None:
    if not Path(path).exists():
        return None
    return extract_management_section_from_text(extract_text_from_pdf(path), max_chars=max_chars)
