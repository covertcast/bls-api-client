"""Pydantic models:
1. SeriesRequest  - validate inputs before sending the request.
2. BLSResponse    - validate the response and raise typed errors on failure.
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import Status
from .exceptions import BLSAPIError, BLSValidationError


def normalize_series_ids(
    series_ids: str | Sequence[str] | Mapping[str, str],
) -> tuple[list[str], dict[str, str] | None]:
    """Normalize the accepted `series_ids` shapes into (bls_ids, aliases).

    Accepts a single id, a sequence of ids, or a {label: id} mapping. Returns the list of
    BLS ids to request plus an optional {bls_id: label} map (inverted from the mapping) so
    downstream code can relabel the output. aliases is None when no mapping was given.

    This mirrors blsR's named-list feature. Raises BLSValidationError on empty input, blank
    ids, or a mapping whose ids aren't unique.
    """
    if isinstance(series_ids, str):
        _check_ids([series_ids])
        return [series_ids], None
    if isinstance(series_ids, Mapping):
        if not series_ids:
            raise BLSValidationError("series_ids mapping must not be empty")
        ids = list(series_ids.values())
        _check_ids(ids)
        aliases = {bls_id: label for label, bls_id in series_ids.items()}
        if len(aliases) != len(ids):
            raise BLSValidationError("series_ids mapping maps two labels to the same id")
        return ids, aliases
    ids = list(series_ids)
    if not ids:
        raise BLSValidationError("series_ids must not be empty")
    _check_ids(ids)
    return ids, None


def _check_ids(ids: list[str]) -> None:
    if not all(isinstance(i, str) and i.strip() for i in ids):
        raise BLSValidationError("every series id must be a non-empty string")


class SeriesRequest(BaseModel):
    """Validated inputs for a POST timeseries/data request."""

    series_ids: list[str]
    start_year: int | None = None
    end_year: int | None = None
    catalog: bool = False
    calculations: bool = False
    annual_average: bool = False
    aspects: bool = False
    latest: bool = False

    @model_validator(mode="after")
    def _validate(self) -> "SeriesRequest":
        if not self.series_ids:
            raise BLSValidationError("series_ids must not be empty")
        if (
            self.start_year is not None
            and self.end_year is not None
            and self.start_year > self.end_year
        ):
            raise BLSValidationError("start_year must be <= end_year")
        return self

    def to_payload(self, api_key: str | None) -> dict[str, Any]:
        """Render the minimal JSON body that the BLS API expects."""
        payload: dict = {"seriesid": self.series_ids}

        if self.catalog:
            payload["catalog"] = True
        if self.calculations:
            payload["calculations"] = True
        if self.annual_average:
            payload["annualaverage"] = True
        if self.aspects:
            payload["aspects"] = True
        if self.latest:
            payload["latest"] = True
        if self.start_year is not None:
            payload["startyear"] = str(self.start_year)
        if self.end_year is not None:
            payload["endyear"] = str(self.end_year)
        if api_key is not None:
            payload["registrationkey"] = api_key

        return payload


class SeriesResult(BaseModel):
    """One series in the response."""

    model_config = ConfigDict(populate_by_name=True)

    series_id: str = Field(alias="seriesID")
    catalog: dict[str, Any] | None = None
    data: list[dict[str, Any]] = Field(default_factory=list)


class Results(BaseModel):
    series: list[SeriesResult] = Field(default_factory=list)


class BLSResponse(BaseModel):
    """The top-level error checking"""

    model_config = ConfigDict(populate_by_name=True)

    status: str
    response_time: int | None = Field(default=None, alias="responseTime")
    message: list[str] = Field(default_factory=list)
    results: Results | None = Field(default=None, alias="Results")

    @model_validator(mode="after")
    def validate_response(self) -> BLSResponse:
        if self.status != Status.SUCCEEDED:
            raise BLSAPIError(
                "; ".join(self.message) or self.status,
                status=self.status,
                messages=self.message,
            )
        for msg in self.message:
            warnings.warn(msg, stacklevel=2)
        return self

    @property
    def series(self) -> list[SeriesResult]:
        """Convenience accessor"""
        return self.results.series if self.results is not None else []
