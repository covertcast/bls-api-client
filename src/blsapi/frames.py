"""Shape BLS results into tidy Polars DataFrames.

period_to_date() handles the M/Q/S/A period-code -> calendar-date mapping, including
the annual-average trap (M13/Q05/S03 don't have a real date). series_to_frame() runs the flatten
+ value-coercion + date-construction pipeline, and pivot_wide() reshapes the long frame to one column per series.
"""

import datetime as dt
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

import polars as pl

from .enums import PeriodType

if TYPE_CHECKING:
    from .models import SeriesResult


def period_to_date(year: int, period: str) -> tuple[PeriodType, dt.date | None]:
    """Map a (year, BLS period code) to a (PeriodType, first-of-period date).

    Annual-average codes (M13, Q05, S03) classify as ANNUAL_AVERAGE and return a None
    date, because they're a computed average over the year, not a moment in time. Keeping
    a None date lets callers filter them out cleanly.

    Raises ValueError on an unrecognized code.
    """
    code = period.strip().upper()
    kind, number = code[:1], int(code[1:])

    if kind == "M":
        if 1 <= number <= 12:
            return PeriodType.MONTHLY, dt.date(year, number, 1)
        if number == 13:
            return PeriodType.ANNUAL_AVERAGE, None
    elif kind == "Q":
        if 1 <= number <= 4:
            # Quarter start months: Q1->Jan, Q2->Apr, Q3->Jul, Q4->Oct.
            return PeriodType.QUARTERLY, dt.date(year, (number - 1) * 3 + 1, 1)
        if number == 5:
            return PeriodType.ANNUAL_AVERAGE, None
    elif kind == "S":
        if number in (1, 2):
            # Semiannual: S1->Jan (H1), S2->Jul (H2).
            return PeriodType.SEMIANNUAL, dt.date(year, 1 if number == 1 else 7, 1)
        if number == 3:
            return PeriodType.ANNUAL_AVERAGE, None
    elif kind == "A":
        return PeriodType.ANNUAL, dt.date(year, 1, 1)

    raise ValueError(f"Unrecognized BLS period code: {period!r}")


# Stable schema for an empty result.
_EMPTY_SCHEMA = {
    "series_id": pl.String,
    "year": pl.Int64,
    "period": pl.String,
    "period_name": pl.String,
    "period_type": pl.String,
    "date": pl.Date,
    "value": pl.Float64,
    "latest": pl.Boolean,
    "footnotes": pl.List,
}


def series_to_frame(
    series: "Sequence[SeriesResult]",
    *,
    parse_values: bool = True,
    aliases: "Mapping[str, str] | None" = None,
) -> pl.DataFrame:
    """Flatten BLS series results into one tidy/long Polars DataFrame.

    Each input SeriesResult has `.series_id` and `.data` (a list of raw BLS point dicts).
    Output is one row per (series, period), sorted by series then date.

    parse_values: when True (default) cast `value` to Float64; when False keep the raw BLS
        strings (mirrors blsR's parse_values=FALSE).
    aliases: optional {bls_id: label} to relabel the series_id column.
    """
    rows: list[dict] = []
    for result in series:
        for point in result.data:
            year = int(point["year"])
            period_type, date = period_to_date(year, point["period"])
            row = {
                "series_id": result.series_id,
                "year": year,
                "period": point["period"],
                "period_name": point.get("periodName"),
                "period_type": period_type.value,
                "date": date,
                "value": point.get("value"),
                "latest": bool(point.get("latest", False)),
                "footnotes": [fn for fn in point["footnotes"] if fn],
            }
            if "calculations" in point:
                net = point["calculations"].get("net_changes", {})
                pct = point["calculations"].get("pct_changes", {})
                for p in (1, 3, 6, 12):
                    row[f"net_change_{p}m"] = net.get(str(p))
                    row[f"pct_change_{p}m"] = pct.get(str(p))
            rows.append(row)

    if not rows:
        schema = dict(_EMPTY_SCHEMA)
        if not parse_values:
            schema["value"] = pl.String
        return pl.DataFrame(schema=schema)

    frame = pl.DataFrame(rows, infer_schema_length=None).with_columns(pl.col("date").cast(pl.Date))

    if parse_values:
        calc_cols = [c for c in frame.columns if c.startswith(("net_change_", "pct_change_"))]
        frame = frame.with_columns(
            pl.col("value").str.strip_chars().cast(pl.Float64, strict=False),
            *(pl.col(c).cast(pl.Float64, strict=False) for c in calc_cols),
        )

    if aliases:
        frame = frame.with_columns(pl.col("series_id").replace(aliases))
    return frame.sort(["series_id", "date"], nulls_last=True)


def pivot_wide(df: pl.DataFrame) -> pl.DataFrame:
    """Pivot the long frame to one value-column per series, indexed by date.

    Annual-average rows have a null date, so they're filtered out before pivoting; pivot on
    (year, period) instead if you need to keep them.
    """
    return (
        df.filter(pl.col("date").is_not_null())
        .pivot(values="value", index="date", on="series_id")
        .sort("date")
    )
