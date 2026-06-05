"""OpenSearch client + k-NN helpers."""
from functools import lru_cache
from typing import Any, Dict, List, Optional

from opensearchpy import OpenSearch, RequestsHttpConnection

from app.core.config import get_settings
from app.core.logging import get_logger
from app.vectorstore.mappings import build_index_body

log = get_logger(__name__)


@lru_cache
def get_client() -> OpenSearch:
    s = get_settings()
    http_auth = (s.opensearch_user, s.opensearch_password) if s.opensearch_user else None
    client = OpenSearch(
        hosts=[s.opensearch_url],
        http_auth=http_auth,
        use_ssl=s.opensearch_use_ssl,
        verify_certs=s.opensearch_verify_certs,
        ssl_show_warn=False,
        connection_class=RequestsHttpConnection,
        timeout=30,
    )
    return client


def ensure_index() -> None:
    s = get_settings()
    client = get_client()
    if client.indices.exists(index=s.opensearch_index):
        log.info("Index '%s' already exists", s.opensearch_index)
        return
    body = build_index_body(s.openai_embedding_dim)
    client.indices.create(index=s.opensearch_index, body=body)
    log.info("Created index '%s' (dim=%d)", s.opensearch_index, s.openai_embedding_dim)


def index_documents(docs: List[Dict[str, Any]]) -> int:
    """Bulk-index documents. Each doc must have 'text' and 'embedding'."""
    s = get_settings()
    client = get_client()
    bulk_body: List[Dict[str, Any]] = []
    for d in docs:
        bulk_body.append({"index": {"_index": s.opensearch_index}})
        bulk_body.append(d)
    if not bulk_body:
        return 0
    resp = client.bulk(body=bulk_body, refresh=True)
    errors = [it for it in resp.get("items", []) if it.get("index", {}).get("error")]
    if errors:
        log.error("Bulk indexing errors: %s", errors[:3])
    return len(docs) - len(errors)


def knn_search(embedding: List[float], k: int = 4) -> List[Dict[str, Any]]:
    s = get_settings()
    client = get_client()
    body = {
        "size": k,
        "query": {"knn": {"embedding": {"vector": embedding, "k": k}}},
        "_source": {"excludes": ["embedding"]},
    }
    resp = client.search(index=s.opensearch_index, body=body)
    return [
        {"score": h["_score"], **h["_source"]} for h in resp["hits"]["hits"]
    ]


def health() -> Optional[Dict[str, Any]]:
    try:
        return get_client().cluster.health()
    except Exception as e:  # pragma: no cover
        log.warning("OpenSearch health check failed: %s", e)
        return None

