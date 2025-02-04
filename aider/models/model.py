import importlib.resources
import os
from dataclasses import fields
from typing import Optional

import yaml

from .settings import ModelSettings

# Load model settings from package resource
MODEL_SETTINGS = []
with importlib.resources.open_text("aider.resources", "model-settings.yml") as f:
    model_settings_list = yaml.safe_load(f)
    for model_settings_dict in model_settings_list:
        if "stackspot" in model_settings_dict.get("name", ""):
            MODEL_SETTINGS.append(ModelSettings(**model_settings_dict))

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
    ):
        # Initialize parent class
        super().__init__(
            name=name,
            api_key=api_key,
            model_type="chat" if "chat" in name else "code",
            use_temperature=use_temperature,
            remove_reasoning=remove_reasoning,
            extra_params=extra_params or {},
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
                print(f"Warning: Could not configure StackSpot provider: {e}")

        # Validate environment
        res = self.validate_environment()
        self.missing_keys = res.get("missing_keys")
        self.keys_in_environment = res.get("keys_in_environment")

    def configure_model_settings(self, model):
        """Configure model-specific settings."""
        # Look for exact model match
        exact_match = False
        for ms in MODEL_SETTINGS:
            if model == ms.name:
                self._copy_fields(ms)
                exact_match = True
                break

        if not exact_match:
            self.apply_generic_model_settings(model)

    def _copy_fields(self, source):
        """Copy fields from another ModelSettings instance."""
        for field in fields(ModelSettings):
            val = getattr(source, field.name)
            setattr(self, field.name, val)

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
            if not self.api_key and "STACKSPOT_API_KEY" not in os.environ:
                missing_keys.append("STACKSPOT_API_KEY")
            else:
                keys_in_environment.append("STACKSPOT_API_KEY")

        return {
            "missing_keys": missing_keys,
            "keys_in_environment": keys_in_environment,
        }
