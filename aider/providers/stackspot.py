"""StackSpot AI provider implementation.

This module implements the StackSpot AI provider, which provides access to StackSpot's
AI capabilities through their API. The provider handles authentication, request
management, and response processing.

The provider supports:
- Authentication with client credentials
- Automatic token refresh
- Request retry with exponential backoff
- Concurrent request handling
- Proper error handling and logging
- Configurable timeouts and polling
"""

import asyncio
import json
import logging
import os
import time
from typing import Dict, List, Optional

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .stackspot_config import configure_stackspot
from .stackspot_constants import (
    CONTENT_TYPE_MAP,
    ENV_CLIENT_KEY,
    ERROR_MESSAGES,
    TOKEN_REFRESH_THRESHOLD,
)
from .stackspot_errors import (
    InvalidRequestError,
    StackSpotError,
    handle_http_error,
)

# Configure logging
logger = logging.getLogger(__name__)


class TokenInfo:
    """Token information and management.

    This class handles token lifecycle management, including expiration tracking
    and refresh scheduling.

    Attributes:
        token: The access token string.
        created_at: Timestamp when the token was created.
        expires_in: Token lifetime in seconds.
        refresh_threshold: Percentage of token lifetime after which to refresh.
    """

    def __init__(self, token: str, expires_in: int):
        """Initialize token info.

        Args:
            token: The access token string.
            expires_in: Token lifetime in seconds.
        """
        self.token = token
        self.created_at = time.time()
        self.expires_in = expires_in
        self.refresh_threshold = TOKEN_REFRESH_THRESHOLD
        logger.debug(f"Token initialized with {expires_in}s lifetime")

    @property
    def is_expired(self) -> bool:
        """Check if token is expired.

        Returns:
            True if the token has expired, False otherwise.
        """
        expired = time.time() >= self.created_at + self.expires_in
        if expired:
            logger.debug("Token is expired")
        return expired

    @property
    def needs_refresh(self) -> bool:
        """Check if token needs refresh.

        Returns:
            True if the token should be refreshed, False otherwise.
        """
        elapsed = time.time() - self.created_at
        needs_refresh = elapsed >= self.expires_in * self.refresh_threshold
        if needs_refresh:
            logger.debug(f"Token needs refresh (elapsed: {elapsed}s)")
        return needs_refresh

    @property
    def remaining_time(self) -> float:
        """Get remaining time in seconds.

        Returns:
            Number of seconds until token expiration.
        """
        remaining = max(0, (self.created_at + self.expires_in) - time.time())
        logger.debug(f"Token remaining time: {remaining}s")
        return remaining


class StackSpotCommand(BaseModel):
    """Base model for StackSpot commands.

    This model defines the structure of commands sent to the StackSpot API.

    Attributes:
        input_data: The prompt or input text.
        conversation_id: Optional conversation identifier.
        model: The model to use for completion.
        temperature: The sampling temperature.
        max_tokens: Maximum number of tokens to generate.
    """

    model_config = ConfigDict(populate_by_name=True)

    input_data: str
    conversation_id: Optional[str] = None
    model: str = "stackspot-ai"
    temperature: float = 0.7
    max_tokens: Optional[int] = None


