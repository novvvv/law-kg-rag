# ------------------------------------------------------------------
# step1_embeddings.py Module 
# * flow *
# - 문장을 벡터로 바꾸고 (임베딩 수행), 해당 벡터간 코사인 유사도를 계산하는 모듈입니다. 
# ------------------------------------------------------------------

from __future__ import annotations
import numpy as np
from sentence_transformers import SentenceTransformer
from ..config import EMBEDDING_MODEL

# ------------------------------------------------------------------
# [method] cosine 
# * description * 
# - 코사인 유사도를 계산합니다. 
# - +1e-9로 0으로 나누기를 방지합니다. 
# ------------------------------------------------------------------

def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """두 벡터의 코사인 유사도."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


# ------------------------------------------------------------------
# [method] laod_model 
# * flow *
# config.EMBEDDINGZ_MODEL 로드. 최초 1회 다운로드 
# ------------------------------------------------------------------

def load_model(model_name: str = EMBEDDING_MODEL) -> SentenceTransformer:
    print(f"모델 불러오는 중: {model_name}  (최초 1회는 다운로드로 조금 걸립니다)")
    return SentenceTransformer(model_name)


def main() -> None:

    # Logic1. Embedding Model Load 
    # Huggingface SentenceTransformer Class Instance 
    model = load_model()

    sentences = [
        "술을 마시고 운전했다",  # 0
        "음주운전으로 적발됐다",  # 1 — 0과 의미 유사
        "길에서 소변을 봤다",  # 2 — 0과 의미 다름
    ]

    # Logic2. Input Sentences, Output Numpy(np.ndarray)
    vecs = model.encode(sentences)

    print(f"→ 각 문장이 숫자 {len(vecs[0])}개짜리 벡터가 됐습니다.\n")
    print("음주운전 vs 술마시고운전 :", round(cosine(vecs[0], vecs[1]), 3), " (높을 것)")
    print("음주운전 vs 노상방뇨     :", round(cosine(vecs[0], vecs[2]), 3), " (낮을 것)")


if __name__ == "__main__":
    main()
