"""국가법령정보센터(law.go.kr) Open API — 검색·조문 파싱·파일 저장."""
from __future__ import annotations

import json
import os
import re
from html import escape
from pathlib import Path
from typing import Any

import requests

# util 단독 사용 기준 기본 경로·API 키
ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUT_DIR = ROOT / "data" / "laws" / "api"
DEFAULT_API_KEY = os.environ.get("LAW_API_KEY", "doillawapi")
BASE = "https://www.law.go.kr/DRF"


def _get(url: str, *, as_json: bool = False, timeout: int = 60) -> Any:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    if as_json:
        return response.json()
    return response.text


def search_laws(
    query: str,
    *,
    api_key: str = DEFAULT_API_KEY,
    limit: int = 3,
) -> list[dict[str, str]]:
    """법령명으로 검색해 메타데이터 목록을 반환합니다."""
    url = (
        f"{BASE}/lawSearch.do?OC={api_key}&target=law&type=JSON"
        f"&query={query}&display={limit}"
    )
    data = _get(url, as_json=True)
    laws = data.get("LawSearch", {}).get("law", [])
    if isinstance(laws, dict):
        laws = [laws]
    return [
        {
            "법령일련번호": law["법령일련번호"],
            "법령명한글": law["법령명한글"],
            "시행일자": law.get("시행일자", ""),
            "공포번호": law.get("공포번호", ""),
        }
        for law in laws
    ]


def fetch_law_json(
    law_id: str,
    *,
    api_key: str = DEFAULT_API_KEY,
) -> dict[str, Any]:
    """법령일련번호(MST)로 전체 본문 JSON을 가져옵니다."""
    url = f"{BASE}/lawService.do?OC={api_key}&target=law&MST={law_id}&type=JSON"
    return _get(url, as_json=True)


def fetch_law_html_raw(
    law_id: str,
    *,
    api_key: str = DEFAULT_API_KEY,
) -> str:
    """API가 반환하는 원본 HTML(iframe 래퍼)을 그대로 가져옵니다."""
    url = f"{BASE}/lawService.do?OC={api_key}&target=law&MST={law_id}&type=HTML"
    return _get(url)


def _normalize_units(raw: Any) -> list[dict[str, Any]]:
    units = raw.get("조문단위", []) if isinstance(raw, dict) else raw
    if isinstance(units, dict):
        return [units]
    return units or []


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(part for item in value for part in [_text(item)] if part)
    return str(value).strip()


def _collect_hang(hang: dict[str, Any], body_parts: list[str]) -> None:
    text = _text(hang.get("항내용"))
    if text:
        body_parts.append(text)
    for ho in hang.get("호") or []:
        if not isinstance(ho, dict):
            continue
        ho_text = _text(ho.get("호내용"))
        if ho_text:
            body_parts.append(ho_text)
        for mok in ho.get("목") or []:
            if isinstance(mok, dict):
                mok_text = _text(mok.get("목내용"))
                if mok_text:
                    body_parts.append(mok_text)


def extract_articles(law_json: dict[str, Any]) -> list[dict[str, Any]]:
    """조문단위만 뽑아 사용하기 쉬운 형태로 정리합니다."""
    law = law_json.get("법령", {})
    articles: list[dict[str, Any]] = []

    for unit in _normalize_units(law.get("조문", {})):
        if unit.get("조문여부") != "조문":
            continue

        article_no = unit.get("조문번호", "")
        branch = unit.get("조문가지번호", "")
        title = unit.get("조문제목", "")
        label = f"제{article_no}조"
        if branch:
            label += f"의{branch}"
        if title:
            label += f"({title})"

        body_parts: list[str] = []
        main = _text(unit.get("조문내용"))
        if main and main != label:
            body_parts.append(main)

        for hang in unit.get("항") or []:
            if isinstance(hang, dict):
                _collect_hang(hang, body_parts)

        articles.append(
            {
                "조문번호": article_no,
                "조문가지번호": branch,
                "조문제목": title,
                "조문표시": label,
                "조문내용": "\n".join(body_parts).strip(),
                "조문키": unit.get("조문키", ""),
                "조문시행일자": unit.get("조문시행일자", ""),
            }
        )

    return articles


