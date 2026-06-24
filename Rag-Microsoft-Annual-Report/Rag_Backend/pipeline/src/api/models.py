from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str
    api_key: str | None = None


class SourceItem(BaseModel):
    page: int | str | None = None
    type: str | None = None
    content: str | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    provider: str | None = None   # e.g. "google", "anthropic", "openai"


class HealthResponse(BaseModel):
    status: str
    chunks: int
    tables: int
    cache_size: int


class IngestResponse(BaseModel):
    message: str
    chunks: int
    tables: int
