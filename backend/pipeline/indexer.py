import hashlib
from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter

from pipeline.embedder import get_embeddings
from db import qdrant_client as qdrant_db
from db import pgvector_client as pg_db


def _make_doc_id(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()


def _chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return splitter.split_text(text)


def index_documents(
    documents: List[dict],
    qdrant_client,
    pg_conn,
) -> dict:
    """
    documents: [{"content": str, "metadata": dict}, ...]
    Returns stats: {"chunks": int}
    """
    all_chunks = []
    all_metadatas = []

    for doc in documents:
        chunks = _chunk_text(doc["content"])
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_metadatas.append({**doc.get("metadata", {}), "chunk_index": i})

    if not all_chunks:
        return {"chunks": 0}

    embeddings = get_embeddings(all_chunks)
    doc_ids = [_make_doc_id(c) for c in all_chunks]

    # Qdrant upsert
    qdrant_ids = [abs(hash(doc_id)) % (2**63) for doc_id in doc_ids]
    qdrant_db.upsert_documents(
        qdrant_client,
        ids=qdrant_ids,
        vectors=embeddings,
        payloads=[{"doc_id": doc_ids[i], "content": all_chunks[i], **all_metadatas[i]} for i in range(len(all_chunks))],
    )

    # pgvector upsert
    pg_db.upsert_documents(
        pg_conn,
        doc_ids=doc_ids,
        contents=all_chunks,
        metadatas=all_metadatas,
        embeddings=embeddings,
    )

    return {"chunks": len(all_chunks)}
