"""
공통 설정
=========
임베딩 모델·법령 폴더·Ollama 등 전 모듈이 공유하는 값을 한곳에 둡니다.
모델을 바꾸면 여기만 수정하면 됩니다.
"""
from pathlib import Path

# 프로젝트 루트 (src/ 의 상위)
ROOT = Path(__file__).resolve().parent.parent

# 법령 텍스트 폴더
LAWS_DIR = ROOT / "data" / "laws"

# 정답 질문 세트
QUESTIONS_PATH = ROOT / "data" / "questions.json"

# 노트북 CPU용 한국어 임베딩 모델
# 대안: "intfloat/multilingual-e5-small"  (문장 앞에 "query: " / "passage: " 접두가 유리)
EMBEDDING_MODEL = "jhgan/ko-sroberta-multitask"

# 로컬 LLM (Ollama)
OLLAMA_URL = "http://localhost:11434/api/generate"
LLM_MODEL = "qwen2.5:3b"  # 또는 "gemma2:2b"

# 검색 기본 top-k
DEFAULT_TOP_K = 1
