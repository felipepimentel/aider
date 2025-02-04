"""Tests for StackSpot provider."""

import os
from unittest.mock import MagicMock, patch

import pytest

from aider.providers.stackspot import StackSpotProvider


@pytest.fixture
def provider():
    """Create a StackSpot provider instance."""
    with patch.dict(
        "os.environ",
        {
            "STACKSPOT_CLIENT_ID": "test-client-id",
            "STACKSPOT_SECRET_KEY": "test-secret-key",
            "STACKSPOT_REALM": "test-realm",
        },
    ):
        return StackSpotProvider()


def test_init_missing_credentials():
    """Test initialization with missing credentials."""
    with patch.dict("os.environ", clear=True):
        with pytest.raises(
            ValueError, match="STACKSPOT_CLIENT_ID.*STACKSPOT_SECRET_KEY.*required"
        ):
            StackSpotProvider()


@pytest.mark.asyncio
async def test_get_access_token(provider):
    """Test access token retrieval."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "access_token": "test-token",
            "expires_in": 3600,
        }

        token = await provider._get_access_token()
        assert token == "test-token"
        assert provider.access_token == "test-token"
        assert provider.token_expires_at > 0


@pytest.mark.asyncio
async def test_completion_with_conversation(provider):
    """Test completion with conversation ID."""
    messages = [{"role": "user", "content": "Create a Python function"}]
    conversation_id = "test-conversation-id"

    with (
        patch("httpx.AsyncClient.post") as mock_post,
        patch("httpx.AsyncClient.get") as mock_get,
    ):
        # Mock token request
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.side_effect = [
            {"access_token": "test-token", "expires_in": 3600},  # Auth response
            {"command_id": "cmd-123"},  # Create command response
            {"execution_id": "exec-123"},  # Execute command response
        ]

        # Mock status check
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "status": "completed",
            "conversation_id": conversation_id,
            "result": {
                "content": "def example():\n    pass",
                "metadata": {"type": "code"},
            },
        }

        response = await provider.completion(
            model="stackspot-ai-code",
            messages=messages,
            conversation_id=conversation_id,
        )

        assert (
            response["choices"][0]["message"]["content"] == "def example():\n    pass"
        )
        assert response["model"] == "stackspot-ai-code"
        assert provider.conversation_id == conversation_id


@pytest.mark.asyncio
async def test_completion_error_handling(provider):
    """Test error handling in completion."""
    messages = [{"role": "user", "content": "test"}]

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value.status_code = 401
        mock_post.return_value.raise_for_status.side_effect = Exception("Unauthorized")

        with pytest.raises(Exception, match="Error in StackSpot completion"):
            await provider.completion(
                model="stackspot-ai-code",
                messages=messages,
            )


def test_prepare_command(provider):
    """Test command preparation."""
    messages = [{"role": "user", "content": "test content"}]
    conversation_id = "test-conversation"
    provider.conversation_id = conversation_id

    command = provider._prepare_command(messages, "code")

    assert command.name == "create-remote-qc"
    assert command.content == "test content"
    assert command.model_type == "code"
    assert command.conversation_id == conversation_id


def test_format_response(provider):
    """Test response formatting."""
    stackspot_response = {
        "content": "test response",
        "metadata": {"type": "code"},
    }

    response = provider._format_response(stackspot_response)

    assert response["object"] == "chat.completion"
    assert response["choices"][0]["message"]["content"] == "test response"
    assert response["model"] == "stackspot-ai"
    assert "usage" in response
    assert "id" in response
    assert "created" in response


def test_init_no_api_key():
    if "STACKSPOT_API_KEY" in os.environ:
        del os.environ["STACKSPOT_API_KEY"]
    with pytest.raises(
        ValueError, match="STACKSPOT_API_KEY environment variable not set"
    ):
        StackSpotProvider()


def test_get_model_config(provider):
    config = provider.get_model_config("stackspot-ai-chat")
    assert config["model_type"] == "chat"
    assert config["max_tokens"] == 8192

    with pytest.raises(ValueError, match="Unknown model"):
        provider.get_model_config("invalid-model")


@patch("httpx.Client.post")
def test_chat_completion(mock_post, provider):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Test response"}}]
    }
    mock_post.return_value = mock_response

    messages = [{"role": "user", "content": "Hello"}]
    response = provider.chat_completion("stackspot-ai-chat", messages)

    assert response == {"choices": [{"message": {"content": "Test response"}}]}
    mock_post.assert_called_once()


def test_count_tokens(provider):
    text = "Hello world, this is a test"
    count = provider.count_tokens("stackspot-ai-chat", text)
    assert count == 7  # Simple word count for now


def test_count_message_tokens(provider):
    messages = [
        {"role": "user", "content": "Hello world"},
        {"role": "assistant", "content": "Hi there"},
    ]
    count = provider.count_message_tokens("stackspot-ai-chat", messages)
    assert count == 4  # Simple word count for now


def test_get_model_context_size(provider):
    size = provider.get_model_context_size("stackspot-ai-chat")
    assert size == 16384


def test_calculate_cost(provider):
    cost = provider.calculate_cost("stackspot-ai-chat", 100, 50)
    expected = (100 * 0.0001) + (50 * 0.0002)
    assert cost == expected
