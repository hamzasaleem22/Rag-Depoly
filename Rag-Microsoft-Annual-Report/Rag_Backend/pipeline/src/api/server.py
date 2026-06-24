import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config import config
from src.pipeline import ingest, is_indexed
from src.api.routes import router
from src.generation.llm import get_llm, clear_llm
from src.retrieval.reranker import get_reranker, clear_reranker
from src.retrieval.embedder import get_embeddings, clear_embeddings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if is_indexed():
        logger.info("Existing FAISS index found")
    else:
        logger.info("No index found, running ingestion...")
        ingest()
    try:
        get_llm()
    except ValueError as e:
        logger.warning("Skipped eager LLM initialization: %s", e)
    get_embeddings()
    get_reranker()
    logger.info("Server ready")
    yield
    clear_llm()
    clear_reranker()
    clear_embeddings()
    logger.info("Server shut down, models cleared")


def create_app() -> FastAPI:
    app = FastAPI(title="RAG Pipeline — Microsoft 2025 Annual Report", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.server.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    return app


app = create_app()
