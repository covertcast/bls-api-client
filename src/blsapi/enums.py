from enum import Enum


class Status(str, Enum):
    """Top-level `status` values BLS can return in the JSON envelope."""

    SUCCEEDED = "REQUEST_SUCCEEDED"
    NOT_PROCESSED = "REQUEST_NOT_PROCESSED"
    FAILED = "REQUEST_FAILED"


class PeriodType(str, Enum):
    """Classification of a BLS period code, derived from the M/Q/S/A prefix.

    ANNUAL_AVERAGE is special: M13, Q05, and S03 are *computed averages* over the year,
    not a point in calendar time, so they get no real `date` (see frames.period_to_date).
    """

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    ANNUAL = "annual"
    ANNUAL_AVERAGE = "annual_average"
