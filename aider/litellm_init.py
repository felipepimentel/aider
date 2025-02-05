import logging
import os

import litellm

logger = logging.getLogger(__name__)


def init_litellm():
    """Initialize LiteLLM with StackSpot configuration."""
    try:
        # Set production mode
        os.environ["LITELLM_MODE"] = "PRODUCTION"

        # Get credentials from environment
        client_key = os.getenv("STACKSPOTAI_CLIENT_KEY")
        if not client_key:
            logger.warning("STACKSPOTAI_CLIENT_KEY not found in environment")
            return

        # Configure LiteLLM
        litellm.api_key = client_key
        litellm.api_base = os.getenv(
            "STACKSPOTAI_API_URL", "https://genai-code-buddy-api.stackspot.com"
        )
        litellm.headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "User-Agent": "aider/1.0 (+https://aider.chat)",
        }

        # Load configuration from environment variables
        if os.getenv("LITELLM_CONFIG_PATH"):
            config_path = os.getenv("LITELLM_CONFIG_PATH")
        else:
            config_path = os.path.join(
                os.path.dirname(__file__), "..", ".litellm.config.yaml"
            )

        if os.path.exists(config_path):
            try:
                with open(config_path) as f:
                    import yaml

                    config = yaml.safe_load(f)

                # Apply configuration
                if "litellm_settings" in config:
                    settings = config["litellm_settings"]
                    for key, value in settings.items():
                        setattr(litellm, key, value)

                if "providers" in config:
                    litellm.providers = config["providers"]

                logger.info("Loaded LiteLLM configuration from %s", config_path)
            except Exception as e:
                logger.error("Failed to load config from %s: %s", config_path, str(e))

        # Enable debug mode in development
        if os.getenv("AIDER_DEV_MODE"):
            litellm.set_verbose = True
            logger.info("LiteLLM debug mode enabled")

        logger.info("LiteLLM initialized successfully")

    except Exception as e:
        logger.error("Failed to initialize LiteLLM: %s", str(e), exc_info=True)
        raise


# Initialize LiteLLM when module is imported
init_litellm()
