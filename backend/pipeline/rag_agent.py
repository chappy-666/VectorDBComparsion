import os
import time
import json
import queue as _queue
import threading
from typing import TypedDict, List, Optional, Generator

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
    query: str
    db: str
    top_k: int
    refined_query: str
    retry_count: int
    search_results: List[dict]
    is_sufficient: bool
    answer: str
    qdrant_latency_ms: Optional[float]
    pgvector_latency_ms: Optional[float]


def run_rag_stream(
    qdrant_client,
    pg_conn,
    query: str,
    db: str,
    top_k: int,
) -> Generator[str, None, None]:
    """SSE形式の文字列をyieldするジェネレータ。LangGraphの各ノード実行時にイベントを配信する。"""

    event_queue: _queue.Queue[Optional[str]] = _queue.Queue()
    llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL)

    def emit(event_type: str, data: dict) -> None:
        event_queue.put(
            f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        )

    # ── ノード定義 ──────────────────────────────────────────────────────────────

    def query_analyzer(state: RAGState) -> dict:
        if state["retry_count"] == 0:
            emit("step", {"step": "query_analyzer", "message": "クエリを解析中..."})
            return {"refined_query": state["query"]}

        emit("step", {"step": "query_analyzer", "message": "クエリを再構築中..."})
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
        refined = response.content.strip()
        emit("step", {"step": "query_analyzer", "message": f"再構築クエリ: {refined}"})
        return {"refined_query": refined}

    def retriever(state: RAGState) -> dict:
        query_vec = get_embedding(state["refined_query"])
        results = []
        qdrant_latency_ms = None
        pgvector_latency_ms = None

        if state["db"] in ("qdrant", "both"):
            emit("step", {"step": "retriever", "message": "Qdrantを検索中..."})
            t0 = time.perf_counter()
            raw = qdrant_db.search(qdrant_client, query_vec, top_k=state["top_k"])
            qdrant_latency_ms = (time.perf_counter() - t0) * 1000
            emit("step", {
                "step": "retriever",
                "message": "Qdrant検索完了",
                "db": "qdrant",
                "latency_ms": round(qdrant_latency_ms, 2),
            })
            for r in raw:
                results.append({
                    "doc_id": str(r["payload"].get("doc_id", r["id"])),
                    "content": r["payload"].get("content", ""),
                    "score": r["score"],
                    "metadata": {k: v for k, v in r["payload"].items() if k not in ("doc_id", "content")},
                    "source_db": "qdrant",
                })

        if state["db"] in ("pgvector", "both"):
            emit("step", {"step": "retriever", "message": "pgvectorを検索中..."})
            t0 = time.perf_counter()
            raw = pg_db.search(pg_conn, query_vec, top_k=state["top_k"])
            pgvector_latency_ms = (time.perf_counter() - t0) * 1000
            emit("step", {
                "step": "retriever",
                "message": "pgvector検索完了",
                "db": "pgvector",
                "latency_ms": round(pgvector_latency_ms, 2),
            })
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
        emit("step", {"step": "evaluator", "message": "検索結果を評価中..."})
        results = state["search_results"]
        retry_count = state["retry_count"]

        if not results or retry_count >= MAX_RETRIES:
            return {"is_sufficient": True}

        top_scores = [r["score"] for r in results[:3]]
        avg_score = sum(top_scores) / len(top_scores)

        if avg_score >= RELEVANCE_THRESHOLD:
            return {"is_sufficient": True}

        emit("step", {
            "step": "evaluator",
            "message": f"スコア不足 (avg={avg_score:.3f}) — クエリを再構築します",
        })
        return {"is_sufficient": False, "retry_count": retry_count + 1}

    def generator(state: RAGState) -> dict:
        emit("step", {"step": "generator", "message": "回答を生成中..."})
        results = state["search_results"]

        if not results:
            answer = "関連するドキュメントが見つかりませんでした。"
            emit("token", {"token": answer})
            return {"answer": answer}

        context = "\n\n".join(
            f"[{i}] {r['content']}" for i, r in enumerate(results[:5], 1)
        )

        full_answer = ""
        for chunk in llm.stream([
            SystemMessage(content=(
                "あなたは優秀なアシスタントです。"
                "以下の検索結果をもとに、ユーザーの質問に日本語で回答してください。"
                "検索結果に含まれない情報は使わないでください。"
            )),
            HumanMessage(content=f"質問: {state['query']}\n\n検索結果:\n{context}"),
        ]):
            token = chunk.content
            if token:
                emit("token", {"token": token})
                full_answer += token

        return {"answer": full_answer}

    def route_after_evaluator(state: RAGState) -> str:
        return "generator" if state["is_sufficient"] else "query_analyzer"

    # ── グラフ構築 ──────────────────────────────────────────────────────────────

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
    compiled = graph.compile()

    initial_state: RAGState = {
        "query": query,
        "db": db,
        "top_k": top_k,
        "refined_query": "",
        "retry_count": 0,
        "search_results": [],
        "is_sufficient": False,
        "answer": "",
        "qdrant_latency_ms": None,
        "pgvector_latency_ms": None,
    }

    # ── グラフを別スレッドで実行しイベントをキューに流す ─────────────────────────

    final_state_holder: dict = {}

    def _run() -> None:
        try:
            final_state_holder["result"] = compiled.invoke(initial_state)
        except Exception as exc:
            emit("error", {"message": str(exc)})
        finally:
            event_queue.put(None)  # 終了シグナル

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    while True:
        event = event_queue.get()
        if event is None:
            break
        yield event

    # ── 完了イベント ─────────────────────────────────────────────────────────────

    state = final_state_holder.get("result", {})
    sources = [
        {
            "doc_id": r["doc_id"],
            "content": r["content"],
            "score": r["score"],
            "metadata": r.get("metadata"),
        }
        for r in state.get("search_results", [])
    ]
    yield (
        "event: done\n"
        f"data: {json.dumps({'query': query, 'answer': state.get('answer', ''), 'sources': sources, 'retry_count': state.get('retry_count', 0), 'qdrant_latency_ms': state.get('qdrant_latency_ms'), 'pgvector_latency_ms': state.get('pgvector_latency_ms')}, ensure_ascii=False)}\n\n"
    )
