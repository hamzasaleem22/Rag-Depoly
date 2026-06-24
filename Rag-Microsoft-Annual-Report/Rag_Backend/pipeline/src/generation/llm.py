"""
Multi-provider LLM module.

Provider is auto-detected from the API key prefix:
  AIza...         → Google Gemini
  sk-ant-...      → Anthropic Claude
  sk-...          → OpenAI

If no key is provided the server's config.yaml provider + env key is used.
"""

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.config import config
import logging
import os

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Cache: keyed by (provider, api_key) to avoid rebuilding per request
# ------------------------------------------------------------------
_llm_cache: dict[str, object] = {}


def detect_provider(api_key: str) -> str:
    """
    Auto-detect the LLM provider from the API key prefix.
    Returns 'google', 'anthropic', or 'openai'.
    """
    if api_key.startswith("AIza"):
        return "google"
    if api_key.startswith("sk-ant-"):
        return "anthropic"
    if api_key.startswith("sk-"):
        return "openai"
    # Fallback: assume the server-configured provider
    return config.llm.provider.lower()


def _build_llm(api_key: str | None = None, provider: str | None = None):
    """
    Build a LangChain chat model for the given provider and key.
    If api_key is None the server env variables are used.
    If provider is None it is auto-detected from the key (or falls back
    to the server config).
    """
    cfg = config.llm

    # Determine provider
    if api_key:
        prov = provider or detect_provider(api_key)
    else:
        prov = cfg.provider.lower()

    if prov == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        key = api_key or os.getenv("GOOGLE_GEMINI_API_KEY", "")
        if not key:
            raise ValueError(
                "No Google Gemini API key found. "
                "Set GOOGLE_GEMINI_API_KEY in .env or provide a key starting with 'AIza'."
            )
        # Use a sensible default model for Gemini
        model = cfg.model if cfg.provider.lower() == "google" else "gemini-2.5-flash"
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=cfg.temperature,
            top_p=cfg.top_p,
            max_output_tokens=cfg.max_output_tokens,
            google_api_key=key,
        )

    elif prov == "anthropic":
        from langchain_anthropic import ChatAnthropic
        key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            raise ValueError(
                "No Anthropic API key found. "
                "Set ANTHROPIC_API_KEY in .env or provide a key starting with 'sk-ant-'."
            )
        # Default Claude model - sensible and widely available
        model = cfg.model if cfg.provider.lower() == "anthropic" else "claude-3-5-haiku-20241022"
        return ChatAnthropic(
            model=model,
            temperature=cfg.temperature,
            top_p=cfg.top_p,
            max_tokens=cfg.max_output_tokens,
            api_key=key,
        )

    elif prov == "openai":
        from langchain_openai import ChatOpenAI
        key = api_key or os.getenv("OPENAI_API_KEY", "")
        if not key:
            raise ValueError(
                "No OpenAI API key found. "
                "Set OPENAI_API_KEY in .env or provide a key starting with 'sk-'."
            )
        model = cfg.model if cfg.provider.lower() == "openai" else "gpt-4o-mini"
        kwargs = dict(
            model=model,
            temperature=cfg.temperature,
            top_p=cfg.top_p,
            max_tokens=cfg.max_output_tokens,
            api_key=key,
        )
        if cfg.openai_base_url:
            kwargs["base_url"] = cfg.openai_base_url
        return ChatOpenAI(**kwargs)

    else:
        raise ValueError(
            f"Cannot determine LLM provider. "
            f"Key prefix not recognised. Supported: Google (AIza...), "
            f"Anthropic (sk-ant-...), OpenAI (sk-...)."
        )


def _retryable_exceptions(prov: str):
    if prov == "google":
        try:
            import google.api_core.exceptions
            return (
                google.api_core.exceptions.ServiceUnavailable,
                google.api_core.exceptions.DeadlineExceeded,
                google.api_core.exceptions.InternalServerError,
            )
        except ImportError:
            return ()
    elif prov == "anthropic":
        try:
            import anthropic
            return (
                anthropic.APITimeoutError,
                anthropic.InternalServerError,
            )
        except ImportError:
            return ()
    elif prov == "openai":
        try:
            import openai
            return (
                openai.APIError,
                openai.APITimeoutError,
                openai.InternalServerError,
            )
        except ImportError:
            return ()
    return ()


def get_llm(api_key: str | None = None, provider: str | None = None):
    """
    Return a cached LLM client.
    Cache key = "<provider>:<api_key>" so different keys get different clients.
    Bad clients are NEVER cached — if _build_llm raises, the entry is not stored
    so the next request will attempt a fresh build.
    """
    if api_key:
        prov = provider or detect_provider(api_key)
    else:
        prov = config.llm.provider.lower()

    cache_key = f"{prov}:{api_key or '__default__'}"
    if cache_key not in _llm_cache:
        # Build outside the cache dict so a failure leaves the cache clean
        client = _build_llm(api_key, prov)
        _llm_cache[cache_key] = client
        logger.info(
            "LLM client created: provider=%s key=%s",
            prov,
            "custom" if api_key else "server-env",
        )
    return _llm_cache[cache_key]


def llm_invoke(messages, api_key: str | None = None) -> tuple[str, str]:
    """
    Invoke the LLM and return (answer, provider_name).
    Retries on transient errors; quota/auth errors propagate immediately.
    """
    if api_key:
        prov = detect_provider(api_key)
    else:
        prov = config.llm.provider.lower()

    retryable = _retryable_exceptions(prov)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(retryable) if retryable else retry_if_exception_type(()),
        before_sleep=lambda s: logger.warning(
            "LLM call failed (attempt %d/3), retrying...", s.attempt_number
        ),
    )
    def _invoke():
        if api_key:
            _prov = detect_provider(api_key)
        else:
            _prov = config.llm.provider.lower()
        cache_key = f"{_prov}:{api_key or '__default__'}"
        try:
            llm = get_llm(api_key)
            response = llm.invoke(messages)
            if isinstance(response.content, str):
                return response.content
            return " ".join(
                p.get("text", str(p)) if isinstance(p, dict) else str(p)
                for p in response.content
            )
        except Exception:
            # Evict this cache entry so the next request won't reuse a broken client
            _llm_cache.pop(cache_key, None)
            raise

    return _invoke(), prov


def clear_llm_cache() -> None:
    global _llm_cache
    _llm_cache = {}
    logger.info("LLM client cache cleared.")


# Backward-compat alias
clear_llm = clear_llm_cache
