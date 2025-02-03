import importlib.resources
import os
from dataclasses import dataclass, fields
from typing import Optional

import yaml

from aider.dump import dump  # noqa: F401

DEFAULT_MODEL_NAME = "stackspot-ai"

# Mapping of model aliases to their canonical names
MODEL_ALIASES = {
    "stackspot": "stackspot-ai",
    "stackspot-code": "stackspot-ai",
}


@dataclass
class ModelSettings:
    name: str
    edit_format: str = "whole"
    use_repo_map: bool = False
    send_undo_reply: bool = False
    lazy: bool = False
    reminder: str = "user"
    examples_as_sys_msg: bool = False
    extra_params: Optional[dict] = None
    cache_control: bool = False
    caches_by_default: bool = False
    use_system_prompt: bool = True
    use_temperature: bool = True
    streaming: bool = True
    editor_model_name: Optional[str] = None
    editor_edit_format: Optional[str] = None
    remove_reasoning: Optional[str] = None


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

        # Find the extra settings
        self.extra_model_settings = next(
            (ms for ms in MODEL_SETTINGS if ms.name == "aider/extra_params"), None
        )

        # Are all needed keys/params available?
        res = self.validate_environment()
        self.missing_keys = res.get("missing_keys")
        self.keys_in_environment = res.get("keys_in_environment")

        self.configure_model_settings(model)

    def configure_model_settings(self, model):
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
        """Helper to copy fields from a ModelSettings instance to self"""
        for field in fields(ModelSettings):
            val = getattr(source, field.name)
            setattr(self, field.name, val)

    def apply_generic_model_settings(self, model):
        if "stackspot-ai" in model:
            self.edit_format = "diff"
            self.use_repo_map = True
            self.send_undo_reply = True
            self.examples_as_sys_msg = True
            self.reminder = "user"
            return

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
