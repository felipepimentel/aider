import importlib.resources
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
        model = MODEL_ALIASES.get(name, name)
        self.name = model
        self.max_chat_history_tokens = 1024
        self.editor_model = None
        self.api_key = api_key
        self.use_temperature = use_temperature
        self.remove_reasoning = remove_reasoning
        self.extra_params = extra_params or {}

        # Model information
        self.info = {
            "max_input_tokens": 1024,
            "max_output_tokens": 1024,
            "supports_vision": False,
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
        }

        # Find the extra settings
        self.extra_model_settings = next(
            (ms for ms in MODEL_SETTINGS if ms.name == "aider/extra_params"), None
        )

        # Are all needed keys/params available?
        res = self.validate_environment()
        self.missing_keys = res.get("missing_keys")
        self.keys_in_environment = res.get("keys_in_environment")

        # Configure model settings
        self.configure_model_settings(model)

        self.editor_model = None
        self.editor_edit_format = None

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
        """Validate environment variables"""
        return {"missing_keys": [], "keys_in_environment": ["STACKSPOT_API_KEY"]}

    def commit_message_models(self):
        """Return list of models for commit messages"""
        return [self]

    def token_count(self, text):
        """Return the number of tokens in the text"""
        return len(text.split())

    def get_repo_map_tokens(self):
        """Return the number of tokens to use for repository mapping"""
        return 1024
