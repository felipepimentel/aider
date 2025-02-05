import logging

logger = logging.getLogger(__name__)

class LazyLiteLLM:
    _litellm = None
    _stackspot_provider = None

    @classmethod
    def get(cls):
        if cls._litellm is None:
            logger.info("Initializing LazyLiteLLM...")
            import litellm

            from aider.providers.stackspot import StackSpotProvider

            cls._litellm = litellm
            try:
                logger.info("Attempting to create StackSpotProvider...")
                provider = StackSpotProvider()
                logger.info("StackSpotProvider created successfully")
                cls._stackspot_provider = provider
                cls._litellm.model_alias_map = {
                    "stackspot": "stackspot-ai-chat",
                    "stackspot-code": "stackspot-ai-code",
                    "stackspot-assistant": "stackspot-ai-assistant",
                }
                logger.info(f"Setting API base URL: {cls._litellm.api_base}")
                cls._litellm.api_base = "https://genai-code-buddy-api.stackspot.com"
                logger.info("Setting API key from provider")
                cls._litellm.api_key = provider.api_key
                logger.info("LiteLLM configuration completed")
            except Exception as e:
                logger.error(f"Error configuring StackSpot provider: {str(e)}", exc_info=True)
                print(f"Warning: Could not configure StackSpot provider: {e}")

        return cls._litellm

    @classmethod
    def get_stackspot(cls):
        if cls._stackspot_provider is None:
            logger.info("Initializing StackSpot provider through get_stackspot...")
            cls.get()
        return cls._stackspot_provider
