"""Tests for StackSpot provider."""

import asyncio
import json
import os
import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from aider.providers.stackspot import StackSpotProvider, TokenInfo
from aider.providers.stackspot_config import (
    build_url,
    get_user_agent,
    normalize_path,
    validate_url,
)
from aider.providers.stackspot_constants import ENV_CLIENT_KEY


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    with patch.dict(
        "os.environ",
        {
            "STACKSPOTAI_CLIENT_ID": "test-client-id",
            "STACKSPOTAI_CLIENT_KEY": "test-client-key",
            "STACKSPOTAI_REALM": "test-realm",
            "STACKSPOTAI_REMOTEQC_NAME": "test-remote-qc",
        },
    ):
        yield


@pytest.fixture
async def provider(mock_env):
    """Create a StackSpot provider instance with cleanup."""
    provider = StackSpotProvider()
    yield provider
    await provider.close()


@pytest.mark.asyncio
async def test_provider_cleanup(mock_env):
    """Test provider cleanup on deletion."""
    provider = StackSpotProvider()
    with patch.object(provider.http_client, "aclose") as mock_close:
        await provider.close()
        mock_close.assert_called_once()


@pytest.mark.asyncio
async def test_request_timeout(provider):
    """Test request timeout handling."""
    # Mock a timeout response
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.TimeoutException(
        "Request timed out"
    )

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        with pytest.raises(ValueError, match="Request failed after .* attempts"):
            await provider._get_access_token()


@pytest.mark.asyncio
async def test_malformed_response(provider):
    """Test handling of malformed responses."""
    # Test malformed token response
    mock_token = MagicMock()
    mock_token.json.return_value = {"invalid": "response"}
    mock_token.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", return_value=mock_token):
        with pytest.raises(ValueError, match="Invalid token response format"):
            await provider._get_access_token()

    # Test malformed execution response
    mock_exec = MagicMock()
    mock_exec.json.return_value = {"invalid": "format"}
    mock_exec.raise_for_status = MagicMock()
    mock_exec.text = '"execution-id"'

    with (
        patch.object(provider, "_get_access_token", return_value="test-token"),
        patch("httpx.AsyncClient.post", return_value=mock_exec),
        patch("httpx.AsyncClient.get", return_value=mock_exec),
    ):
        with pytest.raises(ValueError, match="No content in StackSpot response"):
            await provider.completion(messages=[{"role": "user", "content": "test"}])


@pytest.mark.asyncio
async def test_retry_mechanism(provider):
    """Test retry mechanism with different scenarios."""
    # Mock responses for retry testing
    responses = [
        MagicMock(
            raise_for_status=MagicMock(side_effect=httpx.HTTPError("Server error")),
            status_code=500,
        ),
        MagicMock(
            raise_for_status=MagicMock(side_effect=httpx.HTTPError("Rate limited")),
            status_code=429,
        ),
        MagicMock(
            json=MagicMock(
                return_value={"access_token": "test-token", "expires_in": 3600}
            ),
            raise_for_status=MagicMock(),
        ),
    ]

    with patch("httpx.AsyncClient.post", side_effect=responses):
        token = await provider._get_access_token()
        assert token == "test-token"


@pytest.mark.asyncio
async def test_execution_status_transitions(provider):
    """Test different execution status transitions."""
    provider.access_token = "test-token"

    # Mock start execution
    start_response = MagicMock()
    start_response.text = '"test-execution-id"'
    start_response.raise_for_status = MagicMock()

    # Mock status transitions
    status_responses = [
        MagicMock(
            json=MagicMock(return_value={"progress": {"status": "PROCESSING"}}),
            raise_for_status=MagicMock(),
        ),
        MagicMock(
            json=MagicMock(return_value={"progress": {"status": "PROCESSING"}}),
            raise_for_status=MagicMock(),
        ),
        MagicMock(
            json=MagicMock(
                return_value={
                    "progress": {"status": "COMPLETED"},
                    "result": {"content": "test result"},
                }
            ),
            raise_for_status=MagicMock(),
        ),
    ]

    with (
        patch("httpx.AsyncClient.post", return_value=start_response),
        patch("httpx.AsyncClient.get", side_effect=status_responses),
    ):
        result = await provider.completion(
            messages=[{"role": "user", "content": "test"}]
        )
        assert result["choices"][0]["message"]["content"] == "test result"


