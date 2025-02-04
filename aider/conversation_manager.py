"""Manages conversations and their persistence."""

import json
import os
import time
from pathlib import Path
from typing import Dict, Optional


class ConversationManager:
    """Manages StackSpot conversations and their persistence."""

    def __init__(self, storage_dir: Optional[str] = None):
        """Initialize the conversation manager.

        Args:
            storage_dir: Directory to store conversation data. Defaults to ~/.aider/conversations
        """
        if storage_dir is None:
            storage_dir = os.path.expanduser("~/.aider/conversations")
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.current_conversation = None
        self._load_conversations()

    def _load_conversations(self):
        """Load all saved conversations from storage."""
        self.conversations = {}
        for file in self.storage_dir.glob("*.json"):
            try:
                with open(file, "r") as f:
                    data = json.load(f)
                    self.conversations[data["conversation_id"]] = data
            except Exception as e:
                print(f"Error loading conversation {file}: {e}")

    def create_conversation(self, metadata: Optional[Dict] = None) -> str:
        """Create a new conversation.

        Args:
            metadata: Optional metadata to store with the conversation

        Returns:
            conversation_id: The ID of the new conversation
        """
        conversation_id = f"conv-{int(time.time())}"
        data = {
            "conversation_id": conversation_id,
            "created_at": time.time(),
            "last_used": time.time(),
            "metadata": metadata or {},
        }
        self.conversations[conversation_id] = data
        self.current_conversation = conversation_id
        self._save_conversation(conversation_id)
        return conversation_id

    def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """Get a conversation by ID."""
        return self.conversations.get(conversation_id)

    def update_conversation(self, conversation_id: str, metadata: Dict):
        """Update a conversation's metadata."""
        if conversation_id not in self.conversations:
            raise ValueError(f"Conversation {conversation_id} not found")

        self.conversations[conversation_id]["metadata"].update(metadata)
        self.conversations[conversation_id]["last_used"] = time.time()
        self._save_conversation(conversation_id)

    def _save_conversation(self, conversation_id: str):
        """Save a conversation to storage."""
        data = self.conversations[conversation_id]
        file_path = self.storage_dir / f"{conversation_id}.json"
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    def list_conversations(self) -> Dict[str, Dict]:
        """List all conversations."""
        return self.conversations

    def delete_conversation(self, conversation_id: str):
        """Delete a conversation."""
        if conversation_id not in self.conversations:
            raise ValueError(f"Conversation {conversation_id} not found")

        file_path = self.storage_dir / f"{conversation_id}.json"
        if file_path.exists():
            file_path.unlink()

        del self.conversations[conversation_id]
        if self.current_conversation == conversation_id:
            self.current_conversation = None

    def get_current_conversation(self) -> Optional[str]:
        """Get the current conversation ID."""
        return self.current_conversation

    def set_current_conversation(self, conversation_id: str):
        """Set the current conversation ID."""
        if conversation_id not in self.conversations:
            raise ValueError(f"Conversation {conversation_id} not found")
        self.current_conversation = conversation_id
