import logging
import os

import yaml

from aider.models import Model, register_models

logger = logging.getLogger(__name__)

__all__ = ["register_models", "Model"]


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
                        if "name" in model_settings:
                            model_name = model_settings.pop("name")
                            Model.register_model(model_name, model_settings)
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
                        model_name = model_settings.pop("model")
                        Model.register_model(model_name, model_settings)
                        files_loaded.append(settings_file)
                        logger.info(f"Loaded model settings from {settings_file}")
                    else:
                        logger.warning(f"No model name found in settings file: {settings_file}")

        except Exception as e:
            logger.error(f"Error loading model settings from {settings_file}: {e}")
            continue

    return files_loaded
