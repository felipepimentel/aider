import logging
import os
import sys
import traceback

import litellm


def setup_logging():
    """Setup logging to both file and console"""
    log_file = "/tmp/litellm_debug.log"

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, mode="w"),
            logging.StreamHandler(sys.stderr),
        ],
    )

    # Also write directly to the file for immediate feedback
    with open(log_file, "w") as f:
        f.write("Starting LiteLLM logging...\n")

    return logging.getLogger("litellm_init")


def init_litellm():
    """Initialize LiteLLM with the StackSpot provider configuration."""
    logger = setup_logging()
    logger.info("Logger initialized")

    try:
        logger.info("Configuring LiteLLM base settings...")
        litellm.set_verbose = True
        litellm.drop_params = True
        litellm.cache = False
        litellm.request_timeout = 60
        litellm.max_retries = 3

        logger.info("LiteLLM base configuration:")
        logger.info("- Verbose mode: True")
        logger.info("- Drop params: True")
        logger.info("- Cache enabled: False")
        logger.info("- Request timeout: 60")
        logger.info("- Max retries: 3")

        logger.info("Configuring StackSpot provider...")
        litellm.api_base = "https://genai-code-buddy-api.stackspot.com"
        litellm.api_key = os.getenv("STACKSPOT_API_KEY")

        # Configure model settings
        litellm.model_list = [
            {
                "model_name": "stackspot-ai",
                "litellm_params": {
                    "model": "stackspot-ai",
                    "api_key": litellm.api_key,
                    "api_base": litellm.api_base,
                    "api_path": "/v1/quick-commands/create-execution",
                    "max_tokens": 8192,
                    "headers": {
                        "Authorization": f"Bearer {litellm.api_key}",
                        "Content-Type": "application/json",
                    },
                },
            }
        ]

        # Create custom completion class
        class StackSpotCompletion:
            def __init__(self, api_base, api_key):
                self.api_base = api_base
                self.api_key = api_key
                self.headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }

            def completion(self, model, messages, stream=True, **kwargs):
                import json

                import requests

                url = f"{self.api_base}/v1/quick-commands/create-execution"
                data = {
                    "messages": messages,
                    "stream": stream,
                    "max_tokens": kwargs.get("max_tokens", 8192),
                    **kwargs,
                }

                try:
                    response = requests.post(
                        url, headers=self.headers, json=data, stream=stream
                    )
                    response.raise_for_status()

                    if stream:

                        def generate():
                            for line in response.iter_lines():
                                if line:
                                    try:
                                        chunk = json.loads(line.decode())
                                        yield chunk
                                    except json.JSONDecodeError:
                                        continue

                        return generate()
                    else:
                        return response.json()

                except Exception as e:
                    logger.error(f"Error during completion: {str(e)}")
                    raise

            def chat_completion(self, model, messages, stream=True, **kwargs):
                return self.completion(model, messages, stream, **kwargs)

        # Create instance of custom completion class
        stackspot = StackSpotCompletion(litellm.api_base, litellm.api_key)

        logger.info("StackSpot provider configured successfully")
        logger.info("=== LiteLLM Initialization Complete ===")
        return stackspot

    except Exception as e:
        logger.error("Error during LiteLLM initialization:")
        logger.error(str(e))
        logger.error("Traceback:")
        logger.error(traceback.format_exc())
        raise
