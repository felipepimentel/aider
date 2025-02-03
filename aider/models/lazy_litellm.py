class LazyLiteLLM:
    _litellm = None
    _stackspot_provider = None

    @classmethod
    def get(cls):
        if cls._litellm is None:
            import litellm

            from aider.providers.stackspot import StackSpotProvider

            cls._litellm = litellm
            try:
                provider = StackSpotProvider()
                cls._stackspot_provider = provider
                cls._litellm.model_alias_map = {
                    "stackspot": "stackspot-ai-chat",
                    "stackspot-code": "stackspot-ai-code",
                    "stackspot-assistant": "stackspot-ai-assistant",
                }
                cls._litellm.api_base = "https://genai-code-buddy-api.stackspot.com"
                cls._litellm.api_key = provider.api_key
            except Exception as e:
                print(f"Warning: Could not configure StackSpot provider: {e}")

        return cls._litellm

    @classmethod
    def get_stackspot(cls):
        if cls._stackspot_provider is None:
            cls.get()
        return cls._stackspot_provider
