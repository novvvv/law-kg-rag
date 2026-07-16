# Week 1 — 미니 법령 검색 시스템

목표: 임베딩 → 벡터 검색 → RAG → 정답률 측정까지 직접 만들고, **정확도를 숫자로 재는 기준**을 세운다.

---

## 모듈 구성

| 경로 | 역할 |
| ---- | ---- |
| `src/config.py` | 임베딩 모델명, `data/laws/` 경로, Ollama URL·모델, top-k 등 공통 설정 |
| `src/step1_embeddings.py` | 문장 → 벡터, 코사인 유사도로 “의미가 가까운지” 확인 (STEP 1) |
| `src/step2_search.py` | 조문 청킹 · 인덱스 구축 · 질문 벡터 검색 (STEP 2). step3/step4가 재사용 |
| `src/step3_rag.py` | 검색된 조문을 근거로 로컬 LLM 답변 생성 (STEP 3) |
| `src/step4_measure.py` | `data/questions.json` 정답 세트로 검색 정답률 측정 (STEP 4) |
| `data/questions.json` | 측정용 질문 · 기대 키워드 |
| `data/laws/` | 법령 발췌 `.txt` |
| `requirements.txt` | Python 의존성 (프로젝트 루트) |

```
법령 텍스트 (data/laws/)
    → step2_search.load_chunks / build_index
    → step1_embeddings (유사도 실험) · step2_search (벡터 검색)
    → step3_rag (검색 + LLM)
    → step4_measure (정답률)
```

---

## 실행 방법

프로젝트 루트에서 실행합니다.

```bash
pip install -r requirements.txt
ollama pull qwen2.5:3b   # RAG용, 최초 1회

python -m src.step1_embeddings
python -m src.step2_search "음주운전 처벌은?"
python -m src.step3_rag "음주운전 하면 어떻게 되나요?"
python -m src.step4_measure

# 웹 챗봇 (브라우저 http://127.0.0.1:8000)
./run.sh
# 또는: python -m src.web_app
```

설정 변경은 `src/config.py`에서 합니다. 각 파일의 `TODO` 주석을 따라 모델·청킹·top-k를 바꿔가며 정답률을 비교하세요.

---

## STEP별 할 일

1. **embeddings** — 유사 문장 / 다른 문장 유사도 확인, 모델 바꿔 비교
2. **search** — 청킹·`TOP_K` 변경 실험
3. **rag** — 조문 있는 답변 vs 없는 답변(환각) 비교
4. **measure** — `data/questions.json`을 직접 3–5개로 작성하고 정답률 기록
5. **(덤)** PDF 파싱에서 표·개정표시·조/항/호가 깨지는 사례 메모

법령 txt를 law.go.kr 기준으로 보강 (+ 가능하면 형법)
questions.json을 본인 조문에 맞게 다시 쓰기
STEP 1–4 실행 → measure 정답률 한 번 기록
TODO대로 top-k·모델·RAG 유무 비교
(여유 시) PDF 하나 pdfplumber로 열어 깨짐 사례 메모
