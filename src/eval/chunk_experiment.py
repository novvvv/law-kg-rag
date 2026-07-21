
# ================================================================
#  ✨ chunk_experiment.py ✨
#  실행:
#  python -m src.cli.05_experiment
#  python -m src.cli.05_experiment --top-k 3 상위 Top N 문서 
#  python -m src.cli.05_experiment --rag 
# ================================================================

from __future__ import annotations
import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
import numpy as np
from sentence_transformers import SentenceTransformer
from ..config import EMBEDDING_MODEL, LAWS_DIR, ROOT
from ..rag.llm import ask_llm

# ================================================================
# ✨ Path & Variable ✨
# file : 무청킹, jo : 조 단위, hang : 조/항 단위, detail : 조/항/호/목 단위 
ChunkMode = Literal["file", "jo", "hang", "detail"]
CHUNK_MODES: list[ChunkMode] = ["file", "jo", "hang", "detail"]
MODE_LABELS = {
    "file": "무청킹 (txt 1파일=1청크)",
    "jo": "조 단위",
    "hang": "조/항 단위",
    "detail": "조/항/호/목 단위",
}

# DEFAULT_QUESTIONS : 질문 JSON 기본 경로 
# DEFAULT_OUT : 결과 JSON 저장 경로 
DEFAULT_QUESTIONS = ROOT / "data" / "eval" / "chunk_experiment_questions.json"
DEFAULT_OUT = ROOT / "data" / "eval" / "chunk_experiment.json"

# 정규표현식 [조]
# 정규표현식 [항] "①②③……"
# 정규표현식 [호/목] "1., 가."
ARTICLE_SPLIT = re.compile(r"(?=^제\s*\d+\s*조)", re.MULTILINE)
HANG_SPLIT = re.compile(r"(?=[①②③④⑤⑥⑦⑧⑨⑩⑪⑫])")
HO_MOK_SPLIT = re.compile(r"(?=^\s*\d+\.)|(?=^[가-힣]\.)", re.MULTILINE)
MIN_LEN = {"file": 20, "jo": 10, "hang": 10, "detail": 5}

# ================================================================ #

# ================================================================ #
# data model class 
# QuestionResult : 질문 1개 결과 
@dataclass
class QuestionResult:
    question: str 
    expected_law: str 
    hit: bool
    top_law: str
    top_score: float
    preview: str

# ModeSummary : 청킹 방식 요약 
@dataclass
class ModeSummary:
    mode: str
    label: str
    chunk_count: int
    avg_chunk_len: float
    hit_at_k: float
    avg_top_score: float
    hits: int
    total: int
    details: list[QuestionResult]
# ================================================================ #

# ================================================================ #
# ✨ Chunking Logic ✨

# _keep : 청킹 조각이 MIN_LEN보다 작은 경우 버린다. (너무 짧은 더미는 제거한다.)
def _keep(part: str, mode: ChunkMode) -> bool:
    return len(part.strip()) >= MIN_LEN[mode]

# chunk_text : 입력받은 모드를 기반으로 법령 파일을 청킹합니다.
def chunk_text(text: str, mode: ChunkMode) -> list[str]:

    # file mode "무청킹"
    if mode == "file":
        return [text.strip()] if _keep(text, mode) else []
    parts = [p.strip() for p in ARTICLE_SPLIT.split(text) if p.strip()]

    # jo mode "조 단위 청킹"
    if mode == "jo":
        return [p for p in parts if _keep(p, mode)]
    chunks: list[str] = []

    # hang/detail mode "호/목/항 단위 청킹"
    for article in parts:
        if mode == "hang":
            hangs = [h.strip() for h in HANG_SPLIT.split(article) if h.strip()]
            chunks.extend(h for h in hangs if _keep(h, mode))
            continue
        hangs = [h.strip() for h in HANG_SPLIT.split(article) if h.strip()]
        if len(hangs) <= 1:
            hangs = [article]
        for hang in hangs:
            items = [i.strip() for i in HO_MOK_SPLIT.split(hang) if i.strip()]
            if len(items) <= 1:
                items = [hang]
            chunks.extend(i for i in items if _keep(i, mode))
    return chunks

