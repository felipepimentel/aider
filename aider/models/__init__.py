from .model import MODEL_SETTINGS, Model
from .model_info_manager import model_info_manager
from .settings import ModelSettings


def register_models(settings=None):
    """Register all available models"""
    if settings is None:
        settings = MODEL_SETTINGS

    for model_setting in settings:
        model_info_manager.update_model_info(
            model_setting.name,
            {
                "max_tokens": model_setting.extra_params.get("max_tokens", 8192)
                if model_setting.extra_params
                else 8192,
                "max_input_tokens": 16384,
                "max_output_tokens": 8192,
                "input_cost_per_token": 0.0,
                "output_cost_per_token": 0.0,
                "litellm_provider": "stackspot"
                if "stackspot" in model_setting.name
                else None,
                "mode": "chat",
            },
        )


def register_litellm_models(settings=None):
    """Register models with LiteLLM"""
    from aider.llm import litellm

    if settings is None:
        settings = MODEL_SETTINGS

    for model_setting in settings:
        if "stackspot" in model_setting.name:
            litellm.model_alias_map[model_setting.name] = f"openai/{model_setting.name}"


def sanity_check_models(io, main_model):
    """Sanity check the models"""
    if not main_model:
        io.tool_error("No model specified")
        return False

    if not main_model.name:
        io.tool_error("Model name not specified")
        return False

    if main_model.missing_keys:
        io.tool_error(f"Missing API keys: {', '.join(main_model.missing_keys)}")
        return False

    return True


__all__ = [
    "model_info_manager",
    "ModelSettings",
    "Model",
    "register_models",
    "register_litellm_models",
    "sanity_check_models",
]
