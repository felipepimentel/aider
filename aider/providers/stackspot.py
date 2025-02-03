import json
import os
from pathlib import Path
from typing import Dict, List, Optional

import httpx

from aider.dump import dump


class StackSpotProvider:
    def __init__(self):
        self.api_key = os.getenv("STACKSPOT_API_KEY")
        if not self.api_key:
            raise ValueError("STACKSPOT_API_KEY environment variable not set")

        self.api_base = "https://api.stackspot.com/v1"
        self.config_file = Path(__file__).parent.parent / "resources" / "stackspot.json"
        self.load_config()

    def load_config(self):
        if self.config_file.exists():
            with open(self.config_file) as f:
                self.config = json.load(f)
        else:
            self.config = {}

    def get_model_config(self, model: str) -> Dict:
        if model not in [
            "stackspot-ai-chat",
            "stackspot-ai-code",
            "stackspot-ai-assistant",
        ]:
            raise ValueError(f"Unknown model: {model}")
        return self.config.get("models", {}).get(model, {})

    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = True,
        **kwargs,
    ) -> Dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "stream": stream,
        }

        if max_tokens:
            data["max_tokens"] = max_tokens

        endpoint = "/chat/completions"
        if "code" in model:
            endpoint = "/code/completions"
        elif "assistant" in model:
            endpoint = "/assistant/completions"

        response = httpx.post(
            f"{self.api_base}{endpoint}",
            headers=headers,
            json=data,
            timeout=60,
        )

        if response.status_code != 200:
            raise Exception(f"Error from StackSpot API: {response.text}")

        return response.json()

    def completion(self, *args, **kwargs):
        return self.chat_completion(*args, **kwargs)

    def count_tokens(self, text: str) -> int:
        # Placeholder implementation
        return len(text.split())

    def count_message_tokens(self, messages: List[Dict[str, str]]) -> int:
        # Placeholder implementation
        return sum(len(msg["content"].split()) for msg in messages)

    def get_model_context_size(self, model: str) -> int:
        return 16384  # Default context size

    def calculate_cost(
        self, model: str, input_tokens: int, output_tokens: int
    ) -> float:
        # Free tier
        return 0.0
