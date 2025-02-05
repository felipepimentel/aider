"""Constants for StackSpot provider."""

from typing import Dict, Final

# Default URLs
DEFAULT_AUTH_URL: Final[str] = "https://auth.stackspot.com"
DEFAULT_API_URL: Final[str] = "https://genai-code-buddy-api.stackspot.com"

# Environment variable names
ENV_CLIENT_ID: Final[str] = "STACKSPOTAI_CLIENT_ID"
ENV_CLIENT_KEY: Final[str] = "STACKSPOTAI_CLIENT_KEY"
ENV_REALM: Final[str] = "STACKSPOTAI_REALM"
ENV_REMOTE_QC_NAME: Final[str] = "STACKSPOTAI_REMOTEQC_NAME"
ENV_AUTH_URL: Final[str] = "STACKSPOTAI_AUTH_URL"
ENV_API_URL: Final[str] = "STACKSPOTAI_API_URL"
ENV_USER_AGENT: Final[str] = "STACKSPOTAI_USER_AGENT"

# Default values
DEFAULT_REALM: Final[str] = "stackspot"
DEFAULT_USER_AGENT: Final[str] = "aider/1.0 (+https://aider.chat)"

# API endpoints
API_PATH_CREATE_EXECUTION: Final[str] = "v1/quick-commands/create-execution"
API_PATH_CHECK_EXECUTION: Final[str] = "v1/quick-commands/execution"
API_PATH_TOKEN: Final[str] = "realms/{realm}/protocol/openid-connect/token"

# Content types
CONTENT_TYPE_MAP: Final[Dict[str, str]] = {
    "json": "application/json",
    "form": "application/x-www-form-urlencoded",
}

# Default configuration
DEFAULT_CONFIG: Final[Dict[str, Dict]] = {
    "models": {
        "stackspot-ai": {
            "max_tokens": 8192,
            "max_input_tokens": 16384,
            "max_output_tokens": 8192,
            "model_type": "code",
            "streaming": True,
            "temperature": 0.7,
        },
        "stackspot-ai-chat": {
            "max_tokens": 8192,
            "max_input_tokens": 16384,
            "max_output_tokens": 8192,
            "model_type": "chat",
            "streaming": True,
            "temperature": 0.7,
        },
        "stackspot-ai-code": {
            "max_tokens": 8192,
            "max_input_tokens": 16384,
            "max_output_tokens": 8192,
            "model_type": "code",
            "streaming": True,
            "temperature": 0.7,
        },
    },
    "defaults": {
        "timeout": 60,
        "max_retries": 3,
        "retry_delay": 1.0,
        "cache_ttl": 3600,
        "polling_interval": 2,
        "max_polling_attempts": 30,
    },
}

# HTTP headers
DEFAULT_HEADERS: Final[Dict[str, str]] = {
    "Content-Type": "application/json",
    "Accept": "*/*",
}

# Token configuration
TOKEN_REFRESH_THRESHOLD: Final[float] = 0.9  # Refresh when 90% of lifetime has passed

# Error messages
ERROR_MESSAGES: Final[Dict[str, str]] = {
    "missing_credentials": (
        "STACKSPOTAI_CLIENT_ID and STACKSPOTAI_CLIENT_KEY environment variables are required. "
        "Please set them with your StackSpot credentials."
    ),
    "missing_remote_qc": (
        "STACKSPOTAI_REMOTEQC_NAME environment variable is required. "
        "Please set it with your StackSpot Remote Quick Command name."
    ),
    "invalid_url": "Invalid URL format: {url}",
    "invalid_token_response": "Invalid token response format",
    "no_messages": "No messages provided for completion",
    "empty_content": "Message content is empty or invalid",
    "request_timeout": "Request timed out after {attempts} attempts",
    "execution_failed": "Execution failed: {error}",
    "execution_cancelled": "Execution was cancelled",
    "no_content": "No content in StackSpot response",
    "invalid_response": "Invalid response format from StackSpot API",
}
