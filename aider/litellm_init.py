import logging
import os
from pathlib import Path

import litellm

logger = logging.getLogger(__name__)


def init_litellm():
    """Initialize LiteLLM with StackSpot configuration."""
    try:
        logger.info("Iniciando inicialização do LiteLLM...")

        # Set environment variables for LiteLLM
        os.environ["LITELLM_MODE"] = "PRODUCTION"
        logger.debug("Variáveis de ambiente configuradas")

        # Configure StackSpot provider
        api_key = os.getenv("STACKSPOTAI_CLIENT_KEY")
        if not api_key:
            logger.error(
                "STACKSPOTAI_CLIENT_KEY não encontrada nas variáveis de ambiente"
            )
            return False

        logger.info("Configurando LiteLLM com configurações StackSpot...")

        # Set default parameters
        litellm.api_base = "https://genai-code-buddy-api.stackspot.com/v1"
        litellm.api_key = api_key
        litellm.max_retries = 3
        litellm.retry_delay = 1.0
        litellm.stream_chunk_size = 4096
        litellm.cache_control = True
        litellm.request_timeout = 30
        litellm.drop_params = True
        logger.debug("Parâmetros básicos do LiteLLM configurados")

        # Set default headers
        litellm.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        logger.debug("Headers do LiteLLM configurados")

        # Configure error handling
        litellm.error_handling = {
            "max_retries": 3,
            "backoff_factor": 1.0,
            "retry_status_codes": [429, 500, 502, 503, 504],
        }
        logger.debug("Tratamento de erros configurado")

        # Set model aliases
        litellm.model_alias_map = {
            "stackspot": "openai/stackspot-ai-code",
            "stackspot-code": "openai/stackspot-ai-code",
            "stackspot-chat": "openai/stackspot-ai-chat",
            "stackspot-assistant": "openai/stackspot-ai-assistant",
        }
        logger.debug("Aliases de modelo configurados")

        # Load config file from project root
        config_path = Path(__file__).parent.parent / ".litellm.config.yaml"
        if config_path.exists():
            try:
                logger.info(f"Carregando configuração de {config_path}")
                litellm.config_path = str(config_path)
                logger.info("Configuração do LiteLLM carregada com sucesso")
            except Exception as e:
                logger.error(
                    f"Falha ao carregar arquivo de configuração: {e}", exc_info=True
                )

        # Enable debug mode for detailed logging
        litellm._turn_on_debug()
        logger.debug("Modo debug habilitado")

        logger.info("Inicialização do LiteLLM concluída com sucesso")
        return True

    except Exception as e:
        logger.error(f"Falha ao inicializar LiteLLM: {e}", exc_info=True)
        return False


# Initialize LiteLLM when module is imported
init_litellm()
