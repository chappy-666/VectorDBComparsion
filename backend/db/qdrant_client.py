import os
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Query
from typing import List

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = "documents"
VECTOR_DIM = 3072  # llama3.2 embedding dimension


def get_client() -> QdrantClient:
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def ensure_collection(client: QdrantClient) -> None:
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )


def upsert_documents(
    client: QdrantClient,
    ids: List[int],
    vectors: List[List[float]],
    payloads: List[dict],
) -> None:
    points = [
        PointStruct(id=ids[i], vector=vectors[i], payload=payloads[i])
        for i in range(len(ids))
    ]
    client.upsert(collection_name=COLLECTION_NAME, points=points)


def search(
    client: QdrantClient,
    query_vector: List[float],
    top_k: int = 5,
) -> List[dict]:
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
        with_payload=True,
    )
    return [
        {"id": r.id, "score": r.score, "payload": r.payload}
        for r in results.points
    ]
