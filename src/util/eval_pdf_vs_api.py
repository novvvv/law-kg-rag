"""
PDF 추출 txt(페이지별 병합본) vs law.go.kr API JSON(조문 정답지) 비교 스크립트.

개념
- API JSON에서 "조문여부 == 조문"만 뽑아 조문 리스트 생성
- PDF 추출 txt에서 "제{n}조(…)" 패턴으로 조문 블록 분리
- 각 API 조문에 대해 PDF 조문 블록 중 최고 유사도(SequenceMatcher)를 계산

주의
- PDF의 "표/수식"은 이미지일 수 있어 문자열 완전 일치는 기대하면 안 됩니다.
- 이 스크립트는 기본적으로 "조문 텍스트의 보존" 평가용입니다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

from .law_api import extract_articles


# 조문 헤더는 보통 `제N조(제목)` 형태로 존재합니다.
# 본문 인용(예: "제2조제1항")이 줄바꿈으로 인해 라인 시작에 오면
# 더 느슨한 regex는 조문을 잘못 분리할 수 있으므로, 괄호 제목을 "필수"로 둡니다.
HEADER_RE = re.compile(
    r"(?m)^\s*제\s*(\d+)\s*조(?:\s*의\s*(\d+))?\s*\([^)]*\)",
)

FOOTER_RE = re.compile(r"법제처\s*\d+\s*국가법령정보센터")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_for_cmp(text: str) -> str:
    # 공백/줄바꿈/푸터 제거 + 문자 정규화
    text = FOOTER_RE.sub("", text)
    text = text.replace("\u3000", " ")  # 전각 공백
    # 점 표기 통일(일부 문서에서 · / ㆍ 혼재)
    text = text.replace("ㆍ", "·")
    text = text.replace("⦁", "·")
    # 개정 태그 제거(선택: 유사도에 큰 영향)
    text = re.sub(r"<[^>]+>", "", text)
    # PDF에서 조문 뒤에 따라붙는 개정/신설/삭제/이동 주석(대괄호 형태) 제거
    # 예: [본조신설 2009. 12. 31.], [전문개정 ...], [제X조에서 이동 <...>]
    text = re.sub(
        r"(?m)^\s*\[[^\]]*(?:전문개정|본조신설|신설|삭제|이동|종전|개정)[^\]]*\]\s*$",
        "",
        text,
    )
    # 공백 잔여 제거
    # whitespace 제거
    text = re.sub(r"\s+", "", text)
    return text


def similarity(a: str, b: str) -> float:
    na = _normalize_for_cmp(a)
    nb = _normalize_for_cmp(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def _article_key(article_no: str, branch: str | None = None) -> str:
    if branch and str(branch).strip():
        return f"{article_no}의{branch}"
    return str(article_no).strip()


def _parse_pdf_articles(pdf_text: str) -> list[dict[str, str]]:
    """
    PDF 추출 txt에서 조문 헤더 패턴으로 블록을 나눕니다.
    반환: [{key, raw_text}, ...]
    """
    matches = list(HEADER_RE.finditer(pdf_text))
    if not matches:
        return []

    blocks: list[dict[str, str]] = []
    for idx, m in enumerate(matches):
        start = m.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(pdf_text)
        block = pdf_text[start:end].strip()

        n = m.group(1)
        br = m.group(2)
        key = _article_key(n, br)
        blocks.append({"key": key, "raw_text": block})

    # 극단적으로 짧은 블록 제거(추출 잡음 감소)
    filtered = []
    for b in blocks:
        if len(b["raw_text"]) >= 20:
            filtered.append(b)
    return filtered


def _iter_best_matches(
    api_articles: list[dict[str, Any]],
    pdf_blocks: list[dict[str, str]],
    *,
    api_limit: int | None = None,
) -> dict[str, Any]:
    considered = api_articles[: api_limit] if api_limit else api_articles

    # key별 후보 인덱스(빠른 매칭)
    by_key: dict[str, list[dict[str, str]]] = {}
    for b in pdf_blocks:
        by_key.setdefault(b["key"], []).append(b)

    passed = 0
    failed = 0
    best_sims: list[float] = []
    failures: list[dict[str, Any]] = []

    for t in considered:
        api_key = _article_key(t.get("조문번호", ""), t.get("조문가지번호") or None)
        api_content = t.get("조문내용", "") or ""

        candidates = by_key.get(api_key) or pdf_blocks

        best_sim = -1.0
        best_block = None
        for b in candidates:
            s = similarity(api_content, b["raw_text"])
            if s > best_sim:
                best_sim = s
                best_block = b

        best_sims.append(best_sim)

        report_item = {
            "조문표시": t.get("조문표시", ""),
            "조문키": api_key,
            "유사도_best": round(best_sim, 5),
        }

        if best_sim >= 0.95:
            passed += 1
        else:
            failed += 1
            failures.append(
                {
                    **report_item,
                    "사유": "임계값(0.95) 미달",
                    "api_content_excerpt": (api_content or "")[:120],
                    "pdf_block_excerpt": (best_block.get("raw_text") if best_block else "")[:120],
                }
            )

    avg_sim = sum(best_sims) / len(best_sims) if best_sims else 0.0
    return {
        "api_articles_count": len(considered),
        "passed_0_95": passed,
        "failed": failed,
        "avg_best_similarity": avg_sim,
        "failures": failures[:200],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="law.go.kr API 조문 vs PDF 텍스트 비교")
    parser.add_argument("--api-json", type=Path, required=True, help="lawService.do type=JSON 원본 파일")
    parser.add_argument("--pdf-txt", type=Path, required=True, help="pdfplumber 추출 txt(전체 병합본)")
    parser.add_argument("--out", type=Path, default=None, help="리포트 출력 경로(JSON)")
    parser.add_argument("--api-limit", type=int, default=None, help="테스트용 API 조문 개수 제한")
    args = parser.parse_args()

    if not args.api_json.exists():
        print(f"[error] api json 없음: {args.api_json}", file=sys.stderr)
        sys.exit(1)
    if not args.pdf_txt.exists():
        print(f"[error] pdf txt 없음: {args.pdf_txt}", file=sys.stderr)
        sys.exit(1)

    api_raw = _read_json(args.api_json)
    api_articles = extract_articles(api_raw)

    pdf_text = args.pdf_txt.read_text(encoding="utf-8")
    pdf_blocks = _parse_pdf_articles(pdf_text)

    report_core = _iter_best_matches(api_articles, pdf_blocks, api_limit=args.api_limit)

    out = args.out
    if out is None:
        out = args.pdf_txt.parent / f"{args.pdf_txt.stem}_eval_vs_api.json"

    payload = {
        "api_json": str(args.api_json),
        "pdf_txt": str(args.pdf_txt),
        "api_articles": len(api_articles),
        "pdf_blocks": len(pdf_blocks),
        "threshold": 0.95,
        **report_core,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[done] report: {out}")
    print(f"[summary] api_articles={len(api_articles)} pdf_blocks={len(pdf_blocks)} avg_sim={payload['avg_best_similarity']:.4f}")


if __name__ == "__main__":
    main()

