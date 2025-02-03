"""Tests for StackSpot provider."""

import pytest
from unittest.mock import patch

from aider.providers.stackspot import CommandType, StackSpotProvider


@pytest.fixture
def provider():
    """Create a StackSpot provider instance."""
    with patch.dict("os.environ", {"STACKSPOT_API_KEY": "test-key"}):
        return StackSpotProvider()


def test_init_missing_api_key():
    """Test initialization with missing API key."""
    with patch.dict("os.environ", clear=True):
        with pytest.raises(ValueError, match="STACKSPOT_API_KEY.*not set"):
            StackSpotProvider()


@pytest.mark.asyncio
async def test_completion_success(provider):
    """Test successful completion request."""
    messages = [{"role": "user", "content": "Create a Python function"}]

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value.json.return_value = {
            "content": "def example():\n    pass",
            "metadata": {"type": "code"}
        }
        mock_post.return_value.status_code = 200

        response = await provider.completion(
            model="stackspot-ai-code",
            messages=messages,
            temperature=0.7,
        )

        assert response["choices"][0]["message"]["content"] == "def example():\n    pass"
        assert response["model"] == "stackspot-ai-code"
        assert "usage" in response


@pytest.mark.asyncio
async def test_completion_chat_model(provider):
    """Test completion with chat model."""
    messages = [{"role": "user", "content": "Hello"}]

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value.json.return_value = {
            "content": "Hi! How can I help you?",
            "metadata": {"type": "chat"}
        }
        mock_post.return_value.status_code = 200

        response = await provider.completion(
            model="stackspot-ai-chat",
            messages=messages,
        )

        assert response["model"] == "stackspot-ai-chat"
        assert response["choices"][0]["message"]["content"] == "Hi! How can I help you?"


@pytest.mark.asyncio
async def test_completion_api_error(provider):
    """Test completion with API error."""
    messages = [{"role": "user", "content": "test"}]

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value.status_code = 400
        mock_post.return_value.raise_for_status.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="Error in StackSpot completion"):
            await provider.completion(
                model="stackspot-ai-code",
                messages=messages,
            )


def test_prepare_command(provider):
    """Test command preparation."""
    messages = [{"role": "user", "content": "test content"}]
    command = provider._prepare_command(messages, CommandType.CODE)

    assert command.name == "create-remote-qc"
    assert command.fields["content"] == "test content"
    assert command.fields["type"] == "code"
    assert "name" in command.fields
    assert "description" in command.fields


def test_format_response(provider):
    """Test response formatting."""
    stackspot_response = {
        "content": "test response",
        "metadata": {"type": "code"}
    }

    response = provider._format_response(stackspot_response, CommandType.CODE)

    assert response["object"] == "chat.completion"
    assert response["choices"][0]["message"]["content"] == "test response"
    assert response["model"] == "stackspot-ai-code"
    assert "usage" in response
    assert "id" in response
    assert "created" in response
