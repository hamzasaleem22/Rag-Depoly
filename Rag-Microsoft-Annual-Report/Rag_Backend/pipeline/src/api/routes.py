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
            provider=result.get("provider"),
        )
    except Exception as e:
        err_str = str(e)
        logger.exception("Query failed")

        # --- Quota / Rate-limit errors (429) ---
        if any(kw in err_str for kw in ["RESOURCE_EXHAUSTED", "rate_limit_error", "rate limit", "429", "quota"]):
            raise HTTPException(
                status_code=429,
                detail=(
                    "API quota or rate limit exceeded for this key. "
                    "Please wait a moment or use a different API key."
                ),
            )

        # --- Authentication / Invalid key errors (401) ---
        if any(kw in err_str.lower() for kw in [
            "invalid_api_key", "api_key_invalid", "authentication_error",
            "invalid x-api-key", "incorrect api key", "401", "forbidden",
            "invalid_argument",
        ]):
            raise HTTPException(
                status_code=401,
                detail=(
                    "Invalid API key. Please check your key and try again. "
                    "Click the 🔑 key icon in the top-right to enter your key. "
                    "Supported: Google Gemini (AIza...), Anthropic Claude (sk-ant-...), OpenAI (sk-...)."
                ),
            )

        # --- Model not found (wrong model name in config) ---
        if any(kw in err_str for kw in ["NOT_FOUND", "404", "not found for API version", "model_not_found"]):
            raise HTTPException(
                status_code=500,
                detail=(
                    "The configured AI model was not found. "
                    "The server admin should check the model name in config.yaml."
                ),
            )

        # --- No server key configured ---
        if "no google gemini api key" in err_str.lower() or "not set" in err_str.lower():
            raise HTTPException(
                status_code=401,
                detail=(
                    "No API key is configured on the server. "
                    "Click the 🔑 key icon in the top-right corner to enter your own API key."
                ),
            )

        # --- Provider detection failure ---
        if "cannot determine llm provider" in err_str.lower():
            raise HTTPException(
                status_code=400,
                detail=(
                    "Could not detect the API provider from your key. "
                    "Supported key formats: Google Gemini (AIza...), "
                    "Anthropic Claude (sk-ant-...), OpenAI (sk-...)."
                ),
            )

        # --- Generic 500 ---
        raise HTTPException(status_code=500, detail=err_str)
