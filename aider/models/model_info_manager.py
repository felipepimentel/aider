import json
from pathlib import Path
from typing import Any, Dict, Optional


class ModelInfoManager:
    _instance = None
    _model_info_cache: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelInfoManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self._load_model_info()

    def _load_model_info(self):
        """Load model information from a JSON file if it exists"""
        try:
            cache_file = Path.home() / ".aider" / "model_info.json"
            if cache_file.exists():
                self._model_info_cache = json.loads(cache_file.read_text())
        except (json.JSONDecodeError, OSError):
            self._model_info_cache = {}

    def get_model_from_cached_json_db(
        self, model_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get model information from the cache"""
        return self._model_info_cache.get(model_name)

    def update_model_info(self, model_name: str, info: Dict[str, Any]) -> None:
        """Update model information in the cache"""
        self._model_info_cache[model_name] = info
        try:
            cache_file = Path.home() / ".aider" / "model_info.json"
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(self._model_info_cache, indent=4))
        except OSError:
            pass


# Create a singleton instance
model_info_manager = ModelInfoManager()
