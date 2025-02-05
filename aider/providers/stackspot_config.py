"""Configuration module for StackSpot provider."""

import logging
import os
from typing import Any, Dict
from urllib.parse import quote, urlparse

from .stackspot_constants import (
    API_PATH_CHECK_EXECUTION,
    API_PATH_CREATE_EXECUTION,
    API_PATH_TOKEN,
    DEFAULT_API_URL,
    DEFAULT_AUTH_URL,
    DEFAULT_CONFIG,
    DEFAULT_HEADERS,
    DEFAULT_REALM,
    DEFAULT_USER_AGENT,
    ENV_API_URL,
    ENV_AUTH_URL,
    ENV_CLIENT_ID,
    ENV_CLIENT_KEY,
    ENV_REALM,
    ENV_REMOTE_QC_NAME,
    ENV_USER_AGENT,
    ERROR_MESSAGES,
)

logger = logging.getLogger(__name__)


def validate_url(url: str) -> str:
    """Validate and normalize URL.

    Args:
        url: The URL to validate.

    Returns:
        The validated URL.

    Raises:
        ValueError: If the URL format is invalid.
    """
    logger.debug(f"Validating URL: {url}")
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        logger.error(f"Invalid URL format: {url}")
        raise ValueError(ERROR_MESSAGES["invalid_url"].format(url=url))
    return url


def normalize_path(path: str) -> str:
    """Normalize URL path.

    Args:
        path: The path to normalize.

    Returns:
        The normalized path with proper encoding.
    """
    logger.debug(f"Normalizing path: {path}")
    # Remove leading/trailing slashes and spaces
    path = path.strip().strip("/")
    # Encode path components
    return "/".join(quote(component) for component in path.split("/"))


def build_url(base_url: str, path: str, query_params: Dict[str, str] = None) -> str:
    """Build URL with proper encoding.

    Args:
        base_url: The base URL.
        path: The path to append.
        query_params: Optional query parameters.

    Returns:
        The complete URL with encoded components.
    """
    logger.debug(f"Building URL with base: {base_url}, path: {path}")
    # Validate base URL
    base_url = validate_url(base_url.rstrip("/"))

    # Normalize and encode path
    path = normalize_path(path)

    # Build URL
    url = f"{base_url}/{path}"

    # Add query parameters if provided
    if query_params:
        query_string = "&".join(
            f"{quote(str(k))}={quote(str(v))}" for k, v in query_params.items()
        )
        url = f"{url}?{query_string}"

    logger.debug(f"Built URL: {url}")
    return url


def get_user_agent() -> str:
    """Get User-Agent string.

    Returns:
        The User-Agent string to use in requests.
    """
    custom_user_agent = os.getenv(ENV_USER_AGENT)
    if custom_user_agent:
        logger.debug(f"Using custom User-Agent: {custom_user_agent}")
        return f"{custom_user_agent} {DEFAULT_USER_AGENT}"
    logger.debug(f"Using default User-Agent: {DEFAULT_USER_AGENT}")
    return DEFAULT_USER_AGENT


def configure_stackspot() -> Dict[str, Any]:
    """Configure StackSpot provider settings.

    Returns:
        A dictionary containing all provider configuration.

    Raises:
        ValueError: If required environment variables are missing.
    """
    logger.info("Starting StackSpot configuration...")

    # Get credentials from environment
    client_id = os.getenv(ENV_CLIENT_ID)
    client_key = os.getenv(ENV_CLIENT_KEY)
    client_realm = os.getenv(ENV_REALM, DEFAULT_REALM)
    remote_qc_name = os.getenv(ENV_REMOTE_QC_NAME)

    logger.info(f"Using realm: {client_realm}")
    logger.debug(f"Client ID present: {bool(client_id)}")
    logger.debug(f"Client Key present: {bool(client_key)}")
    logger.debug(f"Remote QC Name: {remote_qc_name}")

    # Get base URLs from environment or use defaults
    auth_base_url = os.getenv(ENV_AUTH_URL, DEFAULT_AUTH_URL)
    api_base_url = os.getenv(ENV_API_URL, DEFAULT_API_URL)

    logger.info(f"Auth base URL: {auth_base_url}")
    logger.info(f"API base URL: {api_base_url}")

    if not client_id or not client_key:
        logger.error("Missing credentials")
        raise ValueError(ERROR_MESSAGES["missing_credentials"])

    if not remote_qc_name:
        logger.error("Missing remote QC name")
        raise ValueError(ERROR_MESSAGES["missing_remote_qc"])

    # Validate base URLs
    try:
        auth_base_url = validate_url(auth_base_url)
        api_base_url = validate_url(api_base_url)
        logger.info("URLs validated successfully")
    except ValueError as e:
        logger.error(f"URL validation failed: {str(e)}")
        raise

    # Build endpoint URLs
    try:
        auth_url = build_url(
            auth_base_url,
            API_PATH_TOKEN.format(realm=client_realm),
        )
        create_exec_url = build_url(api_base_url, API_PATH_CREATE_EXECUTION)
        check_exec_url = build_url(api_base_url, API_PATH_CHECK_EXECUTION)
        logger.info("Endpoint URLs built successfully")
        logger.debug(f"Auth URL: {auth_url}")
        logger.debug(f"Create execution URL: {create_exec_url}")
        logger.debug(f"Check execution URL: {check_exec_url}")
    except Exception as e:
        logger.error(f"Failed to build URLs: {str(e)}")
        raise

    # Create configuration
    logger.info("Creating final configuration...")
    config = DEFAULT_CONFIG.copy()
    config.update({
        "auth": {
            "auth_url": auth_url,
            "realm": client_realm,
            "client_id": client_id,
            "secret_key": client_key,
        },
        "api": {
            "remote_qc_name": remote_qc_name,
            "create_exec_url": create_exec_url,
            "check_exec_url": check_exec_url,
            "headers": {
                **DEFAULT_HEADERS,
                "User-Agent": get_user_agent(),
            },
        },
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
    })

    logger.info("StackSpot configuration completed successfully")
    return config
