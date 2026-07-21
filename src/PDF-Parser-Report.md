pyPDF2 -> default
pdfplumber -> PDF 내의 모든 글자와 단어의 정확한 X,Y좌표를 딕셔너리 형태로 반환한다.
해당 로직을 통해서 어떤 단어가 -로 끝나고, 바로 다음 단어의 Y좌표가 조금 아래 있으면서 시작점 부근에 위치한다면 두 단어를 하나로 합친다.
와 같은 로직을 짤 수 있다.

PyMuPDF -> 단어뿐만 아니라 문단 단위의 블록 구조를 파악하는 성능이 뛰어나다.
또한 다른 라이브러리에 비해서 처리 속도가 압도적으로 빠르기에, 대량의 문서에서 하이픈과 줄바꿈 문자를 정규표현식으로 치환하는 전처리 작업을 수행할 때 가장 많이 애용된다.

---

PDF Table/Image Parsing 전략

1. 레이아웃/그리드 기반 파서 (표준)
   표를 둘러싼 선이나 글자들의 여백/정렬 상태를 수학적으로 계산하여 표 구조를 역추적하는 라이브러리
   ex) pdfplumber, Camelot, Tabula-py
   장점 : 텍스트로 이루어진 깔끔한 표는 95%이상의 정확도로 JSON 형태로 완벽 변환해준다.

2. OCR / Document / LLM AI (Scan or Image)
   컴퓨터 비전 기술을 도입하여 표의 선과 글자를 시각적으로 인식하여 표 구조를 렌더링
   한계점 : 내부 사내망에서는 도입하기에 한계가 있음

[기존 채점방식]
SequenceMatcher -> 파이썬에서 두 문장이 얼마나 비슷한지 비율을 계산하는 라이브러리로 임계값 유사도가 95% 이상이면 합격처리
API에서 준 정답지가 비어있으면 파서가 뭘 긁어오던 정답처리

---

1단계: 추출 (라이브러리)
기본: pdfplumber (좌표, 표, 하이픈 복원)
대량/속도 필요 시: PyMuPDF 병행
여기서 목표는 “깨끗한 plain text + 표 후보 영역”
2단계: 구조화 (자체 파서, 얇게 시작)
제\d+조, ①, 1., 가. 패턴으로 분리
전문, 삭제 조문 필터
표/이미지 구간은 type: table_or_formula 블록으로 따로 태깅
3단계: RAG 저장
chunk 단위 = 조문 또는 항 (페이지 단위 X)
메타데이터: 법령명(추정), 조문표시, 페이지, block_type
4단계: 품질 방어
추출 텍스트가 너무 짧으면 “스캔본/OCR 필요” 안내
표/수식 블록은 답변 시 “원문 표 확인 필요” 같은 disclaimer

---

## Evaluation Data Script

### 입력 파일 (페이지 txt 134개 X → 전체 txt 1개 O)

```
ground_truth = data/laws/api/소득세법_280405_articles.json   # API 정답 (조문 326개)
parsed_text  = data/laws/pdf_extracted/소득세법(...).txt       # PDF 전체 추출본 1개
```

- `_pages/page_*.txt` → 디버깅용. 평가에는 **합친 txt**만 사용
- `_meta.json` → 이미지 페이지 위치 참고용

### 비교 단위: 페이지가 아니라 **조문**

| | 정답 (API) | 파싱 (PDF) |
|---|---|---|
| 단위 | `articles[i].조문표시` | `제\d+조` regex로 split |
| 내용 | `articles[i].조문내용` | 분리된 조문 블록 |
| 매칭 키 | `제1조(목적)` | `제1조` |

페이지 수(134) ≠ 조문 수(326) 이므로 **페이지 1:1 비교는 하지 않음**.

### 평가 흐름

```
PDF 전체 txt
  → 조문 분리 (자체 파서)
  → 정규화
  → articles.json 조문과 유사도 비교 (SequenceMatcher)
  → 리포트 JSON 저장
```

### 정규화 (양쪽 동일 규칙)

- 공백·줄바꿈 통일
- `<개정 2012. 1. 1.>` 제거
- `법제처 N 국가법령정보센터` 푸터 제거
- `<img>`, `┌─┐` 박스문자 → 표/이미지 블록은 **별도 등급** (95% 문자열 비교 제외)

### 비교 제외 (필터)

- `조문여부 == "전문"` (장/절 제목)
- `제N조 삭제` 예고 조문
- 표/이미지 구간 (`<img>`, ASCII 표)

### 매칭 방식 (zip 금지)

정답 조문 1개마다 파싱 조문 **전체**와 유사도 계산 → 최고값 사용.

```python
from difflib import SequenceMatcher

THRESHOLD = 0.95

for target in api_articles:
    best = max(
        SequenceMatcher(None, norm(target["조문내용"]), norm(p["text"])).ratio()
        for p in pdf_articles
    )
    passed = best >= THRESHOLD
```

### 소득세법 실측 참고 (pdfplumber)

| 항목 | 결과 |
|---|---|
| 일반 조문 텍스트 | 추출 OK (~246K자) |
| `extract_tables()` | 0개 (표가 이미지) |
| 이미지 페이지 | 26페이지 (세율표·계산식 등) |

→ 제47조(근로소득공제) 등 **표 조문은 텍스트만 있고 표 숫자는 누락** → 유사도 낮게 나올 수 있음 (정상)

### 리포트 출력 예시

`data/eval/소득세법_report.json`

```json
{
  "법령명": "소득세법",
  "정답_조문수": 326,
  "비교_대상": 298,
  "통과_95pct": 270,
  "실패": 28,
  "제외_전문": 15,
  "제외_표이미지": 13,
  "평균_유사도": 0.94,
  "실패_목록": [
    {
      "조문": "제47조(근로소득공제)",
      "유사도": 0.62,
      "사유": "표가 이미지로만 존재, PDF 텍스트에 표 내용 없음"
    }
  ]
}
```

### 실행 예시 (예정)

```bash
# PDF 추출
.venv/bin/python -m src.util.pdf_extract data/pdf/소득세법.pdf

# API 정답 (이미 있으면 생략)
.venv/bin/python -m src.util 소득세법

# 평가 (구현 예정)
.venv/bin/python -m src.util.eval_parser \
  --truth data/laws/api/소득세법_280405_articles.json \
  --parsed data/laws/pdf_extracted/소득세법_280405.txt
```