# load_chunks_for_mode 
def load_chunks_for_mode(folder: Path, mode: ChunkMode) -> list[dict]:
    chunks: list[dict] = []
    for path in sorted(folder.glob("*.txt")): # 법령 txt 파일
        text = path.read_text(encoding="utf-8") # 파일 읽기
        for part in chunk_text(text, mode): 
            chunks.append({"law": path.name, "text": part})
    return chunks


# build_index : Chunking Search Prepare
def build_index(
    folder: Path,
    model_name: str,
    mode: ChunkMode,
) -> tuple[SentenceTransformer, list[dict], np.ndarray]:

    model = SentenceTransformer(model_name) 
    chunks = load_chunks_for_mode(folder, mode)

    # [Exception] 청크가 존재하지 않는 경우 중단.
    if not chunks:
        raise FileNotFoundError(f"청크가 없습니다: {folder} (mode={mode})")
    print(f"  [{mode}] 청크 {len(chunks)}개 임베딩 중...")
    doc_vecs = model.encode([c["text"] for c in chunks])

    return model, chunks, doc_vecs
# ================================================================ #

# ================================================================ #
# ✨ search logic ✨

# search method 
# - 사용자 질의가 들어오면 코사인 유사도를 계산하여 가장 비슷한 top-k개를 고른다.
# - Query : "술에 취한 상태로 운전하면?"
# - A : "술에 취한 상태에서 자동차등을 운전하여서는 아니 된다."
# - B : "14세되지 아니한 자의 행위는 벌하지 아니한다"
def search(
    question: str,
    model: SentenceTransformer,
    chunks: list[dict],
    doc_vecs: np.ndarray,
    top_k: int,
) -> list[dict]:
    
    # model.encode : 임베딩 모델이 문장을 받아 숫자 벡터로 바꾼다. 
    q = model.encode([question])[0]

    # 두 벡터간의 코사인 유사도를 계산한뒤, top-k개를 정렬하여 반환한다. 
    sims = (doc_vecs @ q) / (np.linalg.norm(doc_vecs, axis=1) * np.linalg.norm(q) + 1e-9)
    order = np.argsort(-sims)[:top_k]
    return [dict(chunks[i], score=float(sims[i])) for i in order]

# law_match method
# - 정답 법령인지 판정한다. 
def _law_match(chunk_law: str, expected_law: str) -> bool:
    a = expected_law.replace(" ", "").replace("처벌법", "처벌")
    b = chunk_law.replace(" ", "").replace("처벌법", "처벌")
    return a in b


def load_questions(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)
# ================================================================ #

def evaluate_mode(
    questions: list[dict],
    mode: ChunkMode,
    *,
    top_k: int,
    laws_dir: Path,
    model_name: str,
) -> ModeSummary:
    model, chunks, doc_vecs = build_index(laws_dir, model_name, mode)
    avg_len = sum(len(c["text"]) for c in chunks) / len(chunks)

    details: list[QuestionResult] = []
    hits = 0
    for item in questions:
        results = search(item["question"], model, chunks, doc_vecs, top_k)
        found = any(_law_match(h["law"], item["expected_law"]) for h in results)
        hits += int(found)
        top = results[0] if results else {"law": "", "score": 0.0, "text": ""}
        details.append(
            QuestionResult(
                question=item["question"],
                expected_law=item["expected_law"],
                hit=found,
                top_law=top["law"],
                top_score=float(top["score"]),
                preview=top["text"].replace("\n", " ")[:120],
            )
        )

    total = len(questions)
    avg_top = (
        sum(d.top_score for d in details) / total if total else 0.0
    )
    return ModeSummary(
        mode=mode,
        label=MODE_LABELS[mode],
        chunk_count=len(chunks),
        avg_chunk_len=round(avg_len, 1),
        hit_at_k=round(hits / total * 100, 1) if total else 0.0,
        avg_top_score=round(avg_top, 4),
        hits=hits,
        total=total,
        details=details,
    )

# ================================================================ #
# ✨ debuging logic ✨

def _progress_bar(done: int, total: int, width: int = 24) -> str:
    pct = done / total if total else 1.0
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct * 100:5.1f}%"

