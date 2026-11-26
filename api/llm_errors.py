from contextlib import contextmanager

from fastapi import HTTPException

from src.llm import LLMAPIError, LLMConfigError, LLMRateLimitError


def llm_http_error(exc: Exception, adapter=None) -> HTTPException | None:
    """HTTP response for an LLM error, or None if it isn't one. Name the active LLM Provider via `adapter`."""
    if isinstance(exc, (LLMConfigError, ImportError)):
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
