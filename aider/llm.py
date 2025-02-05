import logging
import os
import sys
import warnings

from aider.litellm_init import init_litellm

logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

AIDER_SITE_URL = "https://aider.chat"
AIDER_APP_NAME = "Aider"

os.environ["OR_SITE_URL"] = AIDER_SITE_URL
os.environ["OR_APP_NAME"] = AIDER_APP_NAME
os.environ["LITELLM_MODE"] = "PRODUCTION"

logger.debug("=== Debug: Starting LLM Module ===")
logger.debug(f"Current working directory: {os.getcwd()}")
logger.debug(f"Python path: {sys.path}")
logger.debug("Environment variables:")
logger.debug(
    f"- STACKSPOTAI_CLIENT_KEY present: {bool(os.getenv('STACKSPOTAI_CLIENT_KEY'))}"
)
logger.debug(f"- LITELLM_MODE: {os.getenv('LITELLM_MODE')}")

try:
    logger.info("Initializing LiteLLM...")
    init_litellm()
    import litellm

    logger.info("LiteLLM initialized successfully!")
except Exception as e:
    logger.error("\nError initializing LiteLLM:")
    logger.error(str(e))
    logger.error("\nTraceback:", exc_info=True)
    raise

logger.debug("=== Debug: LLM Module Loaded ===\n")


def completion(prompt, model="stackspot-ai", stream=True, **kwargs):
    """Send a completion request to the LLM."""
    try:
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=stream,
            **kwargs,
        )
        return response
    except Exception as e:
        logger.error(f"Error during completion: {str(e)}")
        raise


def chat_completion(messages, model="stackspot-ai", stream=True, **kwargs):
    """Send a chat completion request to the LLM."""
    try:
        response = litellm.chat_completion(
            model=model, messages=messages, stream=stream, **kwargs
        )
        return response
    except Exception as e:
        handle_chat_completion_error(e)
        return None


def handle_chat_completion_error(e):
    """Handle chat completion error."""
    logger.error("Error during chat completion: %s", str(e))
    return None


__all__ = ["litellm", "completion", "chat_completion"]
