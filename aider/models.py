import importlib.resources
import os
from dataclasses import dataclass, fields
from typing import Dict, Optional

import yaml

from aider.dump import dump  # noqa: F401

DEFAULT_MODEL_NAME = "stackspot-ai-code"

# Mapping of model aliases to their canonical names
MODEL_ALIASES = {
    "stackspot": "stackspot-ai-code",
    "stackspot-code": "stackspot-ai-code",
    "stackspot-chat": "stackspot-ai-chat",
    "stackspot-assistant": "stackspot-ai-assistant",
}


@dataclass
class ModelSettings:
    """Model settings."""

    name: str
    edit_format: str = "diff"
    use_repo_map: bool = True
    send_undo_reply: bool = True
    examples_as_sys_msg: bool = True
    reminder: str = "user"
    extra_params: Dict = None

    def __post_init__(self):
        if self.extra_params is None:
            self.extra_params = {
                "max_tokens": 8192,
                "model_type": "code",
                "streaming": True,
                "temperature": 0.7,
                "api_base": "https://genai-code-buddy-api.stackspot.com",
                "api_path": "/v1/code/completions",
            }


# Load model settings from package resource
MODEL_SETTINGS = []
with importlib.resources.open_text("aider.resources", "model-settings.yml") as f:
    model_settings_list = yaml.safe_load(f)
    for model_settings_dict in model_settings_list:
        if "stackspot" in model_settings_dict.get("name", ""):
            MODEL_SETTINGS.append(ModelSettings(**model_settings_dict))


class Model(ModelSettings):
    def __init__(self, model, editor_model=None, editor_edit_format=None):
        # Map any alias to its canonical name
        model = MODEL_ALIASES.get(model, model)

        self.name = model
        self.max_chat_history_tokens = 1024
        self.editor_model = None

        # Find the model settings
        model_settings = next((ms for ms in MODEL_SETTINGS if ms.name == model), None)

        if model_settings:
            self._copy_fields(model_settings)
        else:
            super().__init__(name=model)

        # Are all needed keys/params available?
        res = self.validate_environment()
        self.missing_keys = res.get("missing_keys")
        self.keys_in_environment = res.get("keys_in_environment")

    def _copy_fields(self, source):
        """Helper to copy fields from a ModelSettings instance to self"""
        for field in fields(ModelSettings):
            val = getattr(source, field.name)
            setattr(self, field.name, val)

    def validate_environment(self):
        api_key = os.getenv("STACKSPOT_API_KEY")
        if not api_key:
            return {"missing_keys": ["STACKSPOT_API_KEY"], "keys_in_environment": []}
        return {"missing_keys": [], "keys_in_environment": ["STACKSPOT_API_KEY"]}

    def __str__(self):
        return self.name

    def token_count(self, message):
        """Count the number of tokens in a message."""
        if isinstance(message, dict):
            content = message.get("content", "")
            if isinstance(content, str):
                # Simple approximation: split on whitespace
                return len(content.split())
            elif isinstance(content, list):
                # For messages with multiple content parts
                total = 0
                for part in content:
                    if isinstance(part, dict):
                        text = part.get("text", "")
                        total += len(text.split())
                return total
        return 0


def load_model_settings(
    model_name: str, api_key: Optional[str] = None
) -> ModelSettings:
    """Load model settings from configuration."""
    model_settings = next((ms for ms in MODEL_SETTINGS if ms.name == model_name), None)
    if model_settings:
        return model_settings
    return ModelSettings(name=model_name)


def load_model_metadata(model_name: str) -> Dict:
    """Load model metadata from configuration."""
    return {
        "name": model_name,
        "max_input_tokens": 16384,
        "max_output_tokens": 8192,
        "supports_functions": False,
        "supports_streaming": True,
        "supports_temperature": True,
    }
