from fastapi import FastAPI
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import List, Optional
import time

from db import qdrant_client as qdrant_db
from db import pgvector_client as pg_db
from pipeline.embedder import get_embedding
from pipeline.indexer import index_documents
from pipeline.rag_agent import build_rag_graph, RAGState

# --- DB clients (initialized at startup) ---
_qdrant = None
_pg_conn = None
_rag_graph = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _qdrant, _pg_conn, _rag_graph
    _qdrant = qdrant_db.get_client()
    qdrant_db.ensure_collection(_qdrant)

    _pg_conn = pg_db.get_connection()
    pg_db.ensure_table(_pg_conn)

    _rag_graph = build_rag_graph(_qdrant, _pg_conn)

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


class RAGRequest(BaseModel):
    query: str
    db: str = "both"  # "qdrant" | "pgvector" | "both"
    top_k: int = 5


class RAGResponse(BaseModel):
    query: str
    answer: str
    sources: List[SearchResult]
    retry_count: int
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
            SearchResult(
                doc_id=r["doc_id"],
                content=r["content"],
                score=r["score"],
                metadata=r["metadata"],
            )
            for r in raw
        ]

    return response


@app.post("/rag", response_model=RAGResponse)
def rag(req: RAGRequest):
    initial_state: RAGState = {
        "query": req.query,
        "db": req.db,
        "top_k": req.top_k,
        "refined_query": "",
        "retry_count": 0,
        "search_results": [],
        "is_sufficient": False,
        "answer": "",
        "qdrant_latency_ms": None,
        "pgvector_latency_ms": None,
    }
    final_state = _rag_graph.invoke(initial_state)

    sources = [
        SearchResult(
            doc_id=r["doc_id"],
            content=r["content"],
            score=r["score"],
            metadata=r.get("metadata"),
        )
        for r in final_state["search_results"]
    ]

    return RAGResponse(
        query=final_state["query"],
        answer=final_state["answer"],
        sources=sources,
        retry_count=final_state["retry_count"],
        qdrant_latency_ms=final_state.get("qdrant_latency_ms"),
        pgvector_latency_ms=final_state.get("pgvector_latency_ms"),
    )
