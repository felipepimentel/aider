import os
from typing import Any, Dict


def configure_stackspot() -> Dict[str, Any]:
    """Configure StackSpot provider settings"""
    # Get API key from environment or configuration
    api_key = os.getenv("STACKSPOT_API_KEY")
    if not api_key:
        raise ValueError(
            "STACKSPOT_API_KEY environment variable not set. "
            "Please set it with your StackSpot API key."
        )

    config = {
        "api": {
            "base_url": "https://genai-code-buddy-api.stackspot.com",
            "api_key": api_key,
            "headers": {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            "endpoints": {
                "chat": "/v1/chat/completions",
                "code": "/v1/code/completions",
                "assistant": "/v1/assistant/completions",
            },
        },
        "models": {
            "stackspot-ai": {
                "max_tokens": 8192,
                "max_input_tokens": 16384,
                "max_output_tokens": 8192,
                "model_type": "code",
                "streaming": True,
                "temperature": 0.7,
            },
            "stackspot-ai-chat": {
                "max_tokens": 8192,
                "max_input_tokens": 16384,
                "max_output_tokens": 8192,
                "model_type": "chat",
                "streaming": True,
                "temperature": 0.7,
            },
            "stackspot-ai-code": {
                "max_tokens": 8192,
                "max_input_tokens": 16384,
                "max_output_tokens": 8192,
                "model_type": "code",
                "streaming": True,
                "temperature": 0.7,
            },
        },
        "defaults": {
            "timeout": 60,
            "max_retries": 3,
            "retry_delay": 1.0,
            "cache_ttl": 3600,
        },
    }

    return config