class StackSpotResponse(BaseModel):
    """StackSpot response model.

    This model defines the structure of responses from the StackSpot API.

    Attributes:
        id: Unique response identifier.
        content: The generated content.
        metadata: Optional response metadata.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: f"ssp-{int(time.time())}")
    content: str
    metadata: Optional[Dict] = None


class StackSpotProvider:
    """StackSpot AI provider implementation.

    This class implements the interface to StackSpot's AI services, handling all
    aspects of communication with their API.

    Attributes:
        config: Provider configuration.
        http_client: HTTP client for making requests.
        token_info: Current token information.
        conversation_id: Current conversation identifier.
        _auth_lock: Lock for synchronizing token operations.
    """

    content_type_map = CONTENT_TYPE_MAP

    def __init__(self, api_key: Optional[str] = None):
        """Initialize StackSpot provider.

        Args:
            api_key: Optional API key. If provided, it will override the environment variable.
        """
        logger.info("Initializing StackSpot provider")

        if api_key:
            logger.debug("Using provided API key")
            os.environ[ENV_CLIENT_KEY] = api_key

        self.config = configure_stackspot()
        self.http_client = httpx.AsyncClient(
            timeout=self.config["defaults"]["timeout"],
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
        self.token_info = None
        self.conversation_id = None
        self._auth_lock = asyncio.Lock()
        logger.info("StackSpot provider initialized successfully")

    @property
    def access_token(self) -> Optional[str]:
        """Get current access token.

        Returns:
            The current access token if available, None otherwise.
        """
        return self.token_info.token if self.token_info else None

    async def _get_access_token(self) -> str:
        """Get access token for API requests with automatic refresh.

        Returns:
            A valid access token.

        Raises:
            ValueError: If token acquisition fails.
        """
        async with self._auth_lock:
            if self.token_info and not self.token_info.is_expired:
                if self.token_info.needs_refresh:
                    logger.info("Token needs refresh, fetching new token")
                    await self._refresh_token()
                return self.token_info.token

            logger.info("No valid token available, fetching new token")
            return await self._fetch_new_token()

    async def _fetch_new_token(self) -> str:
        """Fetch a new access token.

        Returns:
            A new access token.

        Raises:
            ValueError: If token acquisition fails.
        """
        auth_url = self.config["auth"]["auth_url"]
        logger.info(f"Fetching new token from {auth_url}")

        data = {
            "grant_type": "client_credentials",
            "client_id": self.config["auth"]["client_id"],
            "client_secret": self.config["auth"]["secret_key"],
        }

        try:
            response = await self._make_request(
                "post",
                auth_url,
                headers=self._get_headers("form"),
                data=data,
                retry_auth=False,
            )

            token_data = response.json()
            logger.debug("Token response received")

            if "access_token" not in token_data or "expires_in" not in token_data:
                logger.error(f"Invalid token response format: {token_data}")
                raise InvalidRequestError("Invalid token response format")

            self.token_info = TokenInfo(
                token=token_data["access_token"],
                expires_in=token_data["expires_in"],
            )

            logger.info(f"New token obtained (expires in {token_data['expires_in']}s)")
            return self.token_info.token

        except httpx.HTTPError as e:
            logger.error("HTTP error during token fetch")
            handle_http_error(e)
        except Exception as e:
            logger.error(
                f"Unexpected error during token fetch: {str(e)}", exc_info=True
            )
            raise StackSpotError(f"Failed to obtain access token: {str(e)}")

    async def _refresh_token(self) -> None:
        """Refresh the current access token.

        Raises:
            ValueError: If token refresh fails.
        """
        try:
            await self._fetch_new_token()
        except Exception as e:
            logger.error(f"Failed to refresh token: {str(e)}")
            # Clear token info to force new token fetch on next request
            self.token_info = None
            raise

    def _get_headers(self, content_type: str = "json") -> Dict[str, str]:
        """Return headers for requests.

        Args:
            content_type: The content type to use (json or form).

        Returns:
            A dictionary of HTTP headers.
        """
        headers = self.config["api"]["headers"].copy()
        headers["Content-Type"] = self.content_type_map[content_type]
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def _make_request(
        self,
        method: str,
        url: str,
        retry_auth: bool = True,
        **kwargs,
    ) -> httpx.Response:
        """Make an HTTP request with automatic token refresh.

        Args:
            method: HTTP method to use.
            url: URL to request.
            retry_auth: Whether to retry with a new token on auth failure.
            **kwargs: Additional arguments to pass to httpx.

        Returns:
            The HTTP response.

        Raises:
            httpx.HTTPError: If the request fails.
        """
        logger.debug(f"Making {method.upper()} request to {url}")
        logger.debug(f"Request kwargs: {json.dumps(kwargs, default=str)}")

        try:
            response = await self.http_client.request(method, url, **kwargs)
            logger.debug(f"Response status: {response.status_code}")

            if response.status_code >= 400:
                logger.error(f"Request failed with status {response.status_code}")
                logger.error(f"Response content: {response.content}")

                if response.status_code in (401, 403) and retry_auth:
                    logger.info("Authentication failed, attempting to refresh token")
                    self.token_info = None
                    if "headers" in kwargs:
                        kwargs["headers"]["Authorization"] = (
                            f"Bearer {await self._get_access_token()}"
                        )
                    return await self._make_request(
                        method, url, retry_auth=False, **kwargs
                    )

                response.raise_for_status()

            return response

        except httpx.HTTPError as e:
            logger.error("HTTP error during request")
            handle_http_error(e)
        except Exception as e:
            logger.error(f"Unexpected error during request: {str(e)}", exc_info=True)
            raise StackSpotError(f"Request failed: {str(e)}")

    async def _start_execution(
        self,
        prompt: str,
        model: str = "stackspot-ai",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Start execution and return execution ID.

        Args:
            prompt: The input prompt.
            model: The model to use.
            temperature: The sampling temperature.
            max_tokens: Maximum number of tokens to generate.

        Returns:
            The execution ID.

        Raises:
            ValueError: If execution start fails.
        """
        suffix_url = (
            f"?conversation_id={self.conversation_id}" if self.conversation_id else ""
        )
        url = f"{self.config['api']['create_exec_url']}/{self.config['api']['remote_qc_name']}{suffix_url}"

        # Create command with all parameters
        command_data = {
            "input_data": prompt,
            "conversation_id": self.conversation_id,
            "model": model,
            "temperature": temperature,
        }
        if max_tokens is not None:
            command_data["max_tokens"] = max_tokens

        command = StackSpotCommand(**command_data)

        try:
            logger.debug(f"Starting execution with prompt: {prompt[:100]}...")
            response = await self._make_request(
                "post",
                url,
                headers=self._get_headers(),
                data=json.dumps(command.model_dump(exclude_none=True)),
            )
            execution_id = response.text.strip('"')
            logger.debug(f"Execution started with ID: {execution_id}")
            return execution_id
        except httpx.HTTPError as e:
            self._handle_http_error(e)

    async def _check_execution(self, execution_id: str) -> Dict:
        """Check execution status and return result.

        Args:
            execution_id: The execution ID to check.

        Returns:
            The execution result.

        Raises:
            ValueError: If execution check fails.
            TimeoutError: If execution check times out.
        """
        url = f"{self.config['api']['check_exec_url']}/{execution_id}"
        attempts = 0
        max_attempts = self.config["defaults"]["max_polling_attempts"]
        polling_interval = self.config["defaults"]["polling_interval"]

        while attempts < max_attempts:
            try:
                logger.debug(
                    f"Checking execution status (attempt {attempts + 1}/{max_attempts})"
                )
                response = await self._make_request(
                    "get", url, headers=self._get_headers()
                )
                data = response.json()

                status = data.get("progress", {}).get("status")
                if status == "COMPLETED":
                    logger.debug("Execution completed successfully")
                    return data
                elif status == "FAILED":
                    error_msg = data.get("progress", {}).get("error", "Unknown error")
                    raise ValueError(
                        ERROR_MESSAGES["execution_failed"].format(error=error_msg)
                    )
                elif status == "CANCELLED":
                    raise ValueError(ERROR_MESSAGES["execution_cancelled"])

                attempts += 1
                logger.debug(f"Execution in progress, status: {status}")
                await asyncio.sleep(polling_interval)
            except httpx.HTTPError as e:
                self._handle_http_error(e)

        raise TimeoutError(
            ERROR_MESSAGES["request_timeout"].format(
                attempts=f"{max_attempts} attempts ({max_attempts * polling_interval} seconds)"
            )
        )

    def _handle_http_error(self, error: httpx.HTTPError):
        """Handle HTTP errors.

        Args:
            error: The HTTP error to handle.

        Raises:
            ValueError: With appropriate error message.
        """
        logger.error(f"HTTP error occurred: {str(error)}")
        if not hasattr(error, "response"):
            raise ValueError(f"Request failed: {str(error)}")

        status_code = error.response.status_code
        logger.error(f"Response status code: {status_code}")
        logger.error(f"Response content: {error.response.content}")

        if status_code == 401:
            raise ValueError("Authentication failed: Invalid credentials")
        elif status_code == 403:
            raise ValueError("Authorization failed: Insufficient permissions")
        elif status_code == 404:
            raise ValueError("Resource not found")
        elif status_code == 429:
            raise ValueError("Rate limit exceeded")
        elif status_code >= 500:
            raise ValueError("Server error occurred")
        else:
            raise ValueError(f"Request failed with status {status_code}")

    def _format_response(self, stackspot_response: Dict) -> Dict:
        """Format StackSpot response to standard format."""
        logger.debug(f"Formatting response: {stackspot_response}")

        try:
            if not stackspot_response:
                logger.error("Response is None or empty")
                return self._create_error_response("Error: Empty response from API")

            if not isinstance(stackspot_response, dict):
                logger.error(
                    f"Response is not a dictionary: {type(stackspot_response)}"
                )
                return self._create_error_response("Error: Invalid response format")

            content = stackspot_response.get("content", "")
            if not content:
                logger.error("Empty content in response")
                return self._create_error_response("Error: Empty content in response")

            # Get token counts from metadata if available
            metadata = stackspot_response.get("metadata", {})
            prompt_tokens = metadata.get("prompt_tokens", 0)
            completion_tokens = metadata.get("completion_tokens", 0)
            total_tokens = metadata.get(
                "total_tokens", prompt_tokens + completion_tokens
            )

            # Create response with proper token counts
            formatted = {
                "id": f"ssp-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": stackspot_response.get("model", "stackspot-ai"),
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                },
            }
            logger.debug(f"Final formatted response: {formatted}")
            return formatted

        except Exception as e:
            logger.error(f"Error formatting response: {str(e)}", exc_info=True)
            return self._create_error_response(f"Error: {str(e)}")

    def _create_error_response(self, error_message: str) -> Dict:
        """Create a standardized error response."""
        return {
            "id": f"ssp-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "stackspot-ai",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": error_message},
                    "finish_reason": "error",
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }

    async def completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "stackspot-ai",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        conversation_id: Optional[str] = None,
        **kwargs,
    ) -> Dict:
        """Generate completion from messages.

        Args:
            messages: List of message dictionaries.
            model: Model to use for completion.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            stream: Whether to stream the response.
            conversation_id: Optional conversation identifier.
            **kwargs: Additional arguments.

        Returns:
            The completion response.

        Raises:
            ValueError: If the request fails.
        """
        logger.info("Starting completion request")
        if not messages:
            logger.error("No messages provided")
            raise InvalidRequestError("No messages provided")

        # Extract prompt and validate messages
        prompt = ""
        for message in messages:
            logger.debug(f"Processing message: {message}")
            content = message.get("content", "").strip()
            if not content:
                logger.error("Empty content in message")
                raise InvalidRequestError("Empty content in message")
            prompt += f"{content}\n"

        logger.debug(f"Final prompt: {prompt}")
        logger.debug(f"Using model: {model}")
        logger.debug(f"Temperature: {temperature}")
        logger.debug(f"Max tokens: {max_tokens}")

        # Check against model limits
        model_config = self.config["models"].get(model, {})
        max_input_tokens = model_config.get("max_input_tokens", 16384)
        max_output_tokens = model_config.get("max_output_tokens", 8192)

        # Use tiktoken for accurate token counting if available
        try:
            import tiktoken

            encoding = tiktoken.encoding_for_model(
                "gpt-3.5-turbo"
            )  # Use GPT-3.5 encoding as fallback
            input_tokens = len(encoding.encode(prompt))
            logger.debug(f"Accurate input token count: {input_tokens}")
        except ImportError:
            # Fallback to rough estimation
            input_tokens = len(prompt.split())
            logger.debug(f"Estimated input token count: {input_tokens}")

        if input_tokens > max_input_tokens:
            logger.error(f"Input tokens {input_tokens} exceed limit {max_input_tokens}")
            raise InvalidRequestError(
                f"Input tokens exceed limit of {max_input_tokens}"
            )

        if max_tokens and max_tokens > max_output_tokens:
            logger.warning(
                f"Requested max_tokens {max_tokens} exceeds limit {max_output_tokens}"
            )
            max_tokens = max_output_tokens

        try:
            # Start execution
            execution_id = await self._start_execution(
                prompt, model, temperature, max_tokens=max_tokens
            )
            logger.info(f"Execution started with ID: {execution_id}")

            # Check execution result
            result = await self._check_execution(execution_id)
            logger.debug(f"Raw execution result: {result}")

            # Format response
            response = self._format_response(result)
            logger.info("Response formatted successfully")
            logger.debug(f"Final response: {response}")

            return response
        except StackSpotError:
            raise
        except Exception as e:
            logger.error(f"Completion request failed: {str(e)}", exc_info=True)
            raise StackSpotError(f"Completion request failed: {str(e)}")

    async def close(self):
        """Close the HTTP client."""
        logger.info("Closing HTTP client")
        if self.http_client and not self.http_client.is_closed:
            await self.http_client.aclose()

    def __del__(self):
        """Cleanup when destroying the object."""
        logger.debug("StackSpot provider cleanup")
        if self.http_client and not self.http_client.is_closed:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.close())
                else:
                    loop.run_until_complete(self.close())
            except Exception as e:
                logger.debug(f"Error during cleanup: {e}")
                # If we can't clean up properly, just ignore it
                pass
