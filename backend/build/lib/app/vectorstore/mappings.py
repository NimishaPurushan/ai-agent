"""OpenSearch index mapping for k-NN vector search."""
from typing import Any, Dict


def build_index_body(embedding_dim: int) -> Dict[str, Any]:
    return {
        "settings": {
            "index": {
                "knn": True,
                "knn.algo_param.ef_search": 100,
            }
        },
        "mappings": {
            "properties": {
                "text": {"type": "text"},
                "source": {"type": "keyword"},
                "metadata": {"type": "object", "enabled": True},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": embedding_dim,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "lucene",
                        "parameters": {"ef_construction": 128, "m": 24},
                    },
                },
            }
        },
    }

