"""조문 텍스트에서 제N조 / 항 정보 추출."""
from __future__ import annotations

import re

# ①②③ … ⑳ → 1,2,3…
_CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def parse_article_hang(text: str) -> tuple[str, str, list[str], str]:
    """조문 텍스트에서 제N조 / 항 정보를 추출한다."""
    article = ""
    m = re.search(r"제\s*\d+\s*조(?:의\s*\d+)?", text)
    if m:
        article = re.sub(r"\s+", "", m.group(0))

    hangs: list[str] = []
    for ch in text:
        if ch in _CIRCLED:
            n = _CIRCLED.index(ch) + 1
            label = f"제{n}항"
            if label not in hangs:
                hangs.append(label)

    for hm in re.finditer(r"^\s*[（(]?\s*(\d+)\s*[）)]?\s*", text, flags=re.MULTILINE):
        label = f"제{hm.group(1)}항"
        if label not in hangs:
            hangs.append(label)

    hang = hangs[0] if hangs else ""
    if article and hang:
        citation = f"{article} {hang}"
    elif article and hangs:
        citation = f"{article} ({', '.join(hangs)})"
    elif article:
        citation = article
    else:
        citation = ""

    return article, hang, hangs, citation
