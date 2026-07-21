"""pdfplumber로 PDF 텍스트 추출."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUT_DIR = ROOT / "data" / "laws" / "pdf_extracted"


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", name).strip()
    return cleaned or "pdf"


def extract_pdf(
    pdf_path: Path,
    *,
    join_hyphenated: bool = True,
) -> dict[str, Any]:
    """PDF에서 페이지별 텍스트·표·이미지 메타를 추출합니다."""
    try:
        import pdfplumber
    except ImportError as e:
        raise ImportError("pdfplumber가 필요합니다. pip install pdfplumber") from e

    pages: list[dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if join_hyphenated:
                text = _join_hyphenated_lines(text)

            tables = page.extract_tables() or []
            images = [
                {
                    "x0": round(img.get("x0", 0), 1),
                    "y0": round(img.get("top", 0), 1),
                    "width": round(img.get("width", 0), 1),
                    "height": round(img.get("height", 0), 1),
                }
                for img in (page.images or [])
            ]

            pages.append(
                {
                    "page": i,
                    "char_count": len(text),
                    "text": text.strip(),
                    "table_count": len(tables),
                    "tables": tables,
                    "image_count": len(images),
                    "images": images,
                }
            )

    full_text = "\n\n".join(
        f"--- page {p['page']} ---\n{p['text']}"
        for p in pages
        if p["text"]
    )

    return {
        "source": str(pdf_path.resolve()),
        "page_count": len(pages),
        "char_count": sum(p["char_count"] for p in pages),
        "table_pages": sum(1 for p in pages if p["table_count"] > 0),
        "image_pages": sum(1 for p in pages if p["image_count"] > 0),
        "pages": pages,
        "full_text": full_text,
    }


def _join_hyphenated_lines(text: str) -> str:
    """줄 끝 하이픈으로 끊긴 단어를 이어 붙입니다."""
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.endswith("-") and i + 1 < len(lines):
            out.append(line[:-1] + lines[i + 1].lstrip())
            i += 2
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def save_pdf_extract(
    pdf_path: Path,
    data: dict[str, Any],
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_filename(pdf_path.stem)

    txt_path = out_dir / f"{stem}.txt"
    txt_path.write_text(data["full_text"], encoding="utf-8")

    meta_path = out_dir / f"{stem}_meta.json"
    meta = {k: v for k, v in data.items() if k != "full_text"}
    meta["pages"] = [
        {k: v for k, v in p.items() if k != "text"}
        for p in data["pages"]
    ]
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    pages_dir = out_dir / f"{stem}_pages"
    pages_dir.mkdir(exist_ok=True)
    for page in data["pages"]:
        page_path = pages_dir / f"page_{page['page']:03d}.txt"
        page_path.write_text(page["text"], encoding="utf-8")

    return {"txt": txt_path, "meta": meta_path, "pages_dir": pages_dir}


def extract_and_save(
    pdf_path: Path,
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    data = extract_pdf(pdf_path)
    paths = save_pdf_extract(pdf_path, data, out_dir=out_dir)
    return {"data": data, "paths": {k: str(v) for k, v in paths.items()}}


def main() -> None:
    parser = argparse.ArgumentParser(description="pdfplumber로 PDF 텍스트 추출")
    parser.add_argument("pdf", type=Path, help="PDF 파일 경로")
    parser.add_argument(
        "-o",
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="저장 디렉터리",
    )
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"파일 없음: {args.pdf}", file=sys.stderr)
        sys.exit(1)

    result = extract_and_save(args.pdf, out_dir=args.out_dir)
    data = result["data"]

    print(f"\n[{args.pdf.name}]")
    print(f"  페이지: {data['page_count']}")
    print(f"  문자 수: {data['char_count']:,}")
    print(f"  표 있는 페이지: {data['table_pages']}")
    print(f"  이미지 있는 페이지: {data['image_pages']}")
    for kind, path in result["paths"].items():
        print(f"  - {kind}: {path}")

    sample = data["full_text"][:400]
    if sample:
        print(f"\n  미리보기:\n{sample}...")

    print("\n완료")


if __name__ == "__main__":
    main()
