import os
import httpx
from typing import List

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
EMBED_MODEL = "llama3.2"


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """Batch embed texts via Ollama. Returns list of embedding vectors."""
    embeddings = []
    for text in texts:
        response = httpx.post(
            f"{OLLAMA_BASE_URL}/api/embed",
            json={"model": EMBED_MODEL, "input": text},
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        embeddings.append(data["embeddings"][0])
    return embeddings


def get_embedding(text: str) -> List[float]:
    return get_embeddings([text])[0]
