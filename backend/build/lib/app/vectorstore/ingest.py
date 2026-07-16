"""Create the OpenSearch index and ingest sample documents with OpenAI embeddings.

Run:  python -m app.vectorstore.ingest
"""
from __future__ import annotations

from typing import List

from app.agent.llm import get_embeddings
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.vectorstore.client import ensure_index, index_documents

log = get_logger(__name__)

SAMPLE_DOCS: List[dict] = [
    {
        "text": "The chatbot uses LangGraph to orchestrate retrieval, planning, and tool execution.",
        "source": "internal/architecture.md",
        "metadata": {"topic": "architecture"},
    },
    {
        "text": "Before any MCP tool runs, the agent must request explicit user confirmation.",
        "source": "internal/safety.md",
        "metadata": {"topic": "safety"},
    },
    {
        "text": "OpenSearch stores document embeddings as knn_vector fields using the HNSW algorithm.",
        "source": "internal/vectorstore.md",
        "metadata": {"topic": "vectorstore"},
    },
    {
        "text": "OpenAI's text-embedding-3-small model produces 1536-dimensional embeddings.",
        "source": "internal/embeddings.md",
        "metadata": {"topic": "embeddings"},
    },
]


def main() -> None:
    configure_logging()
    settings = get_settings()
    log.info("Ensuring OpenSearch index '%s'...", settings.opensearch_index)
    ensure_index()

    log.info("Embedding %d sample documents...", len(SAMPLE_DOCS))
    embedder = get_embeddings()
    texts = [d["text"] for d in SAMPLE_DOCS]
    vectors = embedder.embed_documents(texts)

    docs = [{**d, "embedding": v} for d, v in zip(SAMPLE_DOCS, vectors)]
    n = index_documents(docs)
    log.info("Indexed %d documents into '%s'", n, settings.opensearch_index)


if __name__ == "__main__":
    main()

