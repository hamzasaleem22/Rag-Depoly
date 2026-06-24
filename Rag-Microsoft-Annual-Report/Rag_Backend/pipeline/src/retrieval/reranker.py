from sentence_transformers import CrossEncoder
from langchain_core.documents import Document
from src.config import config
import logging

logger = logging.getLogger(__name__)

_reranker: CrossEncoder | None = None


def get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(config.reranker.model)
        logger.info("Reranker model loaded: %s", config.reranker.model)
    return _reranker


def rerank(query: str, docs: list[Document], top_k: int | None = None) -> list[Document]:
    if not docs:
        return []
    model = get_reranker()
    k = top_k or config.reranker.top_k
    pairs = [[query, doc.page_content] for doc in docs]
    scores = model.predict(pairs)
    scored = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
    reranked = [doc for doc, _ in scored[:k]]
    logger.debug("Reranked %d docs -> top %d", len(docs), len(reranked))
    return reranked


def clear_reranker() -> None:
    global _reranker
    _reranker = None
