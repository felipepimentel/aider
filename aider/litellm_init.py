import logging
import os
from pathlib import Path

import litellm

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_litellm():
    """Initialize LiteLLM with StackSpot configuration."""
    try:
        # Set environment variables for LiteLLM
        os.environ["LITELLM_MODE"] = "PRODUCTION"
        os.environ["LITELLM_LOG_LEVEL"] = "DEBUG"

        # Configure StackSpot provider
        api_key = os.getenv("STACKSPOT_API_KEY")
        if not api_key:
            logger.error("STACKSPOT_API_KEY not found in environment")
            return False

        # Set default parameters
        litellm.api_base = "https://genai-code-buddy-api.stackspot.com/v1"
        litellm.api_key = api_key
        litellm.max_retries = 3
        litellm.retry_delay = 1.0
        litellm.stream_chunk_size = 4096
        litellm.cache_control = True
        litellm.request_timeout = 30
        litellm.drop_params = True

        # Set default headers
        litellm.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Configure error handling
        litellm.error_handling = {
            "max_retries": 3,
            "backoff_factor": 1.0,
            "retry_status_codes": [429, 500, 502, 503, 504],
        }

        # Set model aliases
        litellm.model_alias_map = {
            "stackspot": "openai/stackspot-ai-code",
            "stackspot-code": "openai/stackspot-ai-code",
            "stackspot-chat": "openai/stackspot-ai-chat",
            "stackspot-assistant": "openai/stackspot-ai-assistant",
        }

        # Load config file if exists
        config_path = Path.home() / ".aider" / ".litellm.config.yaml"
        if config_path.exists():
            try:
                litellm.config_path = str(config_path)
                logger.info(f"Loaded LiteLLM config from {config_path}")
            except Exception as e:
                logger.warning(f"Failed to load config file: {e}")

        # Enable debug mode for detailed logging
        litellm._turn_on_debug()

        logger.info("LiteLLM initialization completed successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize LiteLLM: {e}")
        return False


# Initialize LiteLLM when module is imported
init_litellm()
