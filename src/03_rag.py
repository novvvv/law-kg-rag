from __future__ import annotations
import sys
import requests
from .config import DEFAULT_TOP_K, LLM_MODEL, OLLAMA_URL
from .step2_search import build_index, search


# ------------------------------------------------------------------
# [method] ask_llm
# * logic * 
# - 조문과 질문 조합으로 프롬프트를 생성하고, Ollama에 Post한다. 
# ------------------------------------------------------------------

def ask_llm(question: str, context: str, model: str = LLM_MODEL) -> str:

    # Prompt 생성 
    prompt = f"""아래 [조문]만 근거로 [질문]에 답하세요.
            조문에 없는 내용은 지어내지 말고 "제공된 조문에는 없습니다"라고 답하세요.
            [조문]
            {context}
            [질문] {question}
        [답변]"""

    # Request to ollama 
    resp = requests.post(
        OLLAMA_URL,
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=120,
    )

    # exception.
    resp.raise_for_status()
    return resp.json()["response"].strip()


def main() -> None:

    # [Exception] CLI 인자가 존재하면 해당 질문을, 인자가 없다면 기본 질문을 대입한다.
    question = sys.argv[1] if len(sys.argv) > 1 else "음주운전 하면 어떻게 되나요?"

    # Step2 Search 
    model, chunks, doc_vecs = build_index()
    hits = search(question, model, chunks, doc_vecs, top_k=DEFAULT_TOP_K)
    context = "\n\n".join(h["text"] for h in hits)

    print("=== 찾은 조문 ===")
    for h in hits:
        print(" -", h["text"].replace("\n", " ")[:60], "...")

    # context = 검색으로 찾은 조문들의 글자만 이어 붙인 문자열 
    print("\n=== RAG 답변 (조문을 근거로) ===")
    print(ask_llm(question, context))
    # print(ask_llm(question, "(조문 없음)"))
    # ------------------------------------------------------------------
    # TODO: 조문을 빼고(=그냥 LLM) 비교해보세요.
    #   print(ask_llm(question, "(조문 없음)"))
    # 근거 없으면 그럴듯하지만 틀린 답(환각)이 나오기 쉽습니다.
    # ------------------------------------------------------------------

if __name__ == "__main__":
    main()
