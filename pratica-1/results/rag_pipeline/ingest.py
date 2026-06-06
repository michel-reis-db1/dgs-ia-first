"""
Ingestion pipeline: load → chunk → embed → store.

Chunking strategy: SECTION-BASED (split on ## and ### headers).

Why section-based instead of fixed-token:
- NovaTech queries map directly to sections ("carga perigosa" → POL-001 §3.2)
- The PROC-042 regional multiplier table cannot be split mid-row without losing meaning
- One section = one topic → maximizes retrieval precision
- Avoids the "lost in the middle" problem where critical exceptions get buried
"""

import os
import re
from sentence_transformers import SentenceTransformer
import chromadb
from config import (
    CHROMA_PATH, COLLECTION_NAME, MODEL_NAME, CHUNK_OVERLAP_SENTENCES
)

# Maps filename stem → fixed metadata that cannot be inferred from file content
DOCUMENT_REGISTRY = {
    "POL-001-politica-devolucao": {
        "document_id": "POL-001",
        "source_type": "policy",
        "is_superseded": False,
    },
    "PROC-042-frete-especial-v1": {
        "document_id": "PROC-042",
        "source_type": "procedure",
        "is_superseded": True,
    },
    "PROC-042-v2-frete-especial-revisado": {
        "document_id": "PROC-042-v2",
        "source_type": "procedure",
        "is_superseded": False,
    },
    "SLA-2024-tabela-sla-clientes": {
        "document_id": "SLA-2024",
        "source_type": "sla",
        "is_superseded": False,
    },
    "FAQ-atendimento": {
        "document_id": "FAQ",
        "source_type": "faq",
        "is_superseded": False,
    },
}


def _extract_header_metadata(text: str) -> dict:
    """Pull Versão and Última atualização from the document preamble."""
    version_match = re.search(r"\*\*Versão:\*\*\s*(.+)", text)
    date_match = re.search(r"\*\*(?:Última atualização|Data de emissão):\*\*\s*(.+)", text)

    version = version_match.group(1).strip() if version_match else "unknown"
    last_updated = date_match.group(1).strip() if date_match else "unknown"

    # Normalise date formats like "15/01/2024" → "2024-01-15"
    date_norm = re.match(r"(\d{2})/(\d{2})/(\d{4})", last_updated)
    if date_norm:
        last_updated = f"{date_norm.group(3)}-{date_norm.group(2)}-{date_norm.group(1)}"

    # FAQ has "Não controlada" as version → normalise
    if "controlada" in version.lower() or "informal" in version.lower():
        version = "informal"

    return {"version": version, "last_updated": last_updated}


