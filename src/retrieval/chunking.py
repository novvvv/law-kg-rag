# ------------------------------------------------------------------
# [method] load_chunks
# * logic * 
# - data/laws/의 .txt 파일을 자른다. 
# - 줄 맨 앞의 "제12조" 같은 패턴만 자른다. 
# - 문장 중간의 "제 80조에 따라" 같은 패턴은 청킹하지 않는다. 
# ------------------------------------------------------------------

from __future__ import annotations
import re
from pathlib import Path
from ..config import LAWS_DIR


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
