# PDF 파싱 평가 README

이 문서는 `API JSON(정답)`과 `PDF 파싱 txt(결과)`를 비교하는 평가 흐름을 설명합니다.

관련 스크립트:

- PDF 추출: `src/util/pdf_extract.py`
- 평가: `src/util/eval_pdf_vs_api.py`

---

## 1) 평가가 필요한 이유

법령 PDF를 파싱하면 페이지 단위 텍스트(`page_001.txt` ...)가 많이 생깁니다.  
하지만 정답 데이터(API)는 **조문 단위**이므로, 페이지끼리 1:1 비교하면 의미가 없습니다.

평가 스크립트는 두 데이터를 같은 기준(조문 단위)으로 맞춘 뒤 유사도를 계산합니다.

---

## 2) 입력/출력 구조

### 입력

- `--api-json`: law.go.kr `lawService` 원본 JSON  
  예) `data/laws/api/112신고의 운영 및 처리에 관한 법률_257787.json`
- `--pdf-txt`: PDF 추출 전체 텍스트 파일  
  예) `data/laws/pdf_extracted/소득세법(법률)(제21221호)(20260701).txt`

### 출력

- 기본 출력 경로: `<pdf_txt_stem>_eval_vs_api.json`
- 커스텀 경로: `--out` 옵션 사용

리포트에는 아래가 포함됩니다.

- 전체 조문 수 / PDF 블록 수
- 임계값(기본 0.95) 기준 통과/실패 수
- 평균 최고 유사도
- 실패 조문 목록(발췌 포함)

---

## 3) 동작 방식

### A. API JSON 정답 조문 생성

`extract_articles()`로 원본 JSON에서 실제 조문만 추출합니다.

- 사용: `법령.조문.조문단위`
- 필터: `조문여부 == "조문"`만 대상 (`전문` 제외)
- 조문번호/가지번호/제목/항/호/목을 합쳐 `조문내용` 구성

### B. PDF txt 조문 분리

PDF 병합 txt에서 아래 헤더 regex로 조문 블록을 나눕니다.

- 패턴: `제N조(제목)` 또는 `제N조의M(제목)`
- 이유: 본문 인용(`제2조제1항`)을 헤더로 오인식하는 문제를 줄이기 위해 제목 괄호를 필수로 둠

### C. 정규화 후 유사도 계산

비교 전에 양쪽 텍스트에 같은 정규화를 적용합니다.

- 푸터 제거 (`법제처 N 국가법령정보센터`)
- 개정 태그 제거 (`<개정 ...>`)
- 대괄호 주석 제거 (`[본조신설 ...]`, `[전문개정 ...]` 등)
- 공백/줄바꿈 제거, 기호 일부 통일

유사도 계산은 `SequenceMatcher` 사용:

- 각 API 조문마다 PDF 후보 블록 중 **최고 유사도**를 선택
- 최고값이 `0.95` 이상이면 통과

---

## 4) 실행 방법

프로젝트 루트에서 실행합니다.

```bash
cd /Users/choedoil/Desktop/법령
```

### 4-1. PDF 텍스트 추출

```bash
.venv/bin/python -m src.util.pdf_extract "data/pdf/소득세법(법률)(제21221호)(20260701).pdf"
```

생성 파일:

- `data/laws/pdf_extracted/<파일명>.txt`
- `data/laws/pdf_extracted/<파일명>_meta.json`
- `data/laws/pdf_extracted/<파일명>_pages/`

### 4-2. API 데이터 생성

```bash
.venv/bin/python -m src.util "112신고처리법"
```

생성 파일:

- `data/laws/api/<법령명>_<MST>.json`
- `data/laws/api/<법령명>_<MST>_articles.json`
- `data/laws/api/<법령명>_<MST>.html`
- `data/laws/api/<법령명>_<MST>_api.html`

### 4-3. 평가 실행

```bash
.venv/bin/python -m src.util.eval_pdf_vs_api \
  --api-json "data/laws/api/소득세법_280405.json" \
  --pdf-txt "data/laws/pdf_extracted/소득세법(법률)(제21221호)(20260701).txt" \
  --out "data/eval/소득세법_eval.json"
```

빠른 테스트(앞 10개 조문만):

```bash
.venv/bin/python -m src.util.eval_pdf_vs_api \
  --api-json "data/laws/api/소득세법_280405.json" \
  --pdf-txt "data/laws/pdf_extracted/소득세법(법률)(제21221호)(20260701).txt" \
  --api-limit 10 \
  --out "data/eval/소득세법_eval_quick.json"
```

---

## 5) 해석 가이드

- `avg_best_similarity`가 높아도 일부 조문 실패는 정상일 수 있습니다.
- 특히 표/수식이 이미지인 PDF는 텍스트 비교 점수가 낮게 나옵니다.
- `failures`를 보고:
  - 파싱 누락(실패)
  - 표/이미지 구간(구조적 한계)
  를 구분해서 해석하는 것이 중요합니다.

---

## 6) 현재 한계

- 이미지 기반 표/수식은 문자열 비교만으로 정확한 평가가 어렵습니다.
- 조문 헤더가 비정형인 PDF는 분리 정확도가 떨어질 수 있습니다.
- OCR 단계는 현재 평가 스크립트에 포함되어 있지 않습니다.

---

## 7) 추천 운영 방식

1. `pdf_extract.py`로 추출  
2. `eval_pdf_vs_api.py`로 자동 채점  
3. `failures` 중 표/이미지 조문은 별도 수동 검토  

이 흐름으로 운영하면 신규 PDF가 들어와도 일관된 기준으로 비교할 수 있습니다.

