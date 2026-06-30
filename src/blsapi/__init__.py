"""blsapi - a sync + async client for the BLS Public Data API.

Quick start:

    from blsapi import BLSClient
    with BLSClient() as client:                      # reads BLS_API_KEY from env if set
        df = client.get_series("LNS14000000", start_year=2023, end_year=2024)

    # async
    from blsapi import AsyncBLSClient
    async with AsyncBLSClient() as client:
        df = await client.get_series("LNS14000000", start_year=2023, end_year=2024)

The result is a Polars DataFrame. Exporting it to other formats is simple:
    df.write_parquet(...), df.write_csv(...), df.to_pandas(), df.to_arrow()
"""

from .__about__ import __version__
from .aclient import AsyncBLSClient
from .client import BLSClient
from .enums import PeriodType
from .exceptions import (
    BLSAPIError,
    BLSError,
    BLSHTTPError,
    BLSValidationError,
)
from .frames import period_to_date, pivot_wide, series_to_frame
from .models import BLSResponse

__all__ = [
    "AsyncBLSClient",
    "BLSClient",
    "BLSError",
    "BLSValidationError",
    "BLSAPIError",
    "BLSHTTPError",
    "BLSResponse",
    "PeriodType",
    "series_to_frame",
    "pivot_wide",
    "period_to_date",
    "__version__",
]
