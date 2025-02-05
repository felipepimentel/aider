import logging
import os

import yaml

from .model import MODEL_ALIASES, MODEL_SETTINGS, Model
from .model_info_manager import model_info_manager
from .settings import ModelSettings

logger = logging.getLogger(__name__)


def register_models(model_settings_files):
    """Register models from settings files."""
    files_loaded = []

    if not model_settings_files:
        logger.warning("No model settings files provided")
        return files_loaded

    for settings_file in model_settings_files:
        if not os.path.exists(settings_file):
            logger.warning(f"Model settings file not found: {settings_file}")
            continue

        try:
            with open(settings_file, "r") as f:
                settings = yaml.safe_load(f)
                if not settings:
                    logger.warning(f"Empty settings file: {settings_file}")
                    continue

                if isinstance(settings, list):
                    # Handle list format
                    for model_settings in settings:
                        if not isinstance(model_settings, dict):
                            logger.warning(
                                f"Invalid model settings format in {settings_file}: {model_settings}"
                            )
                            continue

                        if "name" in model_settings:
                            try:
                                model_name = model_settings.pop("name")
                                Model.register_model(model_name, model_settings)
                                logger.info(
                                    f"Successfully registered model {model_name} from {settings_file}"
                                )
                            except Exception as e:
                                logger.error(
                                    f"Error registering model {model_settings.get('name', 'unknown')}: {e}"
                                )
                                continue
                    files_loaded.append(settings_file)
                    logger.info(f"Loaded model settings from {settings_file}")
                else:
                    # Handle dictionary format
                    # Extract model settings
                    model_settings = {
                        k: v
                        for k, v in settings.items()
                        if k not in ["model_config", "aider/extra_params"]
                    }

                    # Handle global extra params
                    if "extra_params" in settings:
                        model_settings["extra_params"] = settings["extra_params"]

                    # Register the model
                    if "model" in model_settings:
                        try:
                            model_name = model_settings.pop("model")
                            Model.register_model(model_name, model_settings)
                            files_loaded.append(settings_file)
                            logger.info(
                                f"Successfully registered model {model_name} from {settings_file}"
                            )
                        except Exception as e:
                            logger.error(
                                f"Error registering model {model_settings.get('model', 'unknown')}: {e}"
                            )
                    else:
                        logger.warning(
                            f"No model name found in settings file: {settings_file}"
                        )

        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error in {settings_file}: {e}")
            continue
        except Exception as e:
            logger.error(f"Error loading model settings from {settings_file}: {e}")
            continue

    if not files_loaded:
        logger.warning("No model settings files were successfully loaded")

    return files_loaded


def register_litellm_models(settings=None):
    """Register models with LiteLLM"""
    from aider.llm import litellm

    if settings is None:
        settings = MODEL_SETTINGS

    for model_setting in settings:
        if "stackspot" in model_setting.name:
            litellm.model_alias_map[model_setting.name] = f"openai/{model_setting.name}"


def sanity_check_models(io, model):
    """Check if model is valid and has required settings."""
    if not model:
        io.tool_error("No model specified")
        return False

    if not model.name:
        io.tool_error("Model name not specified")
        return False

    if model.missing_keys:
        io.tool_error(
            f"Missing required environment variables for {model.name}: {', '.join(model.missing_keys)}"
        )
        return False

    return True


__all__ = [
    "model_info_manager",
    "ModelSettings",
    "Model",
    "register_models",
    "register_litellm_models",
    "sanity_check_models",
    "MODEL_ALIASES",
]