@pytest.mark.asyncio
async def test_execution_failure_states(provider):
    """Test handling of execution failure states."""
    provider.access_token = "test-token"

    # Mock start execution
    start_response = MagicMock()
    start_response.text = '"test-execution-id"'
    start_response.raise_for_status = MagicMock()

    # Test FAILED status
    failed_response = MagicMock()
    failed_response.json.return_value = {
        "progress": {"status": "FAILED", "error": "Execution failed"}
    }
    failed_response.raise_for_status = MagicMock()

    with (
        patch("httpx.AsyncClient.post", return_value=start_response),
        patch("httpx.AsyncClient.get", return_value=failed_response),
    ):
        with pytest.raises(ValueError, match="Execution failed: Execution failed"):
            await provider.completion(messages=[{"role": "user", "content": "test"}])

    # Test CANCELLED status
    cancelled_response = MagicMock()
    cancelled_response.json.return_value = {"progress": {"status": "CANCELLED"}}
    cancelled_response.raise_for_status = MagicMock()

    with (
        patch("httpx.AsyncClient.post", return_value=start_response),
        patch("httpx.AsyncClient.get", return_value=cancelled_response),
    ):
        with pytest.raises(ValueError, match="Execution was cancelled"):
            await provider.completion(messages=[{"role": "user", "content": "test"}])


@pytest.mark.asyncio
async def test_network_errors(provider):
    """Test handling of various network errors."""
    # Test connection error
    with patch(
        "httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection failed")
    ):
        with pytest.raises(ValueError, match="HTTP error occurred"):
            await provider._get_access_token()

    # Test DNS failure
    with patch(
        "httpx.AsyncClient.post", side_effect=httpx.ConnectError("DNS lookup failed")
    ):
        with pytest.raises(ValueError, match="HTTP error occurred"):
            await provider._get_access_token()

    # Test SSL error
    with patch(
        "httpx.AsyncClient.post",
        side_effect=httpx.ConnectError("SSL verification failed"),
    ):
        with pytest.raises(ValueError, match="HTTP error occurred"):
            await provider._get_access_token()


@pytest.mark.asyncio
async def test_input_validation(provider):
    """Test input validation for completion requests."""
    provider.access_token = "test-token"

    # Test empty messages
    with pytest.raises(ValueError, match="No messages provided"):
        await provider.completion(messages=[])

    # Test invalid message format
    with pytest.raises(ValueError, match="Message content is empty or invalid"):
        await provider.completion(messages=[{"role": "user"}])

    # Test empty content
    with pytest.raises(ValueError, match="Message content is empty or invalid"):
        await provider.completion(messages=[{"role": "user", "content": ""}])


def test_token_info():
    """Test TokenInfo class functionality."""
    # Test initialization
    token = TokenInfo(token="test-token", expires_in=3600)
    assert token.token == "test-token"
    assert token.expires_in == 3600
    assert token.refresh_threshold == 0.9

    # Test not expired token
    assert not token.is_expired
    assert not token.needs_refresh
    assert token.remaining_time > 0

    # Test token near expiration
    with patch("time.time") as mock_time:
        mock_time.return_value = token.created_at + (token.expires_in * 0.95)
        assert not token.is_expired
        assert token.needs_refresh
        assert token.remaining_time > 0

    # Test expired token
    with patch("time.time") as mock_time:
        mock_time.return_value = token.created_at + token.expires_in + 1
        assert token.is_expired
        assert token.needs_refresh
        assert token.remaining_time == 0


