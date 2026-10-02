"""RAG 부분: 가이드 문서를 벡터로 바꿔 저장하고(벡터DB), 비슷한 가이드를 찾아주는 파일.

[RAG 한 줄 요약]
    가이드 문장들을 "숫자 목록(벡터)"으로 바꿔 두면,
    질문도 숫자 목록으로 바꿔서 "가장 비슷한 가이드"를 계산으로 찾을 수 있다.

[이 파일의 구성]
    get_client()  : OpenAI 접속 객체 만들기 (.env 의 API 키 사용)
    embed()       : 문장 → 벡터 변환 (OpenAI 임베딩 API)
    VectorDB      : 벡터를 들고 있다가 비슷한 가이드를 찾아주는 클래스 (직접 구현한 벡터DB)
    load_db()     : 저장된 벡터DB 불러오기 (없거나 오래됐으면 새로 만들기)
"""

import json
import os
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

# ---------------- 설정 ----------------
BASE_DIR = Path(__file__).parent  # ai_report/ 폴더 (3팀 작업 폴더)
ROOT_DIR = BASE_DIR.parent  # 프로젝트 최상위 폴더 (.env 가 있는 곳, 세 팀 공용)
GUIDE_FILE = BASE_DIR / "data" / "guide_chunks.json"  # 전처리한 가이드 (직접 작성)
DB_FILE = BASE_DIR / "data" / "vector_db.json"  # 벡터DB 저장 파일 (자동 생성)
EMBED_MODEL = "text-embedding-3-small"  # 임베딩 모델

load_dotenv(ROOT_DIR / ".env")  # 최상위 폴더 .env 의 OPENAI_API_KEY 를 읽어 둔다


def get_client() -> OpenAI:
    """OpenAI 접속 객체를 만든다. API 키는 .env 파일에서 가져온다."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 가 없습니다. 프로젝트 최상위 폴더에 .env 파일을 만들고 키를 넣어주세요.")
    return OpenAI(api_key=api_key)


def embed(client: OpenAI, texts: list[str]) -> np.ndarray:
    """문장 여러 개를 벡터로 바꾼다. 결과 모양: (문장 수, 1536)"""
    vectors = []
    for i in range(0, len(texts), 100):  # 한 번에 100개씩 나눠서 요청
        response = client.embeddings.create(model=EMBED_MODEL, input=texts[i : i + 100])
        vectors += [d.embedding for d in response.data]
    return np.array(vectors, dtype=np.float32)


class VectorDB:
    """직접 만든 간단한 벡터DB.

    - chunks  : 가이드 조각 목록  (예: {"item_code": "U-01", "section": "조치방법", "text": "..."})
    - vectors : 각 조각을 벡터로 바꾼 값 (chunks 와 같은 순서)

    ※ 벡터 길이를 모두 1로 맞춰 두면, 내적(@) 결과가 곧 '코사인 유사도'(클수록 비슷함)가 된다.
    """

    def __init__(self, chunks: list[dict], vectors: np.ndarray):
        self.chunks = chunks
        self.vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

    def search(self, query_vector: np.ndarray, item_code: str, top_k: int = 3) -> list[dict]:
        """item_code(예: U-01) 가이드 중에서 질문과 가장 비슷한 top_k 개를 돌려준다."""
        query_vector = query_vector / np.linalg.norm(query_vector)
        scores = self.vectors @ query_vector  # 모든 조각과의 유사도를 한 번에 계산

        # 같은 항목 코드의 조각만 후보로 삼는다 (다른 항목 가이드가 섞이는 것을 방지)
        candidates = [i for i, c in enumerate(self.chunks) if c["item_code"] == item_code]
        candidates.sort(key=lambda i: scores[i], reverse=True)  # 유사도 높은 순
        return [self.chunks[i] for i in candidates[:top_k]]


def build_db(client: OpenAI) -> VectorDB:
    """guide_chunks.json 을 읽어 벡터로 바꾸고, 파일(vector_db.json)로 저장한다."""
    chunks = json.loads(GUIDE_FILE.read_text(encoding="utf-8"))
    print(f"[RAG] 가이드 {len(chunks)}개를 벡터로 변환 중...")

    # 항목코드와 섹션을 앞에 붙여야 검색이 더 정확하다
    texts = [f"{c['item_code']} {c['section']}\n{c['text']}" for c in chunks]
    vectors = embed(client, texts)

    # 저장: 가이드 내용 + 벡터를 한 파일에 같이 넣는다 (파일이 하나라 짝이 어긋날 일이 없음)
    saved = [dict(c, vector=[round(float(x), 6) for x in v]) for c, v in zip(chunks, vectors)]
    DB_FILE.write_text(
        json.dumps({"embed_model": EMBED_MODEL, "chunks": saved}, ensure_ascii=False), encoding="utf-8"
    )
    return VectorDB(chunks, vectors)


def load_db(client: OpenAI) -> VectorDB:
    """벡터DB를 돌려준다. 아래 경우에는 자동으로 새로 만든다.
    1) 저장 파일이 없을 때   2) guide_chunks.json 이 더 최근에 수정됐을 때   3) 임베딩 모델이 바뀌었을 때
    """
    if DB_FILE.exists() and DB_FILE.stat().st_mtime >= GUIDE_FILE.stat().st_mtime:
        saved = json.loads(DB_FILE.read_text(encoding="utf-8"))
        if saved["embed_model"] == EMBED_MODEL:
            vectors = np.array([c.pop("vector") for c in saved["chunks"]], dtype=np.float32)
            return VectorDB(saved["chunks"], vectors)
    return build_db(client)
