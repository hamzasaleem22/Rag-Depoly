from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field
import yaml
import os
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class PDFConfig(BaseModel):
    path: str


class EmbeddingsConfig(BaseModel):
    model: str = "sentence-transformers/all-MiniLM-L6-v2"
    device: str = "cpu"
    normalize_embeddings: bool = True


class ChunkingConfig(BaseModel):
    chunk_size: int = 1500
    chunk_overlap: int = 250
    separators: List[str] = ["\n\n", "\n", ".", " "]


class RetrieverConfig(BaseModel):
    type: str = "mmr"
    k: int = 10
    fetch_k: int = 20
    lambda_mult: float = 0.5


class RerankerConfig(BaseModel):
    model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    top_k: int = 5


class LLMConfig(BaseModel):
    provider: str = "google"
    model: str = "gemini-1.5-flash"
    temperature: float = 0.2
    top_p: float = 0.9
    max_output_tokens: int = 4096
    retry_attempts: int = 3
    retry_min_wait: int = 2
    openai_base_url: Optional[str] = None


class CacheConfig(BaseModel):
    enabled: bool = True
    backend: str = "memory"
    max_size: int = 100
    ttl_seconds: int = 3600


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = ["*"]
    log_level: str = "info"


class PromptConfig(BaseModel):
    system: str
    human: str


class AppConfig(BaseModel):
    pdf: PDFConfig
    embeddings: EmbeddingsConfig = EmbeddingsConfig()
    chunking: ChunkingConfig = ChunkingConfig()
    retriever: RetrieverConfig = RetrieverConfig()
    reranker: RerankerConfig = RerankerConfig()
    llm: LLMConfig = LLMConfig()
    cache: CacheConfig = CacheConfig()
    server: ServerConfig = ServerConfig()
    prompt: PromptConfig



def load_config(path: Optional[str] = None) -> AppConfig:
    if path is None:
        path = str(BASE_DIR / "config.yaml")
    with open(path) as f:
        raw = yaml.safe_load(f)
    return AppConfig.model_validate(raw)


config: AppConfig = load_config()
