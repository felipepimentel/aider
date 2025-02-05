import importlib.resources
import logging
import os
from typing import Optional

import yaml

from .settings import ModelSettings

logger = logging.getLogger(__name__)

# Default settings for all models
DEFAULT_MODEL_SETTINGS = {
    "model_type": "chat",
    "max_tokens": 8192,
    "max_chat_history_tokens": 1024,
    "edit_format": "whole",
    "use_repo_map": False,
    "send_undo_reply": False,
    "lazy": False,
    "reminder": "user",
    "examples_as_sys_msg": False,
    "cache_control": False,
    "caches_by_default": False,
    "use_system_prompt": True,
    "use_temperature": True,
    "streaming": True,
}

# Load model settings from package resource
MODEL_SETTINGS = []
try:
    with importlib.resources.open_text("aider.resources", "model-settings.yml") as f:
        model_settings_list = yaml.safe_load(f)
        if model_settings_list:
            for settings_dict in model_settings_list:
                # Ensure name is present
                if "name" not in settings_dict:
                    continue
                # Merge with default settings
                merged_settings = DEFAULT_MODEL_SETTINGS.copy()
                merged_settings.update(settings_dict)
                # Create model settings with all settings
                model_settings = ModelSettings(**merged_settings)
                MODEL_SETTINGS.append(model_settings)
except Exception as e:
    logger.warning(f"Could not load model settings from package resource: {e}")

# Add stackspot-ai model settings
stackspot_settings = {
    "name": "stackspot-ai",
    "edit_format": "diff",
    "use_repo_map": True,
    "send_undo_reply": True,
    "examples_as_sys_msg": True,
    "reminder": "user",
    "extra_params": {
        "max_tokens": 8192,
        "model_type": "code",
        "streaming": True,
        "temperature": 0.7,
        "api_base": "https://genai-code-buddy-api.stackspot.com",
        "api_path": "/v1/code/completions",
    },
}
# Merge with default settings
merged_stackspot_settings = DEFAULT_MODEL_SETTINGS.copy()
merged_stackspot_settings.update(stackspot_settings)
MODEL_SETTINGS.append(ModelSettings(**merged_stackspot_settings))

MODEL_ALIASES = {
    "stackspot-ai-code": "openai/stackspot-ai-code",
}


class Model(ModelSettings):
    def __init__(
        self,
        name: str,
        api_key: Optional[str] = None,
        use_temperature: bool = True,
        remove_reasoning: Optional[str] = None,
        extra_params: Optional[dict] = None,
        use_repo_map: bool = True,
    ):
        # Normalize api_key if it's a list
        if isinstance(api_key, list):
            api_key = api_key[0] if api_key else None

        # If no api_key provided, try to get from environment
        if not api_key and "stackspot" in name.lower():
            api_key = os.getenv("STACKSPOTAI_CLIENT_KEY")

        # Initialize parent class with all required attributes
        super().__init__(
            name=name,
            api_key=api_key,
            model_type="chat" if "chat" in name else "code",
            use_temperature=use_temperature,
            remove_reasoning=remove_reasoning,
            extra_params=extra_params or {},
            use_repo_map=use_repo_map,
            edit_format="diff",  # Default edit format
            send_undo_reply=True,  # Default value
            examples_as_sys_msg=True,  # Default value
            reminder="user",  # Default value
            streaming=True,  # Default value
            max_tokens=8192,  # Default value
            max_chat_history_tokens=1024,  # Default value
        )

        # Handle model alias
        model = MODEL_ALIASES.get(name, name)
        self.name = model

        # Additional model-specific settings
        self.editor_model = None
        self.editor_edit_format = None

        # Find extra settings and configure
        self.extra_model_settings = next(
            (ms for ms in MODEL_SETTINGS if ms.name == "aider/extra_params"), None
        )
        self.configure_model_settings(model)

        # Configure provider
        if "stackspot" in self.name:
            from aider.providers.stackspot import StackSpotProvider

            try:
                self.provider = StackSpotProvider(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not configure StackSpot provider: {e}")

        # Validate environment
        res = self.validate_environment()
        self.missing_keys = res.get("missing_keys", [])
        self.keys_in_environment = res.get("keys_in_environment", [])

    def configure_model_settings(self, model):
        """Configure model-specific settings."""
        # Look for exact model match
        exact_match = False
        for ms in MODEL_SETTINGS:
            if model == ms.name:
                self._copy_model_fields(ms)
                exact_match = True
                break

        if not exact_match:
            self.apply_generic_model_settings(model)

    def _copy_model_fields(self, source):
        """Copy fields from another ModelSettings instance."""
        for field_name in source.model_fields:
            if hasattr(source, field_name):
                val = getattr(source, field_name)
                setattr(self, field_name, val)

    def apply_generic_model_settings(self, model):
        """Apply generic settings based on model name."""
        if "stackspot-ai" in model:
            self.edit_format = "diff"
            self.use_repo_map = True
            self.send_undo_reply = True
            self.examples_as_sys_msg = True
            self.reminder = "user"
            self.max_tokens = 8192
            self.max_chat_history_tokens = 1024
            self.streaming = True
            self.use_temperature = True

    def validate_environment(self):
        """Validate required environment variables."""
        missing_keys = []
        keys_in_environment = []

        if "stackspot" in self.name:
            required_keys = [
                "STACKSPOTAI_CLIENT_ID",
                "STACKSPOTAI_CLIENT_KEY",
                "STACKSPOTAI_REALM",
            ]

            for key in required_keys:
                if not self.api_key and key not in os.environ:
                    missing_keys.append(key)
                else:
                    keys_in_environment.append(key)

        return {
            "missing_keys": missing_keys or [],  # Ensure we always retornam uma lista
            "keys_in_environment": keys_in_environment
            or [],  # Ensure we always retornam uma lista
        }

    @classmethod
    def register_model(cls, name: str, settings: dict) -> None:
        """Register a model with its settings.

        Args:
            name: The name of the model
            settings: Dictionary of model settings or string with model name
        """
        logger.debug(f"Registering model {name} with settings: {settings}")

        if isinstance(settings, str):
            settings = {"model": settings}

        # Merge with default settings
        merged_settings = DEFAULT_MODEL_SETTINGS.copy()
        merged_settings.update(settings)
        merged_settings["name"] = name

        # Create model settings
        try:
            model_settings = ModelSettings(**merged_settings)
            MODEL_SETTINGS.append(model_settings)

            # Add any aliases
            if "aliases" in settings:
                for alias in settings["aliases"]:
                    MODEL_ALIASES[alias] = name

            logger.info(f"Successfully registered model {name}")

        except Exception as e:
            logger.error(f"Error registering model {name}: {str(e)}")
            raise
