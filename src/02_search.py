# ------------------------------------------------------------------
# step2_search.py Module 
#
# * flow *
# - 법령 조문을 잘라 인덱스를 만들고, 질문에 가까운 조문을 찾는 모듈입니다. 
#
# * related Module * 
# - step4_measure.py -> build_index(), search() 
# - step3_rag.py -> build_index(), search()  
#
# ------------------------------------------------------------------

from __future__ import annotations
import re
import sys
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer
from .config import DEFAULT_TOP_K, EMBEDDING_MODEL, LAWS_DIR


# TODO : 코드 내부 로직 추가 분석 
# ------------------------------------------------------------------
# [method] load_chunks
# * logic * 
# - data/laws/의 .txt 파일을 자른다. 
# - 줄 맨 앞의 "제12조" 같은 패턴만 자른다. 
# - 문장 중간의 "제 80조에 따라" 같은 패턴은 청킹하지 않는다. 
# ------------------------------------------------------------------

def load_chunks(folder: Path | str = LAWS_DIR) -> list[dict]:

    folder = Path(folder)
    chunks: list[dict] = []
    for path in sorted(folder.glob("*.txt")):
        text = path.read_text(encoding="utf-8")

        # 줄 맨 앞 '제N조'에서 분할 (문장 속 "제80조에 따라"는 안 잘림)
        parts = re.split(r"(?=^제\s*\d+\s*조)", text, flags=re.MULTILINE)
        for part in parts:
            part = part.strip()
            if len(part) > 10:
                chunks.append({"law": path.name, "text": part})

    # ------------------------------------------------------------------
    # TODO(1): 청킹 방식을 바꿔 실험해보세요. 정확도가 달라집니다.
    #   - "항(①②③)" 단위로 더 잘게 자르기
    #   - 조문 여러 개를 묶어 크게 자르기
    # ------------------------------------------------------------------

    return chunks


# ------------------------------------------------------------------
# [method] build_index
#  logic  
# - 검색에 사용할 인덱스를 만들어주는 메서드 
# - Search() Method가 질문과 바로 비교할 수 있도록 도와주는 메서드 
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# Chunk : load_chunks로 자른 조문 한 덩어리 ex) 44조 전체 
# Text : 덩어리의 한글 글자 
# Vector : Text를 모델이 바꾼 숫자 
# ------------------------------------------------------------------

def build_index(
    folder: Path | str = LAWS_DIR,
    model_name: str = EMBEDDING_MODEL,
) -> tuple[SentenceTransformer, list[dict], np.ndarray]:

    # Logic1. SentenceTransformer (Text to Number Array)
    # Embedding Model on To Memory 
    model = SentenceTransformer(model_name) 
    # Chunking 
    chunks = load_chunks(folder) 

    # Exception. chunk가 존재하지 않는 경우 
    if not chunks:
        raise FileNotFoundError(f"조문 조각이 없습니다. {folder} 에 .txt 를 넣어주세요.")

    # Logic2. 모든 조문 조각을 벡터로 바꾼다. 
    # 추후에 파일이 많아지면 단순히 doc_vecs에 저장하는 것이 아닌 chroma, FAISS와 같은 벡터DB/인덱스에 저장 
    print(f"조각 {len(chunks)}개 임베딩 중...")
    doc_vecs = model.encode([c["text"] for c in chunks])

    return model, chunks, doc_vecs


# ------------------------------------------------------------------
# ✨ [method] search ✨
# * logic * 
# - build_index() method로 부터 만든 반환 파라미터 (model, chunks, doc_vecs)를
# - 기반으로 질문 하나에 대해 가장 가까운 조문 top-k를 고른다. 
#
# ✨ input parameter ✨
# question : 사용자 질의 
# SentenceTransformer : 사용자의 질의를 Vector로 바꾸는 번역기 
# chunks : 원문 목록 [{law, text}, ...]
# doc_vecs : 조문별 벡터, 모양 
# top_k : 몇 개 까지 탐색할 것인가. 
# ------------------------------------------------------------------

def search(
    question: str,
    model: SentenceTransformer,
    chunks: list[dict],
    doc_vecs: np.ndarray,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict]:

    # Logic1. 질의를 임베딩 모델을 사용하여, 벡터로 변경 
    q = model.encode([question])[0]
    # 모든 조문의 코사인 유사도 식을 계산 
    sims = (doc_vecs @ q) / (np.linalg.norm(doc_vecs, axis=1) * np.linalg.norm(q) + 1e-9)
    # 상위 3개의 인덱스 선정 
    order = np.argsort(-sims)[:top_k]
    # 원문 + 점수로 포장하여 반환한다. 
    return [dict(chunks[i], score=float(sims[i])) for i in order]


def main() -> None:

    question = sys.argv[1] if len(sys.argv) > 1 else "음주운전 처벌은?"
    model, chunks, doc_vecs = build_index()

    # TODO(2): 1, 5 로 바꿔보고 결과 변화를 관찰하세요.
    top_k = DEFAULT_TOP_K  
    hits = search(question, model, chunks, doc_vecs, top_k=top_k)

    print(f"\n질문: {question}")
    print(f"가장 가까운 조문 {top_k}개:")
    for h in hits:
        head = h["text"].replace("\n", " ")[:70]
        print(f"  [{h['score']:.3f}] ({h['law']}) {head} ...")


if __name__ == "__main__":
    main()
