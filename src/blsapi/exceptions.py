"""Exception hierarchy for the blsapi client."""


class BLSError(Exception):
    """Base class for every error raised by this library."""


class BLSValidationError(BLSError):
    """Bad input caught locally."""


class BLSAPIError(BLSError):
    """BLS processed the request but returned a non-success `status`.

    Carries the raw status string and the `message` list so callers can inspect them.
    """

    def __init__(
        self,
        message: str,
        *,
        status: str | None = None,
        messages: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.messages = messages or []


class BLSHTTPError(BLSError):
    """Transport- or HTTP-level failure that survived our retry loop."""
