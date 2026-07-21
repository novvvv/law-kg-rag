"""
step4_measure.py — 정확도 측정 모듈
=============================
역할: data/questions.json 정답 질문 세트로 "맞는 조문이 검색되나?"를 숫자(정답률)로 잽니다.
1주차 STEP 4. 실행: python -m src.cli.04_measure

questions.json 에 질문·기대 키워드를 넣고, 손잡이(청킹·top-k·모델)를 바꿀 때마다
이 숫자와 비교하세요. → 측정 없이는 개선 없다.

핵심 개념
  - expect_keyword: 정답 조문에 들어 있을 것으로 기대하는 문자열
  - top-k hit: 상위 k개 안에 키워드가 있으면 정답으로 간주
"""

# ------------------------------------------------------------------
# ✨ step4_measure.py Module ✨
#
# * description *
# - LLM이 바르게 검색을 가져왔는지 정답률(%)로 재는 모듈 
# - 단순히 LLM 답변 품질이 아닌 "질문에 맞는 조문이 top-k"에 왔는지 검색 
# 
# * flow * 
# - 1. question.json load -> 질문 + 기대 키워드 
# - 2. build_index() -> 조문 인덱스 1회 구축 
# - 3. 질문마다 search(top_k) 가장 가까운 조문 검색 
# - 4. top-k중 하나라도 키워드에 포함되어 있는지 확인 
# - 5. O/X 출력 및 정답률 
#
# ------------------------------------------------------------------

from __future__ import annotations
import json
from ..config import DEFAULT_TOP_K, QUESTIONS_PATH
from ..retrieval.search import build_index, search
from ..rag.llm import ask_llm


def main() -> None:
    with QUESTIONS_PATH.open(encoding="utf-8") as f:
        questions = json.load(f)

    model, chunks, doc_vecs = build_index()

    # TODO(1): 1 로 낮추면 정답률이 떨어지나요?
    top_k = DEFAULT_TOP_K
    correct_search = 0
    correct_rag = 0
    total = len(questions)

    # ------------------------------------------------------------------
    # (A) 검색 정답률: top-k 조문에 expect_keyword 가 있으면 O
    # ------------------------------------------------------------------
    print("\n=== (A) 검색 채점 (조문 키워드) ===")
    for item in questions:
        hits = search(item["question"], model, chunks, doc_vecs, top_k=top_k)
        found = any(item["expect_keyword"] in h["text"] for h in hits)
        correct_search += int(found)
        print(("  O" if found else "  X"), item["question"])

    print(
        f"\n검색 정답률: {correct_search}/{total} = "
        f"{correct_search / total * 100:.0f}%"
    )
    print("→ 이 숫자를 적어두세요. 이후 개선마다 이 값과 비교합니다.")

    # ------------------------------------------------------------------
    # (B) RAG 답변 채점: ask_llm 답변에 expect_keyword 가 있으면 O
    #     Ollama 필요. 검색은 맞아도 답이 비면 X 가 될 수 있음.
    # TODO(3): 질문을 5개까지 늘리고, 어려운 질문도 넣어보기
    # ------------------------------------------------------------------
    print("\n=== (B) RAG 채점 (LLM 답변 키워드) ===")
    for item in questions:
        hits = search(item["question"], model, chunks, doc_vecs, top_k=top_k)
        context = "\n\n".join(h["text"] for h in hits)
        answer = ask_llm(item["question"], context)
        found = item["expect_keyword"] in answer
        correct_rag += int(found)
        mark = "O" if found else "X"
        preview = answer.replace("\n", " ")[:50]
        print(f"  {mark} {item['question']}")
        print(f"     → {preview}...")

    print(
        f"\nRAG 정답률: {correct_rag}/{total} = "
        f"{correct_rag / total * 100:.0f}%"
    )
    print("→ (A)와 (B)를 비교하세요. 검색은 맞는데 답이 틀리면 RAG/조문 보강 이슈입니다.")


if __name__ == "__main__":
    main()
