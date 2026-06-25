import os
import logging
from pathlib import Path
from langchain_community.vectorstores import FAISS

from src.config import config, BASE_DIR
from src.ingestion.loader import load_all
from src.ingestion.chunker import chunk_documents
from src.ingestion.vectorstore import build_index, load_index
from src.generation.prompt import get_prompt, format_context
from src.generation.llm import llm_invoke
from src.retrieval.retriever import retrieve
from src.retrieval.reranker import rerank
from src.cache import cache

logger = logging.getLogger(__name__)

_vectorstore: FAISS | None = None


def _get_pdf_path() -> str:
    return str(BASE_DIR / config.pdf.path)


def _get_index_path() -> str:
    return str(BASE_DIR / "faiss_index")


def is_indexed() -> bool:
    return os.path.exists(_get_index_path())


def ingest() -> dict:
    pdf_path = _get_pdf_path()
    docs = load_all(pdf_path)
    chunks = chunk_documents(docs)
    vs = build_index(chunks, _get_index_path())
    globals()["_vectorstore"] = vs
    logger.info("Ingestion complete: %d chunks, %d vectors", len(chunks), vs.index.ntotal)
    return {"chunks": len(chunks), "tables": sum(1 for d in docs if d.metadata.get("type") == "table")}


def get_vectorstore() -> FAISS:
    global _vectorstore
    if _vectorstore is None:
        if is_indexed():
            _vectorstore = load_index(_get_index_path())
        else:
            raise RuntimeError("No FAISS index found. Run ingestion first.")
    return _vectorstore


def query(question: str, api_key: str | None = None) -> dict:
    cache_key = f"{question}::{api_key or ''}"
    cached = cache.get(cache_key)
    if cached is not None:
        logger.info("Cache hit for query")
        return cached

    vs = get_vectorstore()
    retrieved = retrieve(vs, question)
    top_docs = rerank(question, retrieved)
    context = format_context(top_docs)
    prompt = get_prompt()
    messages = prompt.format_messages(context=context, question=question)
    answer, provider = llm_invoke(messages, api_key)

    sources = [
        {
            "page": d.metadata.get("page"),
            "type": d.metadata.get("type"),
            "content": d.page_content[:200],
        }
        for d in top_docs
    ]
    result = {"answer": answer, "sources": sources, "provider": provider}
    cache.set(cache_key, result)
    return result