def load_documents(docs_dir: str) -> list[dict]:
    """
    Read each .md file in docs_dir, extract header metadata, return doc dicts.
    Only files listed in DOCUMENT_REGISTRY are processed.
    """
    docs = []
    for filename in os.listdir(docs_dir):
        if not filename.endswith(".md"):
            continue
        stem = filename[:-3]  # strip .md
        if stem not in DOCUMENT_REGISTRY:
            continue

        path = os.path.join(docs_dir, filename)
        with open(path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        registry_meta = DOCUMENT_REGISTRY[stem]
        header_meta = _extract_header_metadata(raw_text)

        doc = {
            **registry_meta,
            "version": header_meta["version"],
            "last_updated": header_meta["last_updated"],
            "raw_text": raw_text,
        }

        # FAQ has no formal version — override with "informal"
        if registry_meta["document_id"] == "FAQ":
            doc["version"] = "informal"

        docs.append(doc)

    return docs


def _section_number_from_title(title: str) -> str:
    """
    Extract section number from a header line, e.g.:
      "## 3. Regras de Devolução"  → "3"
      "### 3.2. Exceções ao prazo" → "3.2"
      "### Item 3 — …"            → "item-3"
    """
    # Numbered section: "3.", "3.2.", "2.1."
    num_match = re.match(r"^#+\s+(\d+(?:\.\d+)*)\.", title)
    if num_match:
        return num_match.group(1)

    # FAQ items: "### Item 3 —"
    item_match = re.match(r"^#+\s+Item\s+(\d+)", title, re.IGNORECASE)
    if item_match:
        return f"item-{item_match.group(1)}"

    # Fallback: slugify the words
    words = re.sub(r"^#+\s*", "", title).split()
    slug = "-".join(w.lower() for w in words[:3])
    return slug or "unknown"


def _section_title_from_header(header_line: str) -> str:
    """Strip markdown hashes and leading section numbers from a header line."""
    text = re.sub(r"^#+\s*", "", header_line)
    # Remove leading "3.2. " or "Item 3 — "
    text = re.sub(r"^\d+(?:\.\d+)*\.\s*", "", text)
    text = re.sub(r"^Item\s+\d+\s*[—\-]\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def _last_sentence(text: str) -> str:
    """Return the last non-empty sentence of text (for cross-section overlap)."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    return sentences[-1] if sentences else ""


def split_into_chunks(doc: dict) -> list[dict]:
    """
    Split document text on ## / ### headers.
    Applies 1-sentence overlap: last sentence of section N is prepended to section N+1.

    chunk_id format: "{document_id}-{section}-{chunk_index}"
    e.g. "POL-001-3.2-0", "PROC-042-v2-2.1-0"
    """
    raw = doc["raw_text"]

    # Split on lines that start with ## or ### (keeping the delimiter)
    parts = re.split(r"(?m)^(#{2,3}\s.+)$", raw)
    # parts alternates: [preamble, header1, body1, header2, body2, ...]

    sections = []
    # parts[0] is always the preamble (text before the first ## header, possibly empty).
    # The split captures delimiters, so the pattern is:
    #   [preamble, header1, body1, header2, body2, ...]
    # We always start at index 1 (first ## header), regardless of preamble content.
    i = 1

    while i < len(parts) - 1:
        header = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if header.startswith("##"):
            sections.append({"header": header, "body": body})
        i += 2

    chunks = []
    prev_last_sentence = ""

    for chunk_index, section in enumerate(sections):
        section_num = _section_number_from_title(section["header"])
        section_title = _section_title_from_header(section["header"])

        # Overlap: prepend last sentence of previous section
        body_text = section["body"]
        if prev_last_sentence and CHUNK_OVERLAP_SENTENCES > 0:
            body_text = prev_last_sentence + "\n\n" + body_text

        prev_last_sentence = _last_sentence(section["body"])

        chunk_id = f"{doc['document_id']}-{section_num}-{chunk_index}"

        chunk = {
            "chunk_id": chunk_id,
            "text": f"{section['header']}\n\n{body_text}",
            "document_id": doc["document_id"],
            "version": doc["version"],
            "section": section_num,
            "section_title": section_title,
            "source_type": doc["source_type"],
            "last_updated": doc["last_updated"],
            # ChromaDB stores metadata as JSON; bool must stay bool (not str)
            "is_superseded": doc["is_superseded"],
            "chunk_index": chunk_index,
        }
        chunks.append(chunk)

    return chunks


def embed_and_store(chunks: list[dict], collection) -> None:
    """Generate embeddings and upsert into ChromaDB with full metadata."""
    model = SentenceTransformer(MODEL_NAME)

    texts = [c["text"] for c in chunks]
    ids = [c["chunk_id"] for c in chunks]
    metadatas = [
        {
            "document_id": c["document_id"],
            "version": c["version"],
            "section": c["section"],
            "section_title": c["section_title"],
            "source_type": c["source_type"],
            "last_updated": c["last_updated"],
            # ChromaDB requires metadata values to be str/int/float/bool
            "is_superseded": c["is_superseded"],
            "chunk_index": c["chunk_index"],
        }
        for c in chunks
    ]

    print(f"  Embedding {len(texts)} chunks with {MODEL_NAME}...")
    embeddings = model.encode(texts, show_progress_bar=True).tolist()

    collection.upsert(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def main():
    docs_dir = os.path.join(os.path.dirname(__file__), "documents")

    print("=== NovaTech RAG Ingestion Pipeline ===\n")

    print("1. Loading documents...")
    docs = load_documents(docs_dir)
    print(f"   Loaded {len(docs)} documents: {[d['document_id'] for d in docs]}\n")

    print("2. Chunking documents...")
    all_chunks = []
    for doc in docs:
        chunks = split_into_chunks(doc)
        superseded_flag = " [SUPERSEDED]" if doc["is_superseded"] else ""
        print(f"   {doc['document_id']}{superseded_flag}: {len(chunks)} chunks")
        all_chunks.extend(chunks)
    print(f"   Total: {len(all_chunks)} chunks\n")

    print("3. Setting up ChromaDB...")
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    # Delete existing collection so re-runs start clean
    try:
        client.delete_collection(COLLECTION_NAME)
        print("   Deleted existing collection.")
    except Exception:
        pass
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    print("4. Embedding and storing chunks...")
    embed_and_store(all_chunks, collection)

    print(f"\n✓ Done: {len(docs)} documents → {len(all_chunks)} chunks stored in '{CHROMA_PATH}'")

    # Sanity check: verify superseded chunks are marked
    superseded = [c for c in all_chunks if c["is_superseded"]]
    print(f"  Superseded chunks: {len(superseded)} (all from PROC-042 v1 — will be filtered at retrieval)")


if __name__ == "__main__":
    main()
