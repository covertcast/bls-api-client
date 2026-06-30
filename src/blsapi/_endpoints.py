from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RequestSpec:
    """Everything _send() needs to make a request"""

    method: str
    url: str
    json: dict[str, Any] | None = None
    params: dict[str, Any] | None = None


# All builders take the client's base_url so the same code works against v1 or v2.


def data_url(base_url: str) -> str:
    return f"{base_url}timeseries/data/"


def series_url(base_url: str, series_id: str) -> str:
    return f"{base_url}timeseries/data/{series_id}"


def popular_url(base_url: str) -> str:
    return f"{base_url}timeseries/popular"


def surveys_url(base_url: str, survey_abbr: str | None = None) -> str:
    if survey_abbr is None:
        return f"{base_url}surveys"
    return f"{base_url}surveys/{survey_abbr}"
