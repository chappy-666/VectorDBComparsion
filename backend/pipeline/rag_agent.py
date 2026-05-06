import os
import time
from typing import TypedDict, List, Optional

from langgraph.graph import StateGraph, END
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

from pipeline.embedder import get_embedding
from db import qdrant_client as qdrant_db
from db import pgvector_client as pg_db

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_MODEL = "llama3.2"
RELEVANCE_THRESHOLD = 0.5
MAX_RETRIES = 2


class RAGState(TypedDict):
    # 入力
    query: str
    db: str        # "qdrant" | "pgvector" | "both"
    top_k: int
    # 内部状態
    refined_query: str
    retry_count: int
    search_results: List[dict]
    is_sufficient: bool
    # 出力
    answer: str
    qdrant_latency_ms: Optional[float]
    pgvector_latency_ms: Optional[float]


def build_rag_graph(qdrant_client, pg_conn):
    llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL)

    def query_analyzer(state: RAGState) -> dict:
        """初回はクエリをそのまま使用。リトライ時はLLMでクエリを言い換える。"""
        if state["retry_count"] == 0:
            return {"refined_query": state["query"]}

        response = llm.invoke([
            SystemMessage(content=(
                "あなたは検索クエリの最適化専門家です。"
                "与えられたクエリを、より関連性の高いドキュメントを取得できるよう言い換えてください。"
                "言い換えたクエリのみを返し、説明は不要です。"
            )),
            HumanMessage(content=(
                f"元のクエリ: {state['query']}\n"
                "前回の検索では十分な関連性のある結果が得られませんでした。"
                "別の表現でクエリを言い換えてください。"
            )),
        ])
        return {"refined_query": response.content.strip()}

    def retriever(state: RAGState) -> dict:
        """refined_queryをベクトル化し、指定DBから検索する。"""
        query_vec = get_embedding(state["refined_query"])
        results = []
        qdrant_latency_ms = None
        pgvector_latency_ms = None

        if state["db"] in ("qdrant", "both"):
            t0 = time.perf_counter()
            raw = qdrant_db.search(qdrant_client, query_vec, top_k=state["top_k"])
            qdrant_latency_ms = (time.perf_counter() - t0) * 1000
            for r in raw:
                results.append({
                    "doc_id": str(r["payload"].get("doc_id", r["id"])),
                    "content": r["payload"].get("content", ""),
                    "score": r["score"],
                    "metadata": {k: v for k, v in r["payload"].items() if k not in ("doc_id", "content")},
                    "source_db": "qdrant",
                })

        if state["db"] in ("pgvector", "both"):
            t0 = time.perf_counter()
            raw = pg_db.search(pg_conn, query_vec, top_k=state["top_k"])
            pgvector_latency_ms = (time.perf_counter() - t0) * 1000
            seen = {r["doc_id"] for r in results}
            for r in raw:
                if r["doc_id"] not in seen:
                    results.append({
                        "doc_id": r["doc_id"],
                        "content": r["content"],
                        "score": r["score"],
                        "metadata": r["metadata"],
                        "source_db": "pgvector",
                    })
                    seen.add(r["doc_id"])

        results.sort(key=lambda x: x["score"], reverse=True)
        return {
            "search_results": results,
            "qdrant_latency_ms": qdrant_latency_ms,
            "pgvector_latency_ms": pgvector_latency_ms,
        }

    def evaluator(state: RAGState) -> dict:
        """上位スコアの平均でリトライ判定する。MAX_RETRIES到達時は強制通過。"""
        results = state["search_results"]
        retry_count = state["retry_count"]

        if not results or retry_count >= MAX_RETRIES:
            return {"is_sufficient": True}

        top_scores = [r["score"] for r in results[:3]]
        avg_score = sum(top_scores) / len(top_scores)

        if avg_score >= RELEVANCE_THRESHOLD:
            return {"is_sufficient": True}

        return {"is_sufficient": False, "retry_count": retry_count + 1}

    def generator(state: RAGState) -> dict:
        """検索結果をコンテキストとしてOllamaで回答を生成する。"""
        results = state["search_results"]

        if not results:
            return {"answer": "関連するドキュメントが見つかりませんでした。"}

        context = "\n\n".join(
            f"[{i}] {r['content']}" for i, r in enumerate(results[:5], 1)
        )

        response = llm.invoke([
            SystemMessage(content=(
                "あなたは優秀なアシスタントです。"
                "以下の検索結果をもとに、ユーザーの質問に日本語で回答してください。"
                "検索結果に含まれない情報は使わないでください。"
            )),
            HumanMessage(content=f"質問: {state['query']}\n\n検索結果:\n{context}"),
        ])
        return {"answer": response.content.strip()}

    def route_after_evaluator(state: RAGState) -> str:
        return "generator" if state["is_sufficient"] else "query_analyzer"

    graph = StateGraph(RAGState)
    graph.add_node("query_analyzer", query_analyzer)
    graph.add_node("retriever", retriever)
    graph.add_node("evaluator", evaluator)
    graph.add_node("generator", generator)

    graph.set_entry_point("query_analyzer")
    graph.add_edge("query_analyzer", "retriever")
    graph.add_edge("retriever", "evaluator")
    graph.add_conditional_edges(
        "evaluator",
        route_after_evaluator,
        {"generator": "generator", "query_analyzer": "query_analyzer"},
    )
    graph.add_edge("generator", END)

    return graph.compile()
