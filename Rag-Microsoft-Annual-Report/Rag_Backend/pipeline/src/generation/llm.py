from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.config import config
import logging
import os

logger = logging.getLogger(__name__)

_llm = None


def _build_llm(api_key: str | None = None):
    cfg = config.llm
    provider = cfg.provider.lower()

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        key = api_key or os.getenv("GOOGLE_GEMINI_API_KEY", "")
        if not key:
            raise ValueError("GOOGLE_GEMINI_API_KEY not set")
        return ChatGoogleGenerativeAI(
            model=cfg.model,
            temperature=cfg.temperature,
            top_p=cfg.top_p,
            max_output_tokens=cfg.max_output_tokens,
            google_api_key=key,
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        key = api_key or os.getenv("OPENAI_API_KEY", "")
        if not key:
            raise ValueError("OPENAI_API_KEY not set")
        kwargs = dict(
            model=cfg.model,
            temperature=cfg.temperature,
            top_p=cfg.top_p,
            max_tokens=cfg.max_output_tokens,
            api_key=key,
        )
        if cfg.openai_base_url:
            kwargs["base_url"] = cfg.openai_base_url
        return ChatOpenAI(**kwargs)

    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


def _retryable_exceptions():
    cfg = config.llm
    provider = cfg.provider.lower()
    if provider == "google":
        import google.api_core.exceptions
        return (
            google.api_core.exceptions.ServiceUnavailable,
            google.api_core.exceptions.DeadlineExceeded,
            google.api_core.exceptions.ResourceExhausted,
            google.api_core.exceptions.InternalServerError,
        )
    elif provider == "openai":
        import openai
        return (
            openai.APIError,
            openai.APITimeoutError,
            openai.RateLimitError,
            openai.InternalServerError,
        )
    return ()


def get_llm():
    global _llm
    if _llm is None:
        _llm = _build_llm()
        logger.info("LLM initialized: %s (%s)", config.llm.model, config.llm.provider)
    return _llm


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(_retryable_exceptions()),
    before_sleep=lambda retry_state: logger.warning(
        "LLM call failed (attempt %d/3), retrying...", retry_state.attempt_number
    ),
)
def llm_invoke(messages, api_key: str | None = None) -> str:
    if api_key:
        llm = _build_llm(api_key)
    else:
        llm = get_llm()
    response = llm.invoke(messages)
    if isinstance(response.content, str):
        return response.content
    return " ".join(
        p.get("text", str(p)) if isinstance(p, dict) else str(p)
        for p in response.content
    )


def clear_llm() -> None:
    global _llm
    _llm = None
