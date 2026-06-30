"""Default configuration constants and helpers for the BLS client.
Everything here is a sensible default that the client constructor can override.
"""

import os
import warnings

import httpx2

from .__about__ import __version__

# endpoints & auth
DEFAULT_BASE_URL = "https://api.bls.gov/publicAPI/v2/"
API_KEY_ENV_VAR = "BLS_API_KEY"

# BLS asks clients to identify themselves.
DEFAULT_USER_AGENT = f"bls-api-client/{__version__}"
# Registration keys are 32 hex chars.
EXPECTED_KEY_LENGTH = 32

# timeouts
DEFAULT_TIMEOUT = httpx2.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)

# application-level retry/backoff
DEFAULT_MAX_RETRIES = 3
BACKOFF_BASE = 0.5  # seconds; first backoff ceiling
BACKOFF_MAX = 30.0  # seconds; cap so jittered backoff can't explode
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

# BLS tier limits: (series_per_request, years_per_request, daily_queries)
# These are used for input validation and auto-batching. The limits differ when a registration key is present.
LIMITS_WITH_KEY = (50, 20, 500)
LIMITS_NO_KEY = (25, 10, 25)


def limits_for(api_key: str | None) -> tuple[int, int, int]:
    """Return (series_per_request, years_per_request, daily_queries) for the active tier."""
    return LIMITS_WITH_KEY if api_key else LIMITS_NO_KEY


def resolve_api_key(api_key: str | None) -> str | None:
    """Resolve the effective API key.

    Warns when the key isn't the expected length.
    """
    if api_key is None:
        api_key = os.environ.get(API_KEY_ENV_VAR)
    if api_key is not None and len(api_key) != EXPECTED_KEY_LENGTH:
        warnings.warn(
            f"BLS API key is {len(api_key)} characters; expected {EXPECTED_KEY_LENGTH}.",
            stacklevel=3,
        )
    return api_key
