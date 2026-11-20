"""RAG module for crop guidance and government schemes."""
from rag.ingest import seed_rag_collections
from rag.retriever import RAGRetriever

__all__ = ["seed_rag_collections", "RAGRetriever"]

