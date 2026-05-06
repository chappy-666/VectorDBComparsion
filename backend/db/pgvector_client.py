import os
import psycopg2
from psycopg2.extras import execute_values
from pgvector.psycopg2 import register_vector
from typing import List

PG_HOST = os.getenv("PGVECTOR_HOST", "pgvector")
PG_PORT = int(os.getenv("PGVECTOR_PORT", "5432"))
PG_USER = os.getenv("PGVECTOR_USER", "postgres")
PG_PASSWORD = os.getenv("PGVECTOR_PASSWORD", "postgres")
PG_DB = os.getenv("PGVECTOR_DB", "vectordb")
VECTOR_DIM = 3072  # llama3.2 embedding dimension


def get_connection():
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        dbname=PG_DB,
    )
    return conn


def ensure_table(conn) -> None:
    # Create extension first, commit, then register vector type
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    conn.commit()
    register_vector(conn)

    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                doc_id TEXT UNIQUE NOT NULL,
                content TEXT NOT NULL,
                metadata JSONB,
                embedding vector({VECTOR_DIM})
            );
        """)
        # ivfflat/hnsw both cap at 2000 dims; exact scan is fine at demo scale
    conn.commit()


def upsert_documents(
    conn,
    doc_ids: List[str],
    contents: List[str],
    metadatas: List[dict],
    embeddings: List[List[float]],
) -> None:
    import json
    import numpy as np

    rows = [
        (doc_ids[i], contents[i], json.dumps(metadatas[i]), np.array(embeddings[i]))
        for i in range(len(doc_ids))
    ]
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO documents (doc_id, content, metadata, embedding)
            VALUES %s
            ON CONFLICT (doc_id) DO UPDATE
              SET content = EXCLUDED.content,
                  metadata = EXCLUDED.metadata,
                  embedding = EXCLUDED.embedding;
            """,
            rows,
        )
    conn.commit()


def search(
    conn,
    query_vector: List[float],
    top_k: int = 5,
) -> List[dict]:
    import numpy as np

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT doc_id, content, metadata,
                   1 - (embedding <=> %s::vector) AS score
            FROM documents
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
            """,
            (np.array(query_vector), np.array(query_vector), top_k),
        )
        rows = cur.fetchall()

    return [
        {"doc_id": r[0], "content": r[1], "metadata": r[2], "score": float(r[3])}
        for r in rows
    ]
