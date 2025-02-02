import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Union

import httpx

from aider.dump import dump  # noqa: F401


class StackSpotProvider:
    def __init__(self):
        self.config = self._load_config()
        self.api_key = os.getenv("STACKSPOT_API_KEY")
        if not self.api_key:
            raise ValueError("STACKSPOT_API_KEY environment variable not set")
        
        self.client = httpx.Client(
            base_url=self.config["api"]["base_url"],
            headers={
                self.config["api"]["auth_header"]: f"{self.config['api']['auth_type']} {self.api_key}"
            },
            timeout=60.0
        )

    def _load_config(self) -> Dict:
        config_path = Path(__file__).parent.parent / "resources" / "stackspot.json"
        with open(config_path) as f:
            return json.load(f)

    def get_model_config(self, model_name: str) -> Dict:
        if model_name not in self.config["models"]:
            raise ValueError(f"Unknown model: {model_name}")
        return self.config["models"][model_name]

    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[Dict, httpx.Response]:
        model_config = self.get_model_config(model)
        endpoint = self.config["api"][f"{model_config['model_type']}_endpoint"]
        
        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
            **kwargs
        }
        
        if max_tokens:
            data["max_tokens"] = max_tokens
        elif model_config.get("max_tokens"):
            data["max_tokens"] = model_config["max_tokens"]

        response = self.client.post(endpoint, json=data)
        response.raise_for_status()
        
        if stream:
            return response
        return response.json()

    def count_tokens(self, model: str, text: str) -> int:
        # This is a placeholder - implement actual token counting based on StackSpot's tokenizer
        # For now, using a simple approximation
        return len(text.split())

    def count_message_tokens(self, model: str, messages: List[Dict[str, str]]) -> int:
        total = 0
        for message in messages:
            total += self.count_tokens(model, message.get("content", ""))
        return total

    def get_model_context_size(self, model: str) -> int:
        model_config = self.get_model_config(model)
        return model_config.get("context_window", 8192)

    def calculate_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> float:
        model_config = self.get_model_config(model)
        input_cost = model_config["input_cost_per_token"] * prompt_tokens
        output_cost = model_config["output_cost_per_token"] * completion_tokens
        return input_cost + output_cost 