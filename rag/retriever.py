"""
RAG Retriever for Crop Guidance and Government Schemes
Performs semantic top-k retrieval, confidence scoring, and citation generation.
"""

from typing import List, Dict, Any, Optional
try:
    import chromadb
except ImportError:
    chromadb = None
from rag.ingest import get_chroma_client, seed_rag_collections


class RAGRetriever:
    """
    Retrieves relevant knowledge from ChromaDB collections with metadata citations.
    """

    def __init__(self, chroma_client: Optional[Any] = None):
        if chroma_client is None:
            self.client = get_chroma_client()
            seed_rag_collections(self.client)
        else:
            self.client = chroma_client

    def retrieve_crop_guidance(self, crop: str, stage: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """
        Retrieves agronomic guidance for a specific crop and growth stage.
        """
        try:
            col = self.client.get_collection(name="crop_guidance")
        except Exception:
            seed_rag_collections(self.client)
            col = self.client.get_collection(name="crop_guidance")

        query_text = f"Agronomic management for {crop} at {stage} stage, irrigation and weather practices"
        # Where filter by crop if present
        where_filter = {"crop": crop.capitalize()} if crop else None

        results = col.query(
            query_texts=[query_text],
            n_results=top_k,
            where=where_filter,
        )

        items = []
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if "metadatas" in results else [{}] * len(docs)
            ids = results["ids"][0] if "ids" in results else [""] * len(docs)
            distances = results.get("distances", [[0.5] * len(docs)])[0]

            for doc, meta, doc_id, dist in zip(docs, metas, ids, distances):
                items.append({
                    "id": doc_id,
                    "text": doc,
                    "document_name": meta.get("document_name", "ICAR Guidance Manual"),
                    "source_url": meta.get("source_url", ""),
                    "crop": meta.get("crop", crop),
                    "stage": meta.get("stage", stage),
                    "score": round(max(0.0, 1.0 - (dist if dist is not None else 0.5)), 3),
                    "citation": f"[Source: {meta.get('document_name', 'ICAR')}, Chunk: {doc_id}]",
                })
        return items

    def retrieve_schemes(self, crop: str, stage: str, state: Optional[str] = None, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieves relevant central or state government schemes.
        """
        try:
            col = self.client.get_collection(name="schemes")
        except Exception:
            seed_rag_collections(self.client)
            col = self.client.get_collection(name="schemes")

        query_text = f"Financial, insurance or solar scheme for {crop} farmer at {stage} stage in {state or 'India'}"
        results = col.query(
            query_texts=[query_text],
            n_results=top_k,
        )

        items = []
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if "metadatas" in results else [{}] * len(docs)
            ids = results["ids"][0] if "ids" in results else [""] * len(docs)
            distances = results.get("distances", [[0.5] * len(docs)])[0]

            for doc, meta, doc_id, dist in zip(docs, metas, ids, distances):
                items.append({
                    "id": doc_id,
                    "text": doc,
                    "scheme_name": meta.get("scheme_name", "PM Scheme"),
                    "document_name": meta.get("document_name", "Official Scheme Document"),
                    "source_url": meta.get("source_url", ""),
                    "state": meta.get("state", "All India"),
                    "score": round(max(0.0, 1.0 - (dist if dist is not None else 0.5)), 3),
                    "citation": f"[Source: {meta.get('document_name')}, Chunk: {doc_id}]",
                })
        return items

