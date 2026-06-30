"""Batching helpers to help work around BLS per-request limits.

BLS caps each request at N series and an M-year span (25/10 without a key, 50/20 with).
To fetch more, the client splits into chunks, issues several requests, and stitches the
results back together.
"""

import math
from collections.abc import Iterator, Sequence


def chunk_series(ids: Sequence[str], size: int) -> Iterator[list[str]]:
    """Yield successive `size`-length chunks of series ids.

    list(chunk_series(["a", "b", "c"], 2))
    [['a', 'b'], ['c']]
    """
    if size < 1:
        raise ValueError("size must be >= 1")
    for start in range(0, len(ids), size):
        yield list(ids[start : start + size])


def year_windows(start: int, end: int, span: int) -> Iterator[tuple[int, int]]:
    """Yield inclusive (lo, hi) year windows no longer than `span` years.

    list(year_windows(2000, 2024, 10))
    [(2000, 2009), (2010, 2019), (2020, 2024)]
    """
    if span < 1:
        raise ValueError("span must be >= 1")
    if start > end:
        raise ValueError("start must be <= end")
    lo = start
    while lo <= end:
        hi = min(lo + span - 1, end)
        yield (lo, hi)
        lo = hi + 1


def estimate_query_count(
    n_series: int,
    start_year: int | None,
    end_year: int | None,
    series_limit: int,
    year_limit: int,
) -> int:
    """How many API calls a get_series() will consume after batching.

    Useful for staying under the daily quota; exposed via BLSClient.query_cost().
    A year range only multiplies the count when BOTH years are given (otherwise BLS
    returns its default window in a single call).
    """
    series_chunks = max(1, math.ceil(n_series / series_limit))
    if start_year is None or end_year is None:
        year_chunks = 1
    else:
        year_chunks = max(1, math.ceil((end_year - start_year + 1) / year_limit))
    return series_chunks * year_chunks
