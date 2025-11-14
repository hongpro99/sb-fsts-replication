from __future__ import annotations
import os, glob, textwrap
from typing import List, Dict, Any
from pypdf import PdfReader

from langchain_openai import AzureChatOpenAI
from qdrant_client import QdrantClient, models
from sentence_transformers import CrossEncoder
from dotenv import load_dotenv
import os, time
import pdfplumber

load_dotenv()

COLLECTION = "local_rag"
reranker = CrossEncoder("BAAI/bge-reranker-base")
# ------------------------------------------------------------
# 0) Qdrant 클라이언트 생성- FastEmbed
# ------------------------------------------------------------
def get_client() -> QdrantClient:
    # ① 아주 빠른 테스트: 인메모리
    client = QdrantClient(host="localhost", port=6333)
    
    # ② 디스크 영속화 예시
    # client = QdrantClient(path="./qdrant-db")

    # ③ Qdrant Cloud 예시
    # client = QdrantClient(
    #     url=os.environ["QDRANT_URL"],
    #     api_key=os.environ["QDRANT_API_KEY"],
    # )
    return client

# ------------------------------------------------------------
# 1) 간단한 문서 로더(파싱) & 청킹
# ------------------------------------------------------------
def _chunk_text(text: str, chunk_size: int = 800, chunk_overlap: int = 120):
    i = 0
    n = len(text)
    while i < n:
        j = min(i + chunk_size, n)
        yield text[i:j]
        if j >= n:
            break
        i = j - chunk_overlap

def get_indexed_files(client: QdrantClient):
    """이미 인덱싱된 파일들의 path, mtime을 딕셔너리로 반환"""
    existing = {}
    
    # 컬렉션이 아직 없으면 그냥 빈 dict 리턴
    if not client.collection_exists(COLLECTION):
        return existing
    
    
    scroll_res, _ = client.scroll(
        collection_name=COLLECTION,
        with_payload=True,
        limit=99999
    )
    for point in scroll_res:
        payload = point.payload or {}
        path = payload.get("path")
        mtime = payload.get("mtime")
        if path and mtime:
            existing[path] = mtime
    return existing

def load_texts_from_folder(folder: str, existing_files: dict, chunk_size: int = 800, chunk_overlap: int = 120):
    docs = []
    paths = glob.glob(f"{folder}/**/*.*", recursive=True)
    for p in paths:
        ext = os.path.splitext(p)[1].lower()
        if ext not in [".txt", ".md", ".pdf"]:
            continue

        modified = os.path.getmtime(p)
        # ✅ 동일 path + 동일 mtime이면 스킵
        if existing_files.get(p) == modified:
            print(f"[skip] unchanged: {p}")
            continue

        # ---- 파일별 로딩 ----
        if ext in [".txt", ".md"]:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read().strip()
            chunks = _chunk_text(raw, chunk_size, chunk_overlap)
            for chunk in chunks:
                docs.append({
                    "text": chunk,
                    "metadata": {
                        "source": os.path.basename(p),
                        "path": p,
                        "mtime": modified
                    }
                })

        elif ext == ".pdf":
            try:
                with pdfplumber.open(p) as pdf:
                    for page_idx, page in enumerate(pdf.pages):
                        text = page.extract_text() or ""
                        tables = page.extract_tables() or []

                        # 표가 있으면 텍스트로 변환해 추가
                        table_text = ""
                        for t in tables:
                            if not t:
                                continue
                            for row in t:
                                if row:
                                    table_text += " | ".join([cell or "" for cell in row]) + "\n"

                        combined = (text + "\n" + table_text).strip()
                        if not combined:
                            continue

                        for chunk in _chunk_text(combined, chunk_size, chunk_overlap):
                            docs.append({
                                "text": chunk,
                                "metadata": {
                                    "source": os.path.basename(p),
                                    "path": p,
                                    "page": page_idx + 1,
                                    "mime": modified
                                }
                            })
            except Exception as e:
                print(f"[warn] PDF 읽기 실패: {p} ({e})")

        else:
            continue
        
    print(f"총 {len(docs)}개 청크 생성 완료.")    
    return docs

COLLECTION = "local_rag"

# ------------------------------------------------------------
# 2) 인덱싱: add()는 없으면 컬렉션을 자동 생성
#    documents, metadata, ids만 넘기면 끝!
# ------------------------------------------------------------
def build_index(client: QdrantClient, docs: List[Dict[str, Any]]):
    texts   = [d["text"] for d in docs]
    metas   = [d["metadata"] for d in docs]

    # # 2️⃣ 컬렉션 생성 (없으면 자동 생성됨)
    # COLLECTION = "local_rag"
    # if not client.collection_exists(COLLECTION):
    #     client.create_collection(
    #         collection_name=COLLECTION,
    #         vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
    #     )
    
    # add()는 FastEmbed로 임베딩 생성 + 업서트까지 한 번에 처리
    # 반환값은 생성된 point ID 목록
    client.add(
        collection_name=COLLECTION,
        documents=texts,
        metadata=metas,
        # ids=[...],  # 직접 ID 지정하고 싶으면 주석 해제
        # batch_size=64, parallel=None 등도 조정 가능
    )

