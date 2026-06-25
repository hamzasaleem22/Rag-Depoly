from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from src.config import config
from src.retrieval.embedder import get_embeddings
import logging

logger = logging.getLogger(__name__)


def build_retriever(vectorstore: FAISS):
    cfg = config.retriever
    retriever = vectorstore.as_retriever(
        search_type=cfg.type,
        search_kwargs={
            "k": cfg.k,
            "fetch_k": cfg.fetch_k,
            "lambda_mult": cfg.lambda_mult,
        },
    )
    logger.info("Retriever configured: type=%s k=%d fetch_k=%d", cfg.type, cfg.k, cfg.fetch_k)
    return retriever


def retrieve(vectorstore: FAISS, query: str, k: int | None = None) -> list[Document]:
    cfg = config.retriever
    retriever = vectorstore.as_retriever(
        search_type=cfg.type,
        search_kwargs={
            "k": k or cfg.k,
            "fetch_k": cfg.fetch_k,
            "lambda_mult": cfg.lambda_mult,
        },
    )
    docs = retriever.invoke(query)
    logger.debug("Retrieved %d docs for query", len(docs))
    return docs
