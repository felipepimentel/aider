import logging
import os
from typing import Dict, List, Optional

import httpx
import litellm
from litellm import ModelResponse


def configure_stackspot():
    """Configure StackSpot provider for LiteLLM"""
    logger = logging.getLogger("stackspot_config")

    # Get API key from environment
    api_key = os.getenv("STACKSPOT_API_KEY")
    if not api_key:
        raise ValueError("STACKSPOT_API_KEY environment variable not set")

    # Validate API key format
    if not api_key.startswith("sk-"):
        api_key = f"sk-{api_key}"

    logger.info("Got API key from environment")

    logger.info("Configuring StackSpot provider...")

    # Configure base settings
    litellm.set_verbose = True
    litellm.drop_params = True
    litellm.cache = None

    # Configure model map
    litellm.model_list = [
        {
            "model_name": "stackspot-ai-chat",
            "litellm_params": {
                "model": "openai/stackspot-ai-chat",
                "api_key": api_key,
                "api_base": "https://api.stackspot.com/v1",
                "api_path": "/chat/completions",
                "max_tokens": 8192,
                "headers": {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "litellm/0.1.0",
                },
            },
        },
        {
            "model_name": "stackspot-ai-code",
            "litellm_params": {
                "model": "openai/stackspot-ai-code",
                "api_key": api_key,
                "api_base": "https://api.stackspot.com/v1",
                "api_path": "/code/completions",
                "max_tokens": 8192,
                "headers": {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "litellm/0.1.0",
                },
            },
        },
        {
            "model_name": "stackspot-ai-assistant",
            "litellm_params": {
                "model": "openai/stackspot-ai-assistant",
                "api_key": api_key,
                "api_base": "https://api.stackspot.com/v1",
                "api_path": "/assistant/completions",
                "max_tokens": 8192,
                "headers": {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "litellm/0.1.0",
                },
            },
        },
    ]

    # Configure model aliases
    litellm.model_alias_map = {
        "stackspot": "openai/stackspot-ai-chat",
        "stackspot-code": "openai/stackspot-ai-code",
        "stackspot-assistant": "openai/stackspot-ai-assistant",
    }

    # Configure completion function
    original_completion = litellm.completion

    def stackspot_completion(
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = True,
        **kwargs,
    ) -> ModelResponse:
        try:
            # Check if this is a StackSpot model
            if not model.startswith("openai/stackspot-"):
                # If not a StackSpot model, use the original completion
                return original_completion(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream,
                    **kwargs,
                )

            # Find the model configuration
            model_config = next(
                (
                    m["litellm_params"]
                    for m in litellm.model_list
                    if m["model_name"] == model.replace("openai/", "")
                ),
                None,
            )

            if not model_config:
                raise ValueError(f"No configuration found for model: {model}")

            logger.info(f"Using model configuration: {model_config}")
            logger.debug(f"API key length: {len(model_config['api_key'])}")

            # Prepare request data
            request_data = {
                "model": model_config["model"].replace("openai/", ""),
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens or model_config.get("max_tokens", 8192),
                "stream": stream,
            }

            # Add any additional parameters from kwargs
            request_data.update(kwargs)

            logger.debug(f"Request data: {request_data}")
            logger.debug(f"Headers: {model_config['headers']}")

            # Make the API request
            with httpx.Client() as client:
                response = client.post(
                    f"{model_config['api_base']}{model_config['api_path']}",
                    json=request_data,
                    headers=model_config["headers"],
                    timeout=60.0,
                )

                # Log response details
                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response headers: {response.headers}")
                logger.debug(f"Response body: {response.text}")

                # Check for errors
                response.raise_for_status()

                # Parse the response
                response_data = response.json()

                # Convert to ModelResponse format
                return ModelResponse(
                    id=response_data.get("id", ""),
                    choices=response_data.get("choices", []),
                    model=model,
                    usage=response_data.get("usage", {}),
                )

        except Exception as e:
            logger.error(f"Error in StackSpot completion: {str(e)}")
            raise

    # Set custom completion function
    litellm.completion = stackspot_completion

    logger.info("StackSpot provider configured successfully")
    return True
