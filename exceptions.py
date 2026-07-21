"""
Custom application exceptions.

Having a dedicated exception hierarchy allows Flask error handlers
to automatically distinguish between:
- errors caused by invalid user input (HTTP 4xx)
- errors caused by unavailable data (HTTP 404)
- errors caused by unreachable external services (HTTP 502)
- bugs or unexpected errors (HTTP 500)

without having to inspect the error message text in every route.
"""

class MotoGPStatsError(Exception):
    """Base class for all known and handled application errors."""
    pass

class InvalidParameterError(MotoGPStatsError):
    """Raised when the parameters provided by the client are invalid (HTTP 400)."""
    pass

class DataNotFoundError(MotoGPStatsError):
    """Raised when the requested data is not available, e.g., a missing PDF
    for the requested year/GP/session combination (HTTP 404)."""
    pass

class UpstreamServiceError(MotoGPStatsError):
    """Raised when MotoGP servers are unreachable due to network issues
    (timeout, connection refused, etc.), rather than missing data (HTTP 502)."""
    pass