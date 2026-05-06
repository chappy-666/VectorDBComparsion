from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import List, Optional
import time

from db import qdrant_client as qdrant_db
from db import pgvector_client as pg_db
from pipeline.embedder import get_embedding
from pipeline.indexer import index_documents

# --- DB clients (initialized at startup) ---
_qdrant = None
_pg_conn = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _qdrant, _pg_conn
    _qdrant = qdrant_db.get_client()
    qdrant_db.ensure_collection(_qdrant)

    _pg_conn = pg_db.get_connection()
    pg_db.ensure_table(_pg_conn)

    yield

    if _pg_conn:
        _pg_conn.close()


app = FastAPI(title="VectorDB Benchmark API", lifespan=lifespan)


# --- Request / Response models ---

class IndexRequest(BaseModel):
    documents: List[dict]  # [{"content": str, "metadata": dict}]


class SearchRequest(BaseModel):
    query: str
    db: str = "both"  # "qdrant" | "pgvector" | "both"
    top_k: int = 5


class SearchResult(BaseModel):
    doc_id: str
    content: str
    score: float
    metadata: Optional[dict] = None


class SearchResponse(BaseModel):
    query: str
    qdrant: Optional[List[SearchResult]] = None
    pgvector: Optional[List[SearchResult]] = None
    qdrant_latency_ms: Optional[float] = None
    pgvector_latency_ms: Optional[float] = None


# --- Endpoints ---

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/index")
def index(req: IndexRequest):
    stats = index_documents(req.documents, _qdrant, _pg_conn)
    return {"indexed_chunks": stats["chunks"]}


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    query_vec = get_embedding(req.query)
    response = SearchResponse(query=req.query)

    if req.db in ("qdrant", "both"):
        t0 = time.perf_counter()
        raw = qdrant_db.search(_qdrant, query_vec, top_k=req.top_k)
        response.qdrant_latency_ms = (time.perf_counter() - t0) * 1000
        response.qdrant = [
            # ** List Comprehension **
            SearchResult(
                doc_id=str(r["payload"].get("doc_id", r["id"])),
                content=r["payload"].get("content", ""),
                score=r["score"],
                metadata={k: v for k, v in r["payload"].items() if k not in ("doc_id", "content")},
            )
            for r in raw
        ]

    if req.db in ("pgvector", "both"):
        t0 = time.perf_counter()
        raw = pg_db.search(_pg_conn, query_vec, top_k=req.top_k)
        response.pgvector_latency_ms = (time.perf_counter() - t0) * 1000
        response.pgvector = [
            # ** List Comprehension **
            SearchResult(
                doc_id=r["doc_id"],
                content=r["content"],
                score=r["score"],
                metadata=r["metadata"],
            )
            for r in raw
        ]

    return response
