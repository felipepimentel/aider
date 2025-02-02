import os
import pytest
from unittest.mock import MagicMock, patch

from aider.providers.stackspot import StackSpotProvider


@pytest.fixture
def provider():
    os.environ["STACKSPOT_API_KEY"] = "test-key"
    return StackSpotProvider()


def test_init_no_api_key():
    if "STACKSPOT_API_KEY" in os.environ:
        del os.environ["STACKSPOT_API_KEY"]
    with pytest.raises(ValueError, match="STACKSPOT_API_KEY environment variable not set"):
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
    mock_response.json.return_value = {"choices": [{"message": {"content": "Test response"}}]}
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
        {"role": "assistant", "content": "Hi there"}
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