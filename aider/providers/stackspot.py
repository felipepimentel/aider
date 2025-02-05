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
    ERROR_MESSAGES,
)
from .stackspot_errors import (
    InvalidRequestError,
    StackSpotError,
    handle_http_error,
)

# Configure logging
logger = logging.getLogger(__name__)


class TokenInfo(BaseModel):
    """Token information model.

    This model stores authentication token information including the token itself
    and its expiration time.

    Attributes:
        token: The authentication token.
        expires_in: Time in seconds until the token expires.
    """

    model_config = ConfigDict(
        extra="allow",  # Permite campos extras
        validate_assignment=True,  # Valida atribuições
        frozen=False,  # Permite modificações
        str_strip_whitespace=True,  # Remove espaços em branco
    )

    token: str
    expires_in: int


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

    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        frozen=False,
        str_strip_whitespace=True,
    )

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

    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        frozen=False,
        str_strip_whitespace=True,
    )

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

    def __init__(self, api_key=None, client_id=None, realm=None):
        """Initialize the StackSpot provider.

        Args:
            api_key: Optional API key. If not provided, will try to get from environment.
            client_id: Optional client ID. If not provided, will try to get from environment.
            realm: Optional realm. If not provided, will try to get from environment.
        """
        self.api_key = api_key or os.getenv("STACKSPOTAI_CLIENT_KEY")
        self.client_id = client_id or os.getenv("STACKSPOTAI_CLIENT_ID")
        self.realm = realm or os.getenv("STACKSPOTAI_REALM")

        if not self.api_key:
            raise ValueError("STACKSPOTAI_CLIENT_KEY not found in environment")
        if not self.client_id:
            raise ValueError("STACKSPOTAI_CLIENT_ID not found in environment")
        if not self.realm:
            raise ValueError("STACKSPOTAI_REALM not found in environment")

        self.config = {
            "api_base": os.getenv(
                "STACKSPOTAI_API_URL", "https://genai-code-buddy-api.stackspot.com"
            ),
            "auth_url": os.getenv("STACKSPOTAI_AUTH_URL", "https://auth.stackspot.com"),
        }

        # Initialize other attributes
        self.http_client = None
        self.token_info = None
        self.conversation_id = None
        self._auth_lock = asyncio.Lock()

        # Load configuration
        try:
            self.config = configure_stackspot()
            logger.info("StackSpot provider initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize StackSpot provider: %s", str(e))
            raise

    @property
    def access_token(self) -> Optional[str]:
        """Get current access token.

        Returns:
            The current access token if available, None otherwise.
        """
        return self.token_info.token if self.token_info else None

    def initialize_client(self):
        """Initialize HTTP client with default configuration."""
        if self.http_client:
            return

        try:
            self.http_client = httpx.AsyncClient(
                timeout=self.config["defaults"]["timeout"],
                headers=self.config["api"]["headers"],
                follow_redirects=True,
            )
            logger.info("HTTP client initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize HTTP client: %s", str(e))
            raise

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
        if not self.http_client:
            self.initialize_client()

        auth_url = self.config["auth"]["auth_url"]
        logger.info("Fetching new token from %s", auth_url)

        data = {
            "grant_type": "client_credentials",
            "client_id": self.config["auth"]["client_id"],
            "client_secret": self.config["auth"]["secret_key"],
        }

        try:
            response = await self.http_client.post(
                auth_url,
                headers={"Content-Type": CONTENT_TYPE_MAP["form"]},
                data=data,
            )
            response.raise_for_status()

            token_data = response.json()
            logger.debug("Token response received")

            if "access_token" not in token_data or "expires_in" not in token_data:
                logger.error("Invalid token response format: %s", token_data)
                raise ValueError(ERROR_MESSAGES["invalid_token_response"])

            self.token_info = TokenInfo(
                token=token_data["access_token"],
                expires_in=token_data["expires_in"],
            )

            logger.info("New token obtained (expires in %ds)", token_data["expires_in"])
            return self.token_info.token

        except httpx.HTTPError as e:
            logger.error("HTTP error during token fetch: %s", str(e))
            handle_http_error(e)
        except Exception as e:
            logger.error("Unexpected error during token fetch: %s", str(e))
            raise StackSpotError(f"Failed to obtain access token: {str(e)}")

    async def _refresh_token(self) -> str:
        """Refresh the current access token.

        Returns:
            A new access token.

        Raises:
            ValueError: If token refresh fails.
        """
        logger.info("Refreshing access token")
        return await self._fetch_new_token()

    def _get_headers(self, content_type: str = "json") -> Dict[str, str]:
        """Get headers for API requests.

        Args:
            content_type: The content type to use (json or form).

        Returns:
            A dictionary of headers.
        """
        headers = self.config["api"]["headers"].copy()
        headers["Content-Type"] = self.content_type_map.get(
            content_type, self.content_type_map["json"]
        )
        if self.token_info and self.token_info.token:
            headers["Authorization"] = f"Bearer {self.token_info.token}"
        return headers

    async def _make_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str] = None,
        data: Dict = None,
        retry_auth: bool = True,
    ) -> httpx.Response:
        """Make an HTTP request with automatic token refresh.

        Args:
            method: The HTTP method to use.
            url: The URL to request.
            headers: Optional headers to include.
            data: Optional data to send.
            retry_auth: Whether to retry with a new token on auth failure.

        Returns:
            The HTTP response.

        Raises:
            httpx.HTTPError: If the request fails.
        """
        if not self.http_client:
            self.initialize_client()

        if retry_auth:
            token = await self._get_access_token()
            if not headers:
                headers = {}
            headers["Authorization"] = f"Bearer {token}"

        try:
            response = await self.http_client.request(
                method,
                url,
                headers=headers,
                json=data if method.lower() != "get" else None,
                params=data if method.lower() == "get" else None,
            )
            response.raise_for_status()
            return response

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401 and retry_auth:
                logger.info("Token expired, retrying with new token")
                self.token_info = None
                return await self._make_request(
                    method, url, headers, data, retry_auth=False
                )
            raise

    async def _start_execution(
        self,
        messages: List[Dict[str, str]],
        model: str = "stackspot-ai",
        temperature: float = 0.7,
        max_tokens: int = None,
    ) -> Dict:
        """Start a new execution.

        Args:
            messages: List of messages to process.
            model: The model to use.
            temperature: The sampling temperature.
            max_tokens: Maximum number of tokens to generate.

        Returns:
            The execution response data.

        Raises:
            ValueError: If the request is invalid.
            httpx.HTTPError: If the request fails.
        """
        if not messages:
            raise ValueError(ERROR_MESSAGES["no_messages"])

        url = self.config["api"]["create_exec_url"]
        data = {
            "input_data": json.dumps(messages),
            "model": model,
            "temperature": temperature,
        }
        if max_tokens:
            data["max_tokens"] = max_tokens

        response = await self._make_request("post", url, data=data)
        return response.json()

    async def _check_execution(self, execution_id: str) -> Dict:
        """Check the status of an execution.

        Args:
            execution_id: The execution ID to check.

        Returns:
            The execution status data.

        Raises:
            httpx.HTTPError: If the request fails.
        """
        url = f"{self.config['api']['check_exec_url']}/{execution_id}"
        response = await self._make_request("get", url)
        return response.json()

    async def _wait_for_completion(self, execution_id: str) -> Dict:
        """Wait for an execution to complete.

        Args:
            execution_id: The execution ID to wait for.

        Returns:
            The final execution data.

        Raises:
            TimeoutError: If the execution takes too long.
            ValueError: If the execution fails or is cancelled.
        """
        attempts = 0
        max_attempts = self.config["defaults"]["max_polling_attempts"]
        interval = self.config["defaults"]["polling_interval"]

        while attempts < max_attempts:
            data = await self._check_execution(execution_id)
            status = data.get("status", "").lower()

            if status == "completed":
                return data
            elif status == "failed":
                raise ValueError(
                    ERROR_MESSAGES["execution_failed"].format(
                        error=data.get("error", "Unknown error")
                    )
                )
            elif status == "cancelled":
                raise ValueError(ERROR_MESSAGES["execution_cancelled"])

            attempts += 1
            await asyncio.sleep(interval)

        raise TimeoutError(
            ERROR_MESSAGES["request_timeout"].format(attempts=max_attempts)
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
                messages, model, temperature, max_tokens=max_tokens
            )
            logger.info(f"Execution started with ID: {execution_id}")

            # Check execution result
            result = await self._wait_for_completion(execution_id)
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
        """Cleanup resources on deletion."""
        try:
            if self.http_client and not self.http_client.is_closed:
                import asyncio

                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    # Se não houver event loop, cria um novo
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                try:
                    loop.run_until_complete(self.http_client.aclose())
                except Exception as e:
                    logger.debug("Error during cleanup: %s", e)
                finally:
                    if loop.is_running():
                        loop.stop()
                    loop.close()
        except Exception as e:
            # If we can't clean up properly, just ignore it
            logger.debug("Error during cleanup: %s", e)
            pass

    async def cleanup(self):
        """Clean up resources used by the provider."""
        if self.http_client:
            try:
                await self.http_client.aclose()
                logger.info("HTTP client closed successfully")
            except Exception as e:
                logger.debug("Error during cleanup: %s", e)

    async def send_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "stackspot-ai",
        temperature: float = 0.7,
        max_tokens: int = None,
    ) -> Dict:
        """Send a completion request.

        Args:
            messages: List of messages to process.
            model: The model to use.
            temperature: The sampling temperature.
            max_tokens: Maximum number of tokens to generate.

        Returns:
            The completion response data.

        Raises:
            ValueError: If the request is invalid.
            TimeoutError: If the request times out.
            StackSpotError: If the request fails.
        """
        if not messages:
            raise ValueError(ERROR_MESSAGES["no_messages"])

        try:
            # Start execution
            execution_data = await self._start_execution(
                messages, model, temperature, max_tokens=max_tokens
            )
            logger.info("Execution started successfully")

            # Wait for completion
            result = await self._wait_for_completion(execution_data["execution_id"])
            logger.debug("Execution completed successfully")

            # Extract and validate content
            content = result.get("content")
            if not content:
                raise ValueError(ERROR_MESSAGES["no_content"])

            return {
                "id": result.get("id", f"ssp-{int(time.time())}"),
                "content": content,
                "metadata": result.get("metadata", {}),
            }

        except (ValueError, TimeoutError) as e:
            logger.error("Error during completion: %s", str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error during completion: %s", str(e))
            raise StackSpotError(f"Completion failed: {str(e)}")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()
