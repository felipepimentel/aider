import logging
import os
from pathlib import Path

import litellm

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def init_litellm():
    """Initialize LiteLLM with StackSpot configuration."""
    try:
        logger.info("Starting LiteLLM initialization...")

        # Set environment variables for LiteLLM
        os.environ["LITELLM_MODE"] = "PRODUCTION"
        os.environ["LITELLM_LOG_LEVEL"] = "DEBUG"
        logger.debug("Environment variables set")

        # Configure StackSpot provider
        api_key = os.getenv("STACKSPOTAI_CLIENT_KEY")
        if not api_key:
            logger.error("STACKSPOTAI_CLIENT_KEY not found in environment")
            return False

        logger.info("Configuring LiteLLM with StackSpot settings...")

        # Set default parameters
        litellm.api_base = "https://genai-code-buddy-api.stackspot.com/v1"
        litellm.api_key = api_key
        litellm.max_retries = 3
        litellm.retry_delay = 1.0
        litellm.stream_chunk_size = 4096
        litellm.cache_control = True
        litellm.request_timeout = 30
        litellm.drop_params = True
        logger.debug("Basic LiteLLM parameters configured")

        # Set default headers
        litellm.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        logger.debug("LiteLLM headers configured")

        # Configure error handling
        litellm.error_handling = {
            "max_retries": 3,
            "backoff_factor": 1.0,
            "retry_status_codes": [429, 500, 502, 503, 504],
        }
        logger.debug("Error handling configured")

        # Set model aliases
        litellm.model_alias_map = {
            "stackspot": "openai/stackspot-ai-code",
            "stackspot-code": "openai/stackspot-ai-code",
            "stackspot-chat": "openai/stackspot-ai-chat",
            "stackspot-assistant": "openai/stackspot-ai-assistant",
        }
        logger.debug("Model aliases configured")

        # Load config file from project root
        config_path = Path(__file__).parent.parent / ".litellm.config.yaml"
        if config_path.exists():
            try:
                logger.info(f"Loading config from {config_path}")
                litellm.config_path = str(config_path)
                logger.info("LiteLLM config loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load config file: {e}", exc_info=True)

        # Enable debug mode for detailed logging
        litellm._turn_on_debug()
        logger.debug("Debug mode enabled")

        logger.info("LiteLLM initialization completed successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize LiteLLM: {e}", exc_info=True)
        return False


# Initialize LiteLLM when module is imported
init_litellm()