@pytest.mark.asyncio
async def test_token_refresh(provider):
    """Test token refresh mechanism."""
    # Mock initial token response
    initial_response = MagicMock()
    initial_response.json.return_value = {
        "access_token": "test-token-1",
        "expires_in": 3600,
    }
    initial_response.raise_for_status = MagicMock()

    # Mock refresh token response
    refresh_response = MagicMock()
    refresh_response.json.return_value = {
        "access_token": "test-token-2",
        "expires_in": 3600,
    }
    refresh_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post") as mock_post:
        # First call gets initial token
        mock_post.return_value = initial_response
        token1 = await provider._get_access_token()
        assert token1 == "test-token-1"

        # Simulate token near expiration
        provider.token_info.created_at -= (
            provider.token_info.expires_in * provider.token_info.refresh_threshold
        )

        # Second call should refresh token
        mock_post.return_value = refresh_response
        token2 = await provider._get_access_token()
        assert token2 == "test-token-2"
        assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_token_refresh_failure(provider):
    """Test token refresh failure handling."""
    # Mock initial token response
    initial_response = MagicMock()
    initial_response.json.return_value = {
        "access_token": "test-token-1",
        "expires_in": 3600,
    }
    initial_response.raise_for_status = MagicMock()

    # Mock refresh token failure
    error_response = MagicMock()
    error_response.raise_for_status.side_effect = httpx.HTTPError("Refresh failed")
    error_response.status_code = 500

    with patch("httpx.AsyncClient.post") as mock_post:
        # First call gets initial token
        mock_post.return_value = initial_response
        token1 = await provider._get_access_token()
        assert token1 == "test-token-1"

        # Simulate token near expiration
        provider.token_info.created_at -= (
            provider.token_info.expires_in * provider.token_info.refresh_threshold
        )

        # Second call should fail to refresh
        mock_post.return_value = error_response
        with pytest.raises(ValueError, match="Failed to obtain access token"):
            await provider._get_access_token()

        # Token info should be cleared
        assert provider.token_info is None


@pytest.mark.asyncio
async def test_concurrent_token_refresh(provider):
    """Test concurrent token refresh handling."""
    # Mock token response
    response = MagicMock()
    response.json.return_value = {
        "access_token": "test-token",
        "expires_in": 3600,
    }
    response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", return_value=response) as mock_post:
        # Simulate concurrent requests
        tasks = [provider._get_access_token() for _ in range(5)]
        tokens = await asyncio.gather(*tasks)

        # All requests should get the same token
        assert all(token == "test-token" for token in tokens)
        # Token should only be fetched once
        assert mock_post.call_count == 1


@pytest.mark.asyncio
async def test_invalid_token_response(provider):
    """Test handling of invalid token response."""
    # Mock invalid token response
    response = MagicMock()
    response.json.return_value = {"invalid": "response"}
    response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", return_value=response):
        with pytest.raises(ValueError, match="Invalid token response format"):
            await provider._get_access_token()


def test_init_missing_credentials():
    """Test initialization with missing credentials."""
    with patch.dict("os.environ", clear=True):
        with pytest.raises(
            ValueError,
            match="STACKSPOTAI_CLIENT_ID and STACKSPOTAI_CLIENT_KEY.*required",
        ):
            StackSpotProvider()


def test_init_missing_remote_qc():
    """Test initialization with missing remote QC name."""
    with patch.dict(
        "os.environ",
        {
            "STACKSPOTAI_CLIENT_ID": "test-client-id",
            "STACKSPOTAI_CLIENT_KEY": "test-client-key",
        },
    ):
        with pytest.raises(ValueError, match="STACKSPOTAI_REMOTEQC_NAME.*required"):
            StackSpotProvider()


