# local_index.py
from __future__ import annotations
from pathlib import Path
from typing import Sequence, Dict, List
import hashlib, json

from langchain_community.document_loaders import (
    TextLoader,
    PDFPlumberLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredMarkdownLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

MANIFEST_PATH_DEFAULT = "./.chromadb/local-rag-manifest.json"


# === 유틸리티 ===
def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _load_manifest(path: str) -> Dict[str, Dict]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_manifest(path: str, manifest: Dict[str, Dict]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _scan_files(data_dirs: Sequence[str]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for d in data_dirs:
        for f in Path(d).rglob("*"):
            if f.is_file():
                try:
                    out[str(f.resolve())] = f.stat().st_mtime
                except Exception:
                    pass
    return out


# === 확장자별 로더 ===
def _load_all_files(data_dirs: Sequence[str], target: set[str]) -> List:
    """파일 확장자에 관계없이 텍스트/PDF/DOCX/MD 파일 로드."""
    docs = []
    for d in data_dirs:
        for path in Path(d).rglob("*"):
            if not path.is_file():
                continue
            src = str(path.resolve())
            if src not in target:
                continue
            ext = path.suffix.lower()
            try:
                if ext == ".txt":
                    loader = TextLoader(str(path), encoding="utf-8")
                elif ext == ".pdf":
                    loader = PDFPlumberLoader(str(path))
                elif ext in [".docx", ".doc"]:
                    loader = UnstructuredWordDocumentLoader(str(path))
                elif ext in [".md", ".markdown"]:
                    loader = UnstructuredMarkdownLoader(str(path))
                else:
                    # 기본적으로 텍스트로 시도
                    loader = TextLoader(str(path), encoding="utf-8", autodetect_encoding=True)
                docs.extend(loader.load())
            except Exception as e:
                print(f"⚠️ {path.name} 로드 실패: {e}")
    return docs


# === 메인 인덱싱 함수 ===
def build_or_update_index(
    data_dirs: Sequence[str],
    persist_dir: str = "./.chromadb/local-rag",
    collection_name: str = "local-rag",
    manifest_path: str = MANIFEST_PATH_DEFAULT,
    chunk_size: int = 1000,
    chunk_overlap: int = 120,
):
    print("🚀 RAG incremental indexing start")

    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    vectorstore = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=persist_dir,
    )

    manifest = _load_manifest(manifest_path)
    current = _scan_files(data_dirs)

    changed_files, deleted_files = [], []
    for src, mtime in current.items():
        if src not in manifest or manifest[src].get("mtime") != mtime:
            changed_files.append(src)
    for src in list(manifest.keys()):
        if src not in current:
            deleted_files.append(src)

    print(f"📁 changed={len(changed_files)} deleted={len(deleted_files)}")

    # 삭제 반영
    if deleted_files:
        try:
            ids_to_delete: List[str] = []
            for src in deleted_files:
                ids_to_delete.extend(manifest.get(src, {}).get("chunk_ids", []))
            if ids_to_delete:
                vectorstore._collection.delete(ids=ids_to_delete)
                print(f"🗑️ deleted chunks: {len(ids_to_delete)}")
            for src in deleted_files:
                manifest.pop(src, None)
        except Exception as e:
            print(f"⚠️ delete skipped: {e}")

    # 변경 파일 로드 및 청크화
    new_docs, ids = [], []
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    target = set(changed_files)

    if target:
        docs = _load_all_files(data_dirs, target)
        chunks = splitter.split_documents(docs)
        for i, doc in enumerate(chunks):
            src = str(Path(doc.metadata.get("source", "")).resolve())
            mtime = current.get(src, 0.0)
            file_sig = _hash(f"{src}:{mtime}")
            cid = f"{file_sig}#{i}"
            doc.metadata.update(
                {"source": src, "mtime": mtime, "file_sig": file_sig, "chunk_index": i}
            )
            new_docs.append(doc)
            ids.append(cid)

    print(f"🧩 new/updated chunks: {len(new_docs)}")

    # 벡터스토어 업데이트
    if new_docs:
        vectorstore.add_documents(new_docs, ids=ids)
        per_file: Dict[str, List[str]] = {}
        for doc, cid in zip(new_docs, ids):
            per_file.setdefault(doc.metadata["source"], []).append(cid)
        for src, mtime in current.items():
            if src in per_file:
                manifest[src] = {"mtime": mtime, "chunk_ids": per_file[src]}

    _save_manifest(manifest_path, manifest)
    print("✅ indexing done")
    return vectorstore
