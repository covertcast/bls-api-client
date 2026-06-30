"""Utilities for both the sync and async clients."""

from .models import BLSResponse, SeriesRequest, SeriesResult
from ._endpoints import RequestSpec, data_url
from collections.abc import Iterable
from . import config
from .batching import chunk_series, year_windows


def build_data_request(req: SeriesRequest, api_key: str | None, base_url: str) -> RequestSpec:
    """Turn a validated SeriesRequest into a RequestSpec."""
    return RequestSpec(
        method="POST",
        url=data_url(base_url),
        json=req.to_payload(api_key),
    )


def parse_data_response(payload: dict) -> BLSResponse:
    """Validate the payload. Raises typed errors on failure."""
    return BLSResponse.model_validate(payload)


def plan_data_requests(
    req: SeriesRequest, api_key: str | None, base_url: str, auto_batch: bool
) -> list[RequestSpec]:
    """One RequestSpec per API call, splitting over the tier limits when auto_batch is enabled."""
    if not auto_batch:
        return [build_data_request(req, api_key, base_url)]

    series_limit, year_limit, _ = config.limits_for(api_key)
    if req.start_year is not None and req.end_year is not None:
        windows = list(year_windows(req.start_year, req.end_year, year_limit))
    else:
        windows = [(req.start_year, req.end_year)]  # no year filter produces a single window

    # every combination of series-chunk and year-window is one request.
    return [
        build_data_request(
            req.model_copy(update={"series_ids": ids, "start_year": lo, "end_year": hi}),
            api_key,
            base_url,
        )
        for ids in chunk_series(req.series_ids, series_limit)
        for lo, hi in windows
    ]


def merge_series(series_lists: Iterable[list[SeriesResult]]) -> list[SeriesResult]:
    """Combine SeriesResults from several responses, concatenating .data by series_id."""
    merged: dict[str, SeriesResult] = {}
    for series in series_lists:
        for s in series:
            if s.series_id in merged:
                merged[s.series_id].data.extend(s.data)  # same series, another year-window
            else:
                merged[s.series_id] = s  # first sighting
    return list(merged.values())
