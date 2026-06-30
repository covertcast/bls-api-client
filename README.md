# blsapi

[![PyPI version](https://img.shields.io/pypi/v/blsapi.svg)](https://pypi.org/project/blsapi/)
[![Python versions](https://img.shields.io/pypi/pyversions/blsapi.svg)](https://pypi.org/project/blsapi/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A **sync + async** client inspired by `blsR` for the [U.S. Bureau of Labor Statistics
(BLS) Public Data API](https://www.bls.gov/developers/).

- **Sync and async** clients (`BLSClient`, `AsyncBLSClient`).
- **Polars output** returns easy to use and convert Polars Dataframes.
- **Automatic batching** over the BLS per-request limits (series count and year span).

## Installation

Requires Python 3.11+:
```bash
pip install bls-api-client
# or
uv add bls-api-client
```

```python
import blsapi
```

## Quick start

```python
from blsapi import BLSClient

with BLSClient() as client:
    df = client.get_series("LNS14000000", start_year=2023, end_year=2024)

print(df)
```

The result is a tidy/long DataFrame. Exporting elsewhere is
simple:

```python
df.write_parquet("data.parquet")
df.write_csv("data.csv")
df.to_pandas()
df.to_arrow()
```

### Async

```python
import anyio
from blsapi import AsyncBLSClient

async def main():
    async with AsyncBLSClient() as client:
        df = await client.get_series("LNS14000000", start_year=2023, end_year=2024)
        print(df)

anyio.run(main)
```

## Configuration

Everything has a sensible default, so `blsapi` works out of the box.

### API key

A registration key is optional but raises your rate limits substantially. The key is resolved with this precedence:

1. The explicit `api_key=` argument, if given.
2. Otherwise the `BLS_API_KEY` environment variable.
3. Otherwise no key (unauthenticated tier).

### Example:
```python
# Explicit (highest precedence)
client = BLSClient(api_key="your_32_char_key")

# Or rely on the environment
#   export BLS_API_KEY=your_32_char_key   (macOS/Linux)
#   $env:BLS_API_KEY = "your_32_char_key" (PowerShell)
client = BLSClient()

client.has_key  # returns True if a key is active
```

### Other options

All are keyword-only on both clients:

| Argument      | Default                          | Purpose                                                        |
| ------------- | -------------------------------- | -------------------------------------------------------------- |
| `api_key`     | `None` -> `BLS_API_KEY`           | Registration key.                                              |
| `base_url`    | `https://api.bls.gov/publicAPI/v2/` | API base URL.               |
| `timeout`     | `5/30/10/5s` (connect/read/write/pool) | `httpx2.Timeout`.                            |
| `max_retries` | `3`                              | Application-level retries for transient failures.              |
| `auto_batch`  | `True`                           | Transparently split over the tier limits.                      |
| `user_agent`  | `blsapi/<version>`               | Sent as `User-Agent`.     |
| `client`      | `None`                           | Inject your own `httpx2.Client`/`AsyncClient`.|

```python
import httpx2
from blsapi import BLSClient

client = BLSClient(
    api_key="…",
    max_retries=5,
    timeout=httpx2.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0),
    user_agent="my-app/1.0 (you@example.com)",
)
```

## Usage

### Multiple series and named aliases

Pass a list of ids, or a `{label: id}` mapping to relabel the output's `series_id` column:

```python
df = client.get_series(
    {"unemployment": "LNS14000000", "cpi": "CUUR0000SA0"},
    start_year=2020,
    end_year=2024,
)
df["series_id"].unique().to_list()  # -> ["cpi", "unemployment"]
```

### Wide format

Reshape the long frame to one value column per series, indexed by date:

```python
from blsapi import pivot_wide

wide = pivot_wide(df)  # columns: date, unemployment, cpi
```

(Annual-average rows have no real date and are dropped by `pivot_wide`.)

### Calculations and catalog

```python
df = client.get_series(
    "LNS14000000", start_year=2023, end_year=2024, calculations=True
)
# adds net_change_{1,3,6,12}m and pct_change_{1,3,6,12}m columns

resp = client.get_series_raw("LNS14000000", catalog=True)  # -> BLSResponse with catalog metadata
```

### Surveys and popular series

```python
client.list_surveys()        # -> DataFrame of all surveys
client.get_survey("CU")      # -> dict of metadata for one survey
client.get_popular()         # -> list of popular series ids
client.get_popular("LN")     # -> popular ids within a survey
```

### Quota planning

```python
client.query_cost(["LNS14000000", "CUUR0000SA0"], 2000, 2024)  # -> number of API calls used
```

## Error handling

All errors derive from `BLSError`, so you can catch broadly or narrowly:

```python
from blsapi import BLSError, BLSValidationError, BLSAPIError, BLSHTTPError

try:
    df = client.get_series("BAD_ID", start_year=2024, end_year=2023)
except BLSValidationError:
    ...  # bad input caught locally, before any network call
except BLSAPIError as e:
    ...  # BLS returned a non-success status; inspect e.status and e.messages
except BLSHTTPError:
    ...  # transport/HTTP failure that survived the retry loop
except BLSError:
    ...  # anything else from this library
```

## Tiers & limits

| | Series per request | Years per request | Queries per day |
| --- | --- | --- | --- |
| **No key** | 25 | 10 | 25 |
| **With key** | 50 | 20 | 500 |

With `auto_batch=True` (the default), requests that exceed the per-request limits are split
into multiple calls automatically and stitched back together. Register for a free key at
<https://data.bls.gov/registrationEngine/>.

## Development

```bash
uv sync          # install dependencies
uv build         # build the sdist + wheel
```

## License

[MIT](LICENSE)
