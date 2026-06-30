import random

import httpx2

from .config import BACKOFF_BASE, BACKOFF_MAX, RETRYABLE_STATUS


_RETRYABLE_TRANSPORT_ERRORS: tuple[type[Exception], ...] = (
    httpx2.ConnectError,
    httpx2.ConnectTimeout,
    httpx2.ReadTimeout,
    httpx2.WriteTimeout,
    httpx2.PoolTimeout,
    httpx2.RemoteProtocolError,
)


def is_retryable(exc: Exception) -> bool:
    """True if the client should wait and try again for this error."""
    if isinstance(exc, _RETRYABLE_TRANSPORT_ERRORS):
        return True
    if isinstance(exc, httpx2.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS
    return False


def retry_after(exc: Exception) -> float | None:
    """Honor a server-sent `Retry-After` header if present.
    Returns None when there's no usable header, so the caller falls back to backoff.
    """
    response = getattr(exc, "response", None)
    if response is None:
        return None
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def backoff_delay(attempt: int) -> float:
    """Exponential backoff, capped at BACKOFF_MAX.."""
    ceiling = min(BACKOFF_MAX, BACKOFF_BASE * (2**attempt))
    return random.uniform(0.0, ceiling)
