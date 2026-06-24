import os
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from src.config import config
import logging

logger = logging.getLogger(__name__)


def build_embeddings() -> HuggingFaceEmbeddings:
    cfg = config.embeddings
    return HuggingFaceEmbeddings(
        model_name=cfg.model,
        model_kwargs={"device": cfg.device},
        encode_kwargs={"normalize_embeddings": cfg.normalize_embeddings},
    )


def build_index(chunks: list[Document], index_path: str) -> FAISS:
    embeddings = build_embeddings()
    vectorstore = FAISS.from_documents(chunks, embeddings)
    os.makedirs(os.path.dirname(index_path) or ".", exist_ok=True)
    vectorstore.save_local(index_path)
    logger.info("FAISS index saved to %s with %d vectors", index_path, vectorstore.index.ntotal)
    return vectorstore


def load_index(index_path: str) -> FAISS:
    if not os.path.exists(index_path):
        raise FileNotFoundError(f"FAISS index not found at {index_path}")
    from src.retrieval.embedder import get_embeddings
    embeddings = get_embeddings()
    vectorstore = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
    logger.info("FAISS index loaded from %s with %d vectors", index_path, vectorstore.index.ntotal)
    return vectorstore