@pytest.mark.asyncio
async def test_get_access_token(provider):
    """Test getting access token."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "access_token": "test-token",
        "expires_in": 3600,
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        token = await provider._get_access_token()
        assert token == "test-token"
        assert provider.access_token == "test-token"
        assert provider.token_expires_at > time.time()

        # Verify form data format
        assert (
            mock_post.call_args[1]["headers"]["Content-Type"]
            == "application/x-www-form-urlencoded"
        )
        assert "grant_type=client_credentials" in mock_post.call_args[1]["data"]


@pytest.mark.asyncio
async def test_get_access_token_error(provider):
    """Test error handling in getting access token."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPError("Test error")
    mock_response.status_code = 401

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        with pytest.raises(
            ValueError, match="Invalid credentials or unauthorized access"
        ):
            await provider._get_access_token()


@pytest.mark.asyncio
async def test_start_execution_payload(provider):
    """Test start execution payload format."""
    provider.access_token = "test-token"
    mock_response = MagicMock()
    mock_response.text = '"test-execution-id"'
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        execution_id = await provider._start_execution(
            "test prompt",
            model="stackspot-ai",
            temperature=0.8,
        )

        # Verify execution ID
        assert execution_id == "test-execution-id"

        # Verify request payload
        sent_data = json.loads(mock_post.call_args[1]["data"])
        assert sent_data["input_data"] == "test prompt"
        assert sent_data["model"] == "stackspot-ai"
        assert sent_data["temperature"] == 0.8
        assert "max_tokens" not in sent_data  # Should be excluded when None


@pytest.mark.asyncio
async def test_start_execution_with_conversation(provider):
    """Test starting execution with conversation ID."""
    provider.access_token = "test-token"
    provider.conversation_id = "test-conv-id"
    mock_response = MagicMock()
    mock_response.text = '"test-execution-id"'
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        execution_id = await provider._start_execution("test prompt")
        assert execution_id == "test-execution-id"
        assert "conversation_id=test-conv-id" in mock_post.call_args[0][0]

        # Verify request payload includes conversation_id
        sent_data = json.loads(mock_post.call_args[1]["data"])
        assert sent_data["conversation_id"] == "test-conv-id"


@pytest.mark.asyncio
async def test_check_execution_timeout(provider):
    """Test execution check timeout."""
    provider.access_token = "test-token"
    mock_response = MagicMock()
    mock_response.json.return_value = {"progress": {"status": "PROCESSING"}}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        with pytest.raises(TimeoutError, match="Execution check timed out"):
            await provider._check_execution("test-execution-id")


@pytest.mark.asyncio
async def test_check_execution_with_retries(provider):
    """Test checking execution status with retries."""
    provider.access_token = "test-token"
    processing_response = MagicMock()
    processing_response.json.return_value = {"progress": {"status": "PROCESSING"}}
    processing_response.raise_for_status = MagicMock()

    completed_response = MagicMock()
    completed_response.json.return_value = {
        "progress": {"status": "COMPLETED"},
        "result": {"content": "test result"},
    }
    completed_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [processing_response, completed_response]
        result = await provider._check_execution("test-execution-id")
        assert result["progress"]["status"] == "COMPLETED"
        assert result["result"]["content"] == "test result"
        assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_completion_success(provider):
    """Test successful completion flow."""
    provider.access_token = "test-token"
    messages = [{"role": "user", "content": "test message"}]

    # Mock start execution
    mock_start = MagicMock()
    mock_start.text = '"test-execution-id"'
    mock_start.raise_for_status = MagicMock()

    # Mock check execution
    mock_check = MagicMock()
    mock_check.json.return_value = {
        "progress": {"status": "COMPLETED"},
        "result": {"content": "test result"},
    }
    mock_check.raise_for_status = MagicMock()

    with (
        patch("httpx.AsyncClient.post", return_value=mock_start) as mock_post,
        patch("httpx.AsyncClient.get", return_value=mock_check),
    ):
        response = await provider.completion(
            messages=messages,
            model="stackspot-ai",
            temperature=0.8,
        )

        # Verify completion response format
        assert response["choices"][0]["message"]["content"] == "test result"
        assert response["model"] == "stackspot-ai"
        assert "usage" in response
        assert "id" in response
        assert "created" in response

        # Verify request payload
        sent_data = json.loads(mock_post.call_args[1]["data"])
        assert sent_data["input_data"] == "test message"
        assert sent_data["model"] == "stackspot-ai"
        assert sent_data["temperature"] == 0.8


