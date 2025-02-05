"""Error handling for StackSpot provider."""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class StackSpotError(Exception):
    """Base exception for StackSpot errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_content: Optional[str] = None,
    ):
        """Initialize StackSpot error.

        Args:
            message: Error message.
            status_code: Optional HTTP status code.
            response_content: Optional response content.
        """
        super().__init__(message)
        self.status_code = status_code
        self.response_content = response_content
        logger.error(f"StackSpot error: {message}")
        if status_code:
            logger.error(f"Status code: {status_code}")
        if response_content:
            logger.error(f"Response content: {response_content}")


class AuthenticationError(StackSpotError):
    """Authentication related errors."""

    pass


class AuthorizationError(StackSpotError):
    """Authorization related errors."""

    pass


class RateLimitError(StackSpotError):
    """Rate limit related errors."""

    pass


class ServerError(StackSpotError):
    """Server related errors."""

    pass


class InvalidRequestError(StackSpotError):
    """Invalid request related errors."""

    pass


def handle_http_error(error: httpx.HTTPError) -> None:
    """Handle HTTP errors and raise appropriate exceptions.

    Args:
        error: The HTTP error to handle.

    Raises:
        AuthenticationError: For 401 errors.
        AuthorizationError: For 403 errors.
        RateLimitError: For 429 errors.
        ServerError: For 5xx errors.
        InvalidRequestError: For other errors.
    """
    status_code = None
    response_content = None

    if hasattr(error, "response"):
        status_code = error.response.status_code
        response_content = (
            error.response.content.decode() if error.response.content else None
        )

    logger.error(f"HTTP error occurred: {str(error)}")
    if status_code:
        logger.error(f"Status code: {status_code}")
    if response_content:
        logger.error(f"Response content: {response_content}")

    if status_code == 401:
        raise AuthenticationError(
            "Authentication failed: Invalid credentials",
            status_code=status_code,
            response_content=response_content,
        )
    elif status_code == 403:
        raise AuthorizationError(
            "Authorization failed: Insufficient permissions",
            status_code=status_code,
            response_content=response_content,
        )
    elif status_code == 429:
        raise RateLimitError(
            "Rate limit exceeded",
            status_code=status_code,
            response_content=response_content,
        )
    elif status_code and status_code >= 500:
        raise ServerError(
            "Server error occurred",
            status_code=status_code,
            response_content=response_content,
        )
    else:
        raise InvalidRequestError(
            f"Request failed: {str(error)}",
            status_code=status_code,
            response_content=response_content,
        )
