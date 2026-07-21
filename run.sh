#!/usr/bin/env bash
# 법령 웹 챗봇 실행
# 사용: ./run.sh   또는  bash run.sh

set -e
cd "$(dirname "$0")"

pick_python() {
  if [ -n "${PYTHON:-}" ] && command -v "$PYTHON" >/dev/null 2>&1; then
    echo "$PYTHON"
    return
  fi
  # pyenv 가상환경 / 버전 (이 머신에 있는 것 우선)
  for p in \
    "$HOME/.pyenv/versions/rag-chatbot/bin/python" \
    "$HOME/.pyenv/versions/3.11.6/bin/python" \
    "$HOME/.pyenv/versions/langchain-test/bin/python" \
    "$HOME/.pyenv/versions/llm-application/bin/python"
  do
    if [ -x "$p" ]; then
      echo "$p"
      return
    fi
  done
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return
  fi
  if command -v python >/dev/null 2>&1; then
    echo "python"
    return
  fi
  echo ""
}

PY="$(pick_python)"
if [ -z "$PY" ]; then
  echo "Python을 찾을 수 없습니다."
  echo "예: pyenv shell 3.11.6  후 다시 실행, 또는 PYTHON=/path/to/python ./run.sh"
  exit 1
fi

echo "Python: $PY"
echo "의존성 확인 중..."
if ! "$PY" -c "import fastapi, uvicorn, sentence_transformers" >/dev/null 2>&1; then
  echo "필요한 패키지 설치: pip install -r requirements.txt"
  "$PY" -m pip install -r requirements.txt
fi

echo "서버 시작 → http://127.0.0.1:8000"
echo "(종료: Ctrl+C)"
exec "$PY" -m src.app.api
