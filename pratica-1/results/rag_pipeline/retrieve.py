"""
Retrieval layer: semantic search over the ChromaDB collection.
"""

from sentence_transformers import SentenceTransformer
import chromadb
from config import CHROMA_PATH, COLLECTION_NAME, MODEL_NAME, TOP_K


def search(
    query: str,
    collection,
    model: SentenceTransformer,
    top_k: int = TOP_K,
    exclude_superseded: bool = True,
    min_score: float = 0.3,
    source_type_filter: list[str] | None = None,
) -> list[dict]:
    """
    Return top_k chunks most similar to query.

    exclude_superseded=True adds a ChromaDB where-filter for is_superseded=False.
    This is the primary safeguard against PROC-042 v1 contaminating results —
    the filter runs inside ChromaDB before candidates reach Python, so v1 chunks
    are never scored or returned regardless of their embedding similarity.

    ChromaDB returns L2 or cosine distances (lower = more similar when using
    cosine space). We created the collection with hnsw:space=cosine, so:
        similarity = 1 - distance
    We then drop results below min_score.
    """
    query_embedding = model.encode([query])[0].tolist()

    where_filter: dict | None = None

    if exclude_superseded and source_type_filter:
        where_filter = {
            "$and": [
                {"is_superseded": {"$eq": False}},
                {"source_type": {"$in": source_type_filter}},
            ]
        }
    elif exclude_superseded:
        # ChromaDB requires bool False, not the string "False"
        where_filter = {"is_superseded": {"$eq": False}}
    elif source_type_filter:
        where_filter = {"source_type": {"$in": source_type_filter}}

    query_kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where_filter:
        query_kwargs["where"] = where_filter

    raw = collection.query(**query_kwargs)

    results = []
    for i, (doc, meta, dist) in enumerate(
        zip(raw["documents"][0], raw["metadatas"][0], raw["distances"][0])
    ):
        similarity = 1.0 - dist
        if similarity < min_score:
            continue

        results.append({
            "chunk_id": meta.get("document_id", "?") + "-" + meta.get("section", "?") + f"-{meta.get('chunk_index', i)}",
            "text": doc,
            "document_id": meta.get("document_id"),
            "version": meta.get("version"),
            "section": meta.get("section"),
            "section_title": meta.get("section_title"),
            "source_type": meta.get("source_type"),
            "is_superseded": meta.get("is_superseded"),
            "similarity_score": round(similarity, 4),
        })

    # Sort descending by similarity (ChromaDB already returns sorted, but be explicit)
    results.sort(key=lambda r: r["similarity_score"], reverse=True)
    return results


def format_results_table(results: list[dict]) -> str:
    """Human-readable table of retrieval results for test documentation."""
    if not results:
        return "  (no results above threshold)\n"

    lines = [
        f"  {'#':<3} {'chunk_id':<30} {'score':<8} {'doc':<12} {'section':<10} source_type",
        f"  {'-'*3} {'-'*30} {'-'*8} {'-'*12} {'-'*10} {'-'*12}",
    ]
    for i, r in enumerate(results, 1):
        superseded_flag = " ⚠ SUPERSEDED" if r.get("is_superseded") else ""
        lines.append(
            f"  {i:<3} {r['chunk_id']:<30} {r['similarity_score']:<8.4f} "
            f"{r['document_id']:<12} {r['section']:<10} {r['source_type']}{superseded_flag}"
        )
    return "\n".join(lines) + "\n"


def get_collection_and_model():
    """Convenience loader used by test_pipeline.py and interactive scripts."""
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(COLLECTION_NAME)
    model = SentenceTransformer(MODEL_NAME)
    return collection, model
