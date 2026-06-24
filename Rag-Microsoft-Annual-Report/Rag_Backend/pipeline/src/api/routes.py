import logging
from fastapi import APIRouter, HTTPException
from src.cache import cache
from src.pipeline import ingest, query, is_indexed
from src.api.models import QueryRequest, QueryResponse, HealthResponse, IngestResponse, SourceItem

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    from src.ingestion.vectorstore import load_index
    from src.config import BASE_DIR
    import os

    index_path = str(BASE_DIR / "faiss_index")
    if os.path.exists(index_path):
        vs = load_index(index_path)
        chunk_count = vs.index.ntotal
    else:
        chunk_count = 0

    return HealthResponse(
        status="ok",
        chunks=chunk_count,
        tables=0,
        cache_size=cache.size,
    )


@router.post("/ingest", response_model=IngestResponse)
async def ingest_endpoint():
    try:
        result = ingest()
        return IngestResponse(message="Ingested successfully", **result)
    except Exception as e:
        logger.exception("Ingestion failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=QueryResponse)
@router.post("/chat", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    if not is_indexed():
        raise HTTPException(status_code=400, detail="No index found. Run ingestion first.")
    try:
        result = query(request.question, request.api_key)
        return QueryResponse(
            answer=result["answer"],
            sources=[SourceItem(**s) for s in result["sources"]],
        )
    except Exception as e:
        logger.exception("Query failed")
        raise HTTPException(status_code=500, detail=str(e))
