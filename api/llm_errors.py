from contextlib import contextmanager

from fastapi import HTTPException

from api.deps import get_store, profile_scoring_model
from src.llm import LLMAPIError, LLMConfigError, LLMRateLimitError, check_scoring_config, load_model_overrides


def llm_http_error(exc: Exception, adapter=None) -> HTTPException | None:
    """HTTP response for an LLM error, or None if it isn't one. Name the active LLM Provider via `adapter`."""
    if isinstance(exc, LLMConfigError):
        return HTTPException(status_code=503, detail=f"AI not configured: {exc}")
    name = getattr(adapter, "display_name", "LLM Provider")
    if isinstance(exc, LLMRateLimitError):
        return HTTPException(status_code=502, detail=f"{name} Rate Limit exceeded")
    if isinstance(exc, LLMAPIError):
        return HTTPException(status_code=502, detail=f"{name} API Error: {exc}")
    return None


@contextmanager
def llm_http_errors(adapter=None):
    """Turn LLM errors raised inside the block into HTTPExceptions."""
    try:
        yield
    except Exception as e:
        http_error = llm_http_error(e, adapter)
        if http_error is None:
            raise
        raise http_error from e


def require_scoring_config(profile: str) -> None:
    """Raise the 503 "AI not configured" before a run that will score is launched."""
    with llm_http_errors():
        check_scoring_config(
            profile_model=profile_scoring_model(profile),
            settings_overrides=load_model_overrides(get_store(profile)),
        )
