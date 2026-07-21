# 법령 RAG 검색 시스템

와이매틱스 인턴십 미니 프로젝트입니다.

공개 법령을 근거로 답변을 생성하는 로컬 RAG 챗봇입니다.  
질문과 가장 관련성 높은 조문을 검색하고, 답변과 함께 법령명·조문·유사도 점수를 제공합니다.

> 법령 검색 결과를 단순 키워드 매칭이 아닌 한국어 의미 검색으로 제공하고, 검색 품질과 답변 품질을 분리해 평가할 수 있도록 설계했습니다.

실험으로 검증한 개선 결과는 멘토(팀장)가 실제 112 시스템 개선에 직접 반영합니다.

## Architecture

```text
국가법령정보센터 API / PDF
           ↓
    법령 텍스트 추출 · 조문 청킹
           ↓
SentenceTransformer 임베딩 · Cosine Similarity 검색
           ↓
  검색 근거 조문 + Ollama LLM
           ↓
   답변 생성 · 출처 표시 · 정답률 평가
```

## Key Features

### 근거 기반 법령 질의
- 질문을 임베딩해 조문 단위로 의미 유사도를 계산하고 Top-K 결과를 반환합니다.
- LLM에는 검색된 조문만 컨텍스트로 전달합니다.
- 답변마다 법령명, 조문·항·호, 유사도 점수와 원문 미리보기를 표시합니다.

### 법령 데이터 수집 및 즉시 반영
- 국가법령정보센터 Open API에서 법령 본문과 조문 데이터를 수집합니다.
- PDF 업로드 시 텍스트를 추출해 법령 데이터로 저장하고, 검색 인덱스를 즉시 재구축합니다.
- 스캔본 등 텍스트 추출이 불가능한 PDF는 업로드 단계에서 예외 처리합니다.

### PDF Parser
- PDF에서 법령 본문을 추출하고, RAG·검색에 쓸 수 있는 구조화된 텍스트로 변환합니다.
- **목표:** 표, 개정표시, 조/항/호/목 구조를 정확하게 분리하는 것
- 추출된 조문 단위는 청킹·임베딩·출처 표시의 기준으로 사용됩니다.
- 상세: [docs/pdf-parser.md](docs/pdf-parser.md)

### 검색과 답변 품질의 분리 평가
- 평가 세트의 기대 키워드를 이용해 Top-K 검색 정답률을 측정합니다.
- 동일 질문에 대한 RAG 답변 정답률을 별도로 산출해 검색 문제와 생성 문제를 구분합니다.
- 임베딩 모델, 청킹 방식, Top-K 변경 효과를 수치로 비교할 수 있습니다.

## Tech Stack

**Backend**  
Python · FastAPI · Uvicorn · Pydantic

**Retrieval & Generation**  
SentenceTransformers (`jhgan/ko-sroberta-multitask`) · NumPy cosine similarity · Ollama · Qwen 2.5

**Legal Data Pipeline**  
국가법령정보센터 Open API · Requests · pdfplumber · 조문/항/호 파싱

**Frontend**  
Vanilla JavaScript · HTML · CSS

## Project Structure

```text
src/
├── app/         # FastAPI API, PDF 업로드 및 출처 파싱
├── retrieval/   # 법령 청킹, 임베딩 인덱스, 유사도 검색
├── rag/         # Ollama 기반 답변 생성
├── eval/        # 검색/RAG 정답률 평가
├── embeddings/  # 임베딩 모델 로딩
└── util/        # 법령 API 수집, PDF 추출 도구
```

## Roadmap

- 법령 간 인용·개정 관계를 연결하는 지식그래프 추가
- FAISS 또는 Chroma 기반 벡터 인덱스로 대용량 법령 검색 확장
- 조문 구조를 활용한 하이브리드 검색 및 재순위화
