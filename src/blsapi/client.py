"""Synchronous BLS client."""

import time
from collections.abc import Mapping, Sequence

import httpx2
import polars as pl

from . import batching, config
from ._core import (
    build_data_request,
    merge_series,
    parse_data_response,
    plan_data_requests,
)
from ._endpoints import RequestSpec, popular_url, surveys_url
from ._retry import backoff_delay, is_retryable, retry_after
from .exceptions import BLSHTTPError
from .frames import series_to_frame
from .models import BLSResponse, SeriesRequest, normalize_series_ids


class BLSClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = config.DEFAULT_BASE_URL,
        timeout: float | httpx2.Timeout = config.DEFAULT_TIMEOUT,
        max_retries: int = config.DEFAULT_MAX_RETRIES,
        auto_batch: bool = True,
        user_agent: str = config.DEFAULT_USER_AGENT,
        client: httpx2.Client | None = None,
    ) -> None:
        self._api_key = config.resolve_api_key(api_key)
        self._base_url = base_url
        self._max_retries = max_retries
        self._auto_batch = auto_batch

        if client is not None:
            # Caller-supplied client.
            self._http = client
            self._owns_client = False
        else:
            transport = httpx2.HTTPTransport(retries=2)
            self._http = httpx2.Client(
                timeout=timeout, transport=transport, headers={"User-Agent": user_agent}
            )
            self._owns_client = True

    @property
    def has_key(self) -> bool:
        return self._api_key is not None

    def _send(self, spec: RequestSpec) -> dict:
        """Send a request with retry/backoff, returning parsed JSON."""
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._http.request(
                    spec.method, spec.url, json=spec.json, params=spec.params
                )
                response.raise_for_status()
                return response.json()
            except (httpx2.RequestError, httpx2.HTTPStatusError) as exc:
                last_exc = exc
                if attempt == self._max_retries or not is_retryable(exc):
                    raise BLSHTTPError(str(exc)) from exc
                time.sleep(retry_after(exc) or backoff_delay(attempt))
            except ValueError as exc:
                raise BLSHTTPError(f"BLS returned a non-JSON response: {exc}") from exc
        raise BLSHTTPError(str(last_exc)) from last_exc

    def get_series(
        self,
        series_ids: str | Sequence[str] | Mapping[str, str],
        *,
        start_year: int | None = None,
        end_year: int | None = None,
        catalog: bool = False,
        calculations: bool = False,
        annual_average: bool = False,
        aspects: bool = False,
        latest: bool = False,
        parse_values: bool = True,
    ) -> pl.DataFrame:
        """Fetch one or more series as a tidy Polars DataFrame.

        `series_ids` may be a single id, a sequence of ids, or a {label: id} mapping (the
        labels then replace the ids in the output's series_id column). When auto_batch is True,
        requests that exceed the tier limits are transparently split across multiple API
        calls and stitched back together by series id.
        """
        bls_ids, aliases = normalize_series_ids(series_ids)
        req = SeriesRequest(
            series_ids=bls_ids,
            start_year=start_year,
            end_year=end_year,
            catalog=catalog,
            calculations=calculations,
            annual_average=annual_average,
            aspects=aspects,
            latest=latest,
        )
        specs = plan_data_requests(req, self._api_key, self._base_url, self._auto_batch)
        series = merge_series(parse_data_response(self._send(spec)).series for spec in specs)
        return series_to_frame(series, parse_values=parse_values, aliases=aliases)

    def get_series_raw(
        self,
        series_ids: str | Sequence[str] | Mapping[str, str],
        **flags: object,
    ) -> BLSResponse:
        """Same inputs as get_series, but return the validated BLSResponse (no frame)."""
        bls_ids, _ = normalize_series_ids(series_ids)
        req = SeriesRequest(series_ids=bls_ids, **flags)
        spec = build_data_request(req, self._api_key, self._base_url)
        return parse_data_response(self._send(spec))

    def get_latest(self, series_id: str, **flags: object) -> pl.DataFrame:
        """Most-recent data point for a single series (get_series with latest=True)."""
        return self.get_series(series_id, latest=True, **flags)

    def list_surveys(self) -> pl.DataFrame:
        """All BLS surveys as a small DataFrame."""
        params = {"registrationkey": self._api_key} if self._api_key else None
        spec = RequestSpec("GET", surveys_url(self._base_url), params=params)
        payload = self._send(spec)
        return pl.DataFrame(payload["Results"]["survey"])

    def get_survey(self, survey_abbr: str) -> dict:
        """Metadata for a single survey."""
        params = {"registrationkey": self._api_key} if self._api_key else None
        spec = RequestSpec("GET", surveys_url(self._base_url, survey_abbr), params=params)
        return self._send(spec)["Results"]

    def get_popular(self, survey: str | None = None) -> list[str]:
        """The most popular series ids, optionally scoped to one survey."""
        params: dict[str, str] = {}
        if survey is not None:
            params["survey"] = survey
        if self._api_key:
            params["registrationkey"] = self._api_key
        spec = RequestSpec("GET", popular_url(self._base_url), params=params or None)
        payload = self._send(spec)
        return [s["seriesID"] for s in payload["Results"]["series"]]

    def query_cost(
        self,
        series_ids: str | Sequence[str] | Mapping[str, str],
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> int:
        """Calculates how many API calls a matching get_series() would consume."""
        bls_ids, _ = normalize_series_ids(series_ids)
        series_limit, year_limit, _ = config.limits_for(self._api_key)
        return batching.estimate_query_count(
            len(bls_ids), start_year, end_year, series_limit, year_limit
        )

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> "BLSClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
