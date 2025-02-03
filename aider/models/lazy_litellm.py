class LazyLiteLLM:
    _litellm = None
    _stackspot_provider = None

    @classmethod
    def get(cls):
        if cls._litellm is None:
            import litellm

            cls._litellm = litellm

            try:
                from aider.providers.stackspot_config import configure_stackspot

                configure_stackspot()
            except ImportError:
                pass

        return cls._litellm
