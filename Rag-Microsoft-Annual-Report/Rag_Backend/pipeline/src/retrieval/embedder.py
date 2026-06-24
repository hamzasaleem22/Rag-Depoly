from langchain_huggingface import HuggingFaceEmbeddings
from src.config import config
import logging

logger = logging.getLogger(__name__)

_embeddings: HuggingFaceEmbeddings | None = None


def get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        cfg = config.embeddings
        _embeddings = HuggingFaceEmbeddings(
            model_name=cfg.model,
            model_kwargs={"device": cfg.device},
            encode_kwargs={"normalize_embeddings": cfg.normalize_embeddings},
        )
        logger.info("Embedding model loaded: %s", cfg.model)
    return _embeddings


def clear_embeddings() -> None:
    global _embeddings
    _embeddings = None