def articles_to_html(
    law_name: str,
    basic_info: dict[str, Any],
    articles: list[dict[str, Any]],
) -> str:
    """조문 목록을 읽기 쉬운 HTML 문서로 변환합니다."""
    info_rows = "".join(
        f"<tr><th>{escape(k)}</th><td>{escape(str(v))}</td></tr>"
        for k, v in basic_info.items()
        if v
    )
    article_blocks = []
    for article in articles:
        content = escape(article["조문내용"]).replace("\n", "<br>\n")
        article_blocks.append(
            f"<section class='article' id='art-{article['조문키'] or article['조문표시']}'>"
            f"<h2>{escape(article['조문표시'])}</h2>"
            f"<p>{content}</p>"
            f"</section>"
        )

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(law_name)}</title>
  <style>
    body {{ font-family: "Pretendard", "Apple SD Gothic Neo", sans-serif; line-height: 1.6; max-width: 900px; margin: 2rem auto; padding: 0 1rem; color: #222; }}
    h1 {{ border-bottom: 2px solid #333; padding-bottom: .5rem; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
    th, td {{ border: 1px solid #ddd; padding: .5rem .75rem; text-align: left; }}
    th {{ background: #f5f5f5; width: 8rem; }}
    .article {{ margin-bottom: 1.5rem; }}
    .article h2 {{ font-size: 1.1rem; margin-bottom: .5rem; color: #0b57d0; }}
    .article p {{ margin: 0; white-space: normal; }}
  </style>
</head>
<body>
  <h1>{escape(law_name)}</h1>
  <table>{info_rows}</table>
  <main>
    {"".join(article_blocks)}
  </main>
</body>
</html>
"""


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", name).strip()
    return cleaned or "law"


def save_law_files(
    law_meta: dict[str, str],
    law_json: dict[str, Any],
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    include_raw_html: bool = True,
    api_key: str = DEFAULT_API_KEY,
) -> dict[str, Path]:
    """JSON·조문 JSON·HTML을 저장하고 경로를 반환합니다."""
    out_dir.mkdir(parents=True, exist_ok=True)

    law_name = law_meta["법령명한글"]
    law_id = law_meta["법령일련번호"]
    stem = f"{_safe_filename(law_name)}_{law_id}"

    law = law_json.get("법령", {})
    basic_info = law.get("기본정보", {})
    articles = extract_articles(law_json)

    paths: dict[str, Path] = {}

    full_json_path = out_dir / f"{stem}.json"
    full_json_path.write_text(
        json.dumps(law_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    paths["full_json"] = full_json_path

    articles_json_path = out_dir / f"{stem}_articles.json"
    articles_json_path.write_text(
        json.dumps(
            {
                "법령명": law_name,
                "법령일련번호": law_id,
                "기본정보": basic_info,
                "조문": articles,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    paths["articles_json"] = articles_json_path

    html_path = out_dir / f"{stem}.html"
    html_path.write_text(
        articles_to_html(law_name, basic_info, articles),
        encoding="utf-8",
    )
    paths["html"] = html_path

    if include_raw_html:
        raw_html_path = out_dir / f"{stem}_api.html"
        raw_html_path.write_text(
            fetch_law_html_raw(law_id, api_key=api_key),
            encoding="utf-8",
        )
        paths["api_html"] = raw_html_path

    return paths


def fetch_and_save(
    query: str,
    *,
    limit: int = 1,
    api_key: str = DEFAULT_API_KEY,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> list[dict[str, Any]]:
    """검색 → 본문 조회 → 파일 저장까지 한 번에 수행합니다."""
    results: list[dict[str, Any]] = []
    for meta in search_laws(query, api_key=api_key, limit=limit):
        law_json = fetch_law_json(meta["법령일련번호"], api_key=api_key)
        paths = save_law_files(meta, law_json, out_dir=out_dir, api_key=api_key)
        articles = extract_articles(law_json)
        results.append(
            {
                "meta": meta,
                "article_count": len(articles),
                "paths": {k: str(v) for k, v in paths.items()},
                "sample": articles[0] if articles else None,
            }
        )
    return results
