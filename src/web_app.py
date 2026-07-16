"""
법령 미니 웹 챗봇
================
실행 (프로젝트 루트): python -m src.web_app
브라우저: http://127.0.0.1:8000

사전: ollama pull qwen2.5:3b
"""
from __future__ import annotations

import re
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import DEFAULT_TOP_K, LAWS_DIR, ROOT
from .step2_search import build_index, search
from .step3_rag import ask_llm

WEB_DIR = ROOT / "web"
UPLOAD_DIR = LAWS_DIR

# ①②③ … ⑳ → 1,2,3…
_CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"

app = FastAPI(title="법령 검색 챗봇")
_index: tuple | None = None


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)


class SourceItem(BaseModel):
    law: str
    score: float
    preview: str
    article: str = ""
    hang: str = ""
    hangs: list[str] = []
    citation: str = ""


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceItem]


def get_index():
    global _index
    if _index is None:
        _index = build_index()
    return _index


def rebuild_index():
    global _index
    _index = build_index()
    return _index


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


@app.on_event("startup")
def warmup():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    get_index()


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="질문을 입력해 주세요.")

    model, chunks, doc_vecs = get_index()
    hits = search(question, model, chunks, doc_vecs, top_k=DEFAULT_TOP_K)
    context = "\n\n".join(h["text"] for h in hits)

    try:
        answer = ask_llm(question, context)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"LLM 응답 실패. Ollama가 실행 중인지 확인해 주세요. ({e})",
        ) from e

    sources: list[SourceItem] = []
    for h in hits:
        article, hang, hangs, citation = parse_article_hang(h["text"])
        sources.append(
            SourceItem(
                law=h["law"],
                score=h["score"],
                preview=h["text"].replace("\n", " ")[:220],
                article=article,
                hang=hang,
                hangs=hangs,
                citation=citation,
            )
        )
    return ChatResponse(answer=answer, sources=sources)


@app.post("/api/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다.")

    try:
        import pdfplumber
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail="pdfplumber 가 필요합니다. pip install pdfplumber",
        ) from e

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_stem = re.sub(r"[^\w가-힣\-]+", "_", Path(file.filename).stem).strip("_") or "upload"
    pdf_path = UPLOAD_DIR / f"{safe_stem}.pdf"
    txt_path = UPLOAD_DIR / f"{safe_stem}.txt"

    pdf_path.write_bytes(raw)

    pages: list[str] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF 파싱 실패: {e}") from e

    text = "\n\n".join(p.strip() for p in pages if p and p.strip())
    if len(text) < 20:
        raise HTTPException(
            status_code=400,
            detail="PDF에서 텍스트를 충분히 추출하지 못했습니다. (스캔본일 수 있음)",
        )

    header = f"※ PDF 업로드 변환본: {file.filename}\n\n"
    txt_path.write_text(header + text, encoding="utf-8")

    try:
        rebuild_index()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"인덱스 재구축 실패: {e}") from e

    return {
        "ok": True,
        "filename": txt_path.name,
        "chars": len(text),
        "message": f"{txt_path.name} 저장 · 인덱스 갱신 완료 ({len(text)}자)",
    }


def main():
    uvicorn.run("src.web_app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