@pytest.mark.asyncio
async def test_completion_with_conversation(provider):
    """Test completion with conversation ID."""
    provider.access_token = "test-token"
    messages = [{"role": "user", "content": "test message"}]

    # Mock start execution
    mock_start = MagicMock()
    mock_start.text = '"test-execution-id"'
    mock_start.raise_for_status = MagicMock()

    # Mock check execution
    mock_check = MagicMock()
    mock_check.json.return_value = {
        "progress": {"status": "COMPLETED"},
        "result": {"content": "test result"},
    }
    mock_check.raise_for_status = MagicMock()

    with (
        patch("httpx.AsyncClient.post", return_value=mock_start) as mock_post,
        patch("httpx.AsyncClient.get", return_value=mock_check),
    ):
        response = await provider.completion(
            messages=messages,
            conversation_id="test-conv-id",
        )
        assert response["choices"][0]["message"]["content"] == "test result"
        assert "conversation_id=test-conv-id" in mock_post.call_args[0][0]

        # Verify conversation_id in payload
        sent_data = json.loads(mock_post.call_args[1]["data"])
        assert sent_data["conversation_id"] == "test-conv-id"


def test_format_response(provider):
    """Test response formatting."""
    stackspot_response = {
        "progress": {"status": "COMPLETED"},
        "result": {"content": "test result"},
        "metadata": {"type": "code"},
    }

    response = provider._format_response(stackspot_response)

    assert response["object"] == "chat.completion"
    assert response["choices"][0]["message"]["content"] == "test result"
    assert response["model"] == "stackspot-ai"
    assert "usage" in response
    assert "id" in response
    assert "created" in response


@pytest.mark.asyncio
async def test_error_handling(provider):
    """Test error handling in various scenarios."""
    provider.access_token = "test-token"
    messages = [{"role": "user", "content": "test message"}]

    # Test 400 Bad Request
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPError("Bad request")
    mock_response.status_code = 400

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        with pytest.raises(ValueError, match="Bad request"):
            await provider.completion(messages=messages)

    # Test 401 Unauthorized
    mock_response.status_code = 401
    with patch("httpx.AsyncClient.post", return_value=mock_response):
        with pytest.raises(ValueError, match="Unauthorized"):
            await provider.completion(messages=messages)

    # Test 429 Too Many Requests
    mock_response.status_code = 429
    with patch("httpx.AsyncClient.post", return_value=mock_response):
        with pytest.raises(ValueError, match="Too many requests"):
            await provider.completion(messages=messages)


def test_validate_url():
    """Test URL validation."""
    # Valid URLs
    assert validate_url("https://example.com") == "https://example.com"
    assert validate_url("http://localhost:8080") == "http://localhost:8080"
    assert (
        validate_url("https://api.example.com/path") == "https://api.example.com/path"
    )

    # Invalid URLs
    with pytest.raises(ValueError, match="Invalid URL format"):
        validate_url("not-a-url")
    with pytest.raises(ValueError, match="Invalid URL format"):
        validate_url("http://")
    with pytest.raises(ValueError, match="Invalid URL format"):
        validate_url("://example.com")


def test_normalize_path():
    """Test path normalization."""
    # Basic normalization
    assert normalize_path("/path/to/resource/") == "path/to/resource"
    assert normalize_path("path/to/resource") == "path/to/resource"
    assert normalize_path("  /path/to/resource/  ") == "path/to/resource"

    # URL encoding
    assert normalize_path("/path with spaces/") == "path%20with%20spaces"
    assert normalize_path("/special&chars?") == "special%26chars%3F"
    assert normalize_path("/unicode/🚀") == "unicode/%F0%9F%9A%80"


