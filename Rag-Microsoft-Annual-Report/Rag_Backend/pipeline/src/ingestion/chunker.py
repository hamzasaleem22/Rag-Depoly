from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from src.config import config
import logging

logger = logging.getLogger(__name__)


def chunk_documents(docs: list[Document], chunk_size: int | None = None, chunk_overlap: int | None = None) -> list[Document]:
    cfg = config.chunking
    size = chunk_size if chunk_size is not None else cfg.chunk_size
    overlap = chunk_overlap if chunk_overlap is not None else cfg.chunk_overlap
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        separators=cfg.separators,
        length_function=len,
    )
    chunks = splitter.split_documents(docs)
    logger.info("Split %d docs into %d chunks", len(docs), len(chunks))
    return chunks
