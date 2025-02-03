import os
from typing import Any, Dict


def configure_stackspot() -> Dict[str, Any]:
    """Configure StackSpot provider settings"""
    api_key = os.getenv("STACKSPOT_API_KEY")
    if not api_key:
        raise ValueError("STACKSPOT_API_KEY environment variable is required")

    config = {
        "stackspot-ai": {
            "api_base": "https://genai-code-buddy-api.stackspot.com",
            "api_path": "/v1/quick-commands/create-execution",
            "api_key": api_key,
            "max_tokens": 8192,
            "headers": {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        },
        "stackspot-ai-chat": {
            "api_base": "https://genai-code-buddy-api.stackspot.com",
            "api_path": "/v1/quick-commands/create-execution",
            "api_key": api_key,
            "max_tokens": 8192,
            "model_type": "chat",
            "headers": {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        },
        "stackspot-ai-code": {
            "api_base": "https://genai-code-buddy-api.stackspot.com",
            "api_path": "/v1/quick-commands/create-execution",
            "api_key": api_key,
            "max_tokens": 8192,
            "model_type": "code",
            "headers": {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        },
    }

    return config
