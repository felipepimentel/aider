from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ModelSettings:
    name: str
    api_key: Optional[str] = None
    model_type: str = "chat"
    api_base: Optional[str] = None
    max_tokens: int = 8192
    max_chat_history_tokens: int = 1024
    headers: Optional[Dict[str, str]] = None
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
    provider: Optional[object] = None
    weak_model: Optional["ModelSettings"] = None
    editor_model: Optional["ModelSettings"] = None

    def __post_init__(self):
        if self.headers is None:
            self.headers = {"Content-Type": "application/json"}

        # Handle API key format
        if self.api_key and "=" not in self.api_key:
            self.api_key = f"stackspot={self.api_key}"

    def commit_message_models(self) -> List["ModelSettings"]:
        """Return list of models for commit messages."""
        return [self]

    def token_count(self, text) -> int:
        """Count tokens in text."""
        if isinstance(text, dict):
            content = text.get("content", "")
            if isinstance(content, str):
                return len(content.split())
            elif isinstance(content, list):
                total = 0
                for part in content:
                    if isinstance(part, dict):
                        text = part.get("text", "")
                        total += len(text.split())
                return total
        elif isinstance(text, str):
            return len(text.split())
        return 0

    def token_count_for_image(self, fname: str) -> int:
        """Count tokens for an image file."""
        return 1024  # Approximate token count for images

    def get_repo_map_tokens(self) -> int:
        """Get token limit for repository mapping."""
        return 1024

    def get_model_context_size(self) -> int:
        """Get the model's context size."""
        return 16384  # Default context size for StackSpot models

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate the cost for token usage."""
        return 0.0  # StackSpot models are currently free

    def count_message_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Count tokens in a list of messages."""
        total = 0
        for message in messages:
            total += self.token_count(message)
        return total

    @property
    def info(self):
        """Return model information."""
        return {
            "max_input_tokens": self.max_tokens,
            "max_output_tokens": self.max_tokens,
            "supports_vision": False,
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
            "supports_assistant_prefill": False,
            "supports_functions": True,
            "supports_streaming": True,
        }