def test_build_url():
    """Test URL building."""
    # Basic URL building
    assert (
        build_url("https://api.example.com", "v1/resource")
        == "https://api.example.com/v1/resource"
    )

    # URL with trailing slash in base
    assert (
        build_url("https://api.example.com/", "v1/resource")
        == "https://api.example.com/v1/resource"
    )

    # URL with query parameters
    assert (
        build_url(
            "https://api.example.com",
            "v1/resource",
            {"param1": "value1", "param2": "value2"},
        )
        == "https://api.example.com/v1/resource?param1=value1&param2=value2"
    )

    # URL with special characters
    assert (
        build_url(
            "https://api.example.com",
            "v1/resource with spaces",
            {"param&special": "value with spaces"},
        )
        == "https://api.example.com/v1/resource%20with%20spaces?param%26special=value%20with%20spaces"
    )


def test_get_user_agent():
    """Test User-Agent string generation."""
    default_ua = "aider/1.0 (+https://aider.chat)"

    # Default User-Agent
    with patch.dict("os.environ", {}):
        assert get_user_agent() == default_ua

    # Custom User-Agent
    custom_ua = "CustomApp/2.0"
    with patch.dict("os.environ", {"STACKSPOTAI_USER_AGENT": custom_ua}):
        assert get_user_agent() == f"{custom_ua} {default_ua}"


def test_config_with_custom_urls(mock_env):
    """Test configuration with custom URLs."""
    custom_env = {
        "STACKSPOTAI_AUTH_URL": "https://custom-auth.example.com",
        "STACKSPOTAI_API_URL": "https://custom-api.example.com",
        "STACKSPOTAI_USER_AGENT": "CustomApp/2.0",
    }

    with patch.dict("os.environ", {**os.environ, **custom_env}):
        provider = StackSpotProvider()
        config = provider.config

        # Check if URLs are properly constructed
        assert config["auth"]["auth_url"].startswith("https://custom-auth.example.com/")
        assert config["api"]["create_exec_url"].startswith(
            "https://custom-api.example.com/"
        )
        assert config["api"]["check_exec_url"].startswith(
            "https://custom-api.example.com/"
        )

        # Check if User-Agent is properly set
        assert "CustomApp/2.0" in config["api"]["headers"]["User-Agent"]


def test_config_with_invalid_urls():
    """Test configuration with invalid URLs."""
    invalid_env = {
        "STACKSPOTAI_CLIENT_ID": "test-client-id",
        "STACKSPOTAI_CLIENT_KEY": "test-client-key",
        "STACKSPOTAI_REALM": "test-realm",
        "STACKSPOTAI_REMOTEQC_NAME": "test-remote-qc",
        "STACKSPOTAI_AUTH_URL": "invalid-url",
    }

    with patch.dict("os.environ", invalid_env):
        with pytest.raises(ValueError, match="Invalid URL format"):
            StackSpotProvider()


def test_init_with_api_key():
    """Test initialization with API key parameter."""
    api_key = "test-api-key"
    with patch.dict(
        "os.environ",
        {
            "STACKSPOTAI_CLIENT_ID": "test-client-id",
            "STACKSPOTAI_REMOTEQC_NAME": "test-remote-qc",
        },
    ):
        provider = StackSpotProvider(api_key=api_key)
        assert os.environ[ENV_CLIENT_KEY] == api_key


def test_init_with_env_priority():
    """Test that environment variable takes priority over api_key."""
    env_key = "env-api-key"
    param_key = "param-api-key"
    with patch.dict(
        "os.environ",
        {
            "STACKSPOTAI_CLIENT_ID": "test-client-id",
            "STACKSPOTAI_CLIENT_KEY": env_key,
            "STACKSPOTAI_REMOTEQC_NAME": "test-remote-qc",
        },
    ):
        provider = StackSpotProvider(api_key=param_key)
        assert os.environ[ENV_CLIENT_KEY] == param_key
