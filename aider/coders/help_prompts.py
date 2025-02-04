# flake8: noqa: E501

from .base_prompts import CoderPrompts


class HelpPrompts(CoderPrompts):
    main_system = """You are an expert on the AI coding tool called Aider.
Answer the user's questions about how to use aider.

The user is currently chatting with you using aider, to write and edit code.

Use the provided aider documentation *if it is relevant to the user's question*.

Include a bulleted list of urls to the aider docs that might be relevant for the user to read.
Include *bare* urls. *Do not* make [markdown links](http://...).
For example:
- https://aider.chat/docs/usage.html
- https://aider.chat/docs/faq.html

If you don't know the answer, say so and suggest some relevant aider doc urls.

If asks for something that isn't possible with aider, be clear about that.
Don't suggest a solution that isn't supported.

Be helpful but concise.

Unless the question indicates otherwise, assume the user wants to use aider as a CLI tool.

Keep this info about the user's system in mind:
{platform}
"""

    example_messages = []
    system_reminder = ""

    files_content_prefix = """These are some files we have been discussing that we may want to edit after you answer my questions:
"""

    files_no_full_files = "I am not sharing any files with you."

    files_no_full_files_with_repo_map = ""
    files_no_full_files_with_repo_map_reply = ""

    repo_content_prefix = """Here are summaries of some files present in my git repository.
We may look at these in more detail after you answer my questions.
"""

    system = """You are an expert on using the aider coding assistant. Help users understand how to use aider effectively.

Reply using markdown formatting.
"""

    commands = """
Available commands:

/help [topic]      Show help about topic, or general help if no topic given
/exit, /quit       Exit the application
/run CMD          Run a shell command and optionally add the output to the chat
/add FILES        Add files to the chat session
/drop FILES       Remove files from the chat session
/ls               List files in chat session
/lint             Run the linter on all files
/test             Run the test command
/undo             Undo the last git commit if it was done by aider
/diff             Display the git diff of local changes
/commit           Commit edits to git (commit message is optional)
/git CMD          Run a git command
/copy-context     Copy chat context to clipboard
/clear            Clear the chat history
/tokens           Report token usage statistics
/voice            Toggle voice input mode
/web URL          Add content from a URL to the chat
/map              Show the repository map
/edit-format      Show or change the edit format
/model            Show or change the current model
/conversations    List all conversations
/switch-conversation ID  Switch to a different conversation
/delete-conversation ID  Delete a conversation
/new-conversation  Start a new conversation
"""

    topics = {
        "conversations": """
# Conversation Management

Aider supports managing multiple conversations with the StackSpot AI provider. Each conversation maintains its own context and history.

Commands:
- `/conversations` - List all conversations with their details
- `/switch-conversation ID` - Switch to a different conversation
- `/delete-conversation ID` - Delete a conversation
- `/new-conversation` - Start a new conversation

Each conversation stores metadata including:
- Creation time
- Last used time
- Model used
- Status of last interaction
- Message history

Conversations are persisted between sessions and stored in `~/.aider/conversations/`.

Example usage:
```
/conversations              # List all conversations
/new-conversation          # Start a fresh conversation
/switch-conversation conv-1234  # Switch to existing conversation
/delete-conversation conv-1234  # Delete a conversation
```
""",
        "edit-formats": "Information about different edit formats...",
        "models": "Information about different models...",
        "git": "Information about git integration...",
        "voice": "Information about voice commands...",
    }
