"""Configuration module for StackSpot provider."""

import logging
import os
from typing import Any, Dict
from urllib.parse import quote, urlparse

from .stackspot_constants import (
    API_PATH_CHECK_EXECUTION,
    API_PATH_CREATE_EXECUTION,
    API_PATH_TOKEN,
    DEFAULT_CONFIG,
    DEFAULT_HEADERS,
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
    return "aider/1.0 (+https://aider.chat)"


def configure_stackspot() -> Dict[str, Any]:
    """Configure StackSpot provider settings.

    Returns:
        A dictionary containing all provider configuration.

    Raises:
        ValueError: If required environment variables are missing.
    """
    logger.info("Starting StackSpot configuration...")

    # Get credentials from environment
    client_id = os.getenv("STACKSPOTAI_CLIENT_ID")
    client_key = os.getenv("STACKSPOTAI_CLIENT_KEY")
    client_realm = os.getenv("STACKSPOTAI_REALM", "stackspot")
    remote_qc_name = os.getenv("STACKSPOTAI_REMOTEQC_NAME")

    logger.info(f"Using realm: {client_realm}")
    logger.debug(f"Client ID present: {bool(client_id)}")
    logger.debug(f"Client Key present: {bool(client_key)}")
    logger.debug(f"Remote QC Name: {remote_qc_name}")

    # Get base URLs from environment or use defaults
    auth_base_url = os.getenv("STACKSPOTAI_AUTH_URL", "https://auth.stackspot.com")
    api_base_url = os.getenv(
        "STACKSPOTAI_API_URL", "https://genai-code-buddy-api.stackspot.com"
    )

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
    })

    logger.info("StackSpot configuration completed successfully")
    return config