# ------------------------------------------------------------
# 3) 검색(리트리벌): query()로 텍스트 쿼리
#    query_filter로 메타데이터 필터도 가능
# ------------------------------------------------------------
def retrieve(client: QdrantClient, query: str, top_k: int = 5, source_only: str | None = None):
    qfilter = None
    if source_only:
        qfilter = models.Filter(
            must=[models.FieldCondition(key="source", match=models.MatchValue(value=source_only))]
        )

    res = client.query(
        collection_name=COLLECTION,
        query_text=query,
        limit=top_k,
        query_filter=qfilter,
    )
    print(f"res : {res}")
    # client.query() 결과는 point들 포함
    passages = []
    for pt in res:
        passages.append({
            "text": pt.metadata.get("document") or pt.metadata.get("text") or "",  # add()는 기본적으로 'document'에 본문 저장
            "score": pt.score,
            "source": pt.metadata.get("source"),
            "path": pt.metadata.get("path"),
            "page": pt.metadata.get("page")
        })
    return passages

# ------------------------------------------------------------
# 4) Cross-Encoder 기반 Reranker
#    
# ------------------------------------------------------------
def rerank_passages(query, passages):
    pairs = [(query, p["text"]) for p in passages]
    scores = reranker.predict(pairs)
    for p, s in zip(passages, scores):
        p["rerank_score"] = float(s)
    return sorted(passages, key=lambda x: x["rerank_score"], reverse=True)


# ------------------------------------------------------------
# 5) 매우 단순한 생성기(LLM 호출 자리)
# ------------------------------------------------------------
def generate_answer(query: str, passages: List[Dict[str, Any]]) -> str:
    context = "\n\n".join(
        f"[{i+1}] ({p['score']:.3f}) {p['source']} :: {p['text']}"
        for i, p in enumerate(passages)
    )

    llm = AzureChatOpenAI(
        azure_deployment="gpt-4o-mini",
        azure_endpoint="https://sb-azure-openai-studio.openai.azure.com/",
        api_version="2024-10-21",
        temperature=0
        )

    prompt = f"""당신은 주어진 문맥으로만 답하는 어시스턴트입니다.
질문: {query}

문맥:
{context}

지침:
- 문맥에 근거한 답만 작성
- 필요한 경우 [번호]로 출처 표시
"""

    # 여기서 실제 LLM 호출로 바꾸세요.
    # 예: OpenAI Responses API / local LLM 등
    # 일단은 데모로 '추출형' 요약을 리턴:
    llm_response = llm.invoke(prompt)
    return (
        llm_response.content
        if hasattr(llm_response, "content")
        else str(llm_response)
    )
    
def run_rag_pipeline(query: str) -> str:
    client = get_client()
    passages = retrieve(client, query, top_k=5)
    reranked = rerank_passages(query, passages)
    return generate_answer(query, reranked[:5])

# ------------------------------------------------------------
# 5) 파이프라인 실행
# ------------------------------------------------------------
def main():
    client = get_client()
    
    # if not client.collection_exists(COLLECTION):
    #     client.create_collection(
    #         collection_name=COLLECTION,
    #         vectors_config=models.VectorParams(
    #             size=384,
    #             distance=models.Distance.COSINE
    #         )
    #     )
    #     print(f"[init] Qdrant collection '{COLLECTION}' created.")
        
    existing_files = get_indexed_files(client)
    # 1) 인덱싱
    docs = load_texts_from_folder("./docs", existing_files)  # ./docs 폴더에서 txt/md/pdf를 읽고, 청킹

    if docs:
        build_index(client, docs) #FastEmbed가 자동으로 문장 임베딩을 만들고, Qdrant 컬렉션에 업서트
    #------------------------- 사전준비------------------------------------------------- ->     별도 CLI / 배치 작업으로 주기적으로 실행(FastAPI background task) 



    # 2) Qdrant 검색
    # query = "코스메카코리아의 2025년 매출 얼마야?"
    # passages = retrieve(client, query, top_k=5) #query_text에 문자열을 넣으면 내장 임베딩이 생성되어 유사도 검색이 수행
    # print("== Top-K 문서 ==")
    # for i, p in enumerate(passages, 1):
    #     print(f"[{i}] {p['source']} {p['page']}  score={p['score']:.3f}")

    # # 3) Reranking
    # reranked = rerank_passages(query, passages)
    # print("\n== Re-ranked ==")
    # for i, p in enumerate(reranked[:5], 1):
    #     print(f"[{i}] {p['source']} {p['page']}  rerank={p['rerank_score']:.3f}")
        
    #  # 4) LLM 생성    
    # print("\n== 생성 결과 ==")
    # print(generate_answer(query, reranked[:5]))

if __name__ == "__main__":
    main()