def print_mode_done(summary: ModeSummary, *, index: int, total_modes: int) -> None:
    print()
    print("─" * 56)
    print(f"  {_progress_bar(index, total_modes)}  ({index}/{total_modes})")
    print(f"  ✓ 완료  {summary.label}")
    print(
        f"     Hit@K  {summary.hit_at_k:5.1f}%  ({summary.hits}/{summary.total})  ·  "
        f"avg top_score {summary.avg_top_score:.4f}  ·  "
        f"청크 {summary.chunk_count}개  ·  평균 {summary.avg_chunk_len:.0f}자"
    )
    print("─" * 56)

# ================================================================ #

# ================================================================ #
# ✨ report save/print logic ✨

def print_report(summaries: list[ModeSummary], top_k: int) -> None:
    print(f"\n{'=' * 72}")
    print(f"청킹 실험 (Hit@{top_k}, 정답=expected_law ↔ 검색 law 파일명)")
    print(f"{'=' * 72}")
    print(f"{'방식':<28} {'청크수':>6} {'평균길이':>8} {'Hit@K':>8} {'avg_score':>10}")
    print("-" * 72)
    for s in summaries:
        print(
            f"{s.label:<28} {s.chunk_count:>6} {s.avg_chunk_len:>8.0f} "
            f"{s.hit_at_k:>7.1f}% {s.avg_top_score:>10.4f}"
        )
    if len(summaries) > 1:
        delta = summaries[-1].hit_at_k - summaries[0].hit_at_k
        print("-" * 72)
        print(f"{summaries[0].mode} → {summaries[-1].mode}: {delta:+.1f}%p")

def save_report(
    summaries: list[ModeSummary],
    *,
    out_path: Path,
    top_k: int,
    model_name: str,
) -> None:
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "top_k": top_k,
        "embedding_model": model_name,
        "laws_dir": str(LAWS_DIR),
        "modes": [asdict(s) for s in summaries],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n결과 저장: {out_path}")

# ================================================================ #

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="청킹 방식 비교 실험")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--modes", default=",".join(CHUNK_MODES))
    parser.add_argument("--laws-dir", type=Path, default=LAWS_DIR)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", default=EMBEDDING_MODEL)
    parser.add_argument("--rag", action="store_true", help="앞 3문항 RAG 샘플 (Ollama)")
    args = parser.parse_args(argv)

    modes: list[ChunkMode] = []
    for m in args.modes.split(","):
        m = m.strip()
        if m not in CHUNK_MODES:
            raise SystemExit(f"unknown mode: {m}")
        modes.append(m)  # type: ignore[arg-type]

    questions = load_questions(args.questions)
    print(f"질문 {len(questions)}개 · Top-K={args.top_k} · modes={modes}")
    print(f"전체 진행  {_progress_bar(0, len(modes))}  (0/{len(modes)})")

    summaries: list[ModeSummary] = []
    for i, mode in enumerate(modes, start=1):
        print(f"\n▶ [{i}/{len(modes)}] {MODE_LABELS[mode]} 평가 시작...")
        summary = evaluate_mode(
            questions,
            mode,
            top_k=args.top_k,
            laws_dir=args.laws_dir,
            model_name=args.model,
        )
        summaries.append(summary)
        print_mode_done(summary, index=i, total_modes=len(modes))

    print_report(summaries, args.top_k)
    save_report(summaries, out_path=args.out, top_k=args.top_k, model_name=args.model)

    if args.rag:
        print("\n[RAG 샘플] 앞 3문항...")
        for mode in modes:
            model, chunks, doc_vecs = build_index(args.laws_dir, args.model, mode)
            print(f"\n--- {mode} ---")
            for item in questions[:3]:
                hits = search(item["question"], model, chunks, doc_vecs, args.top_k)
                ctx = "\n\n".join(h["text"] for h in hits)
                try:
                    ans = ask_llm(item["question"], ctx)
                except Exception as e:
                    ans = f"[LLM 오류] {e}"
                print(f"Q: {item['question']}")
                print(f"A: {ans[:150]}...")


if __name__ == "__main__":
    main()
