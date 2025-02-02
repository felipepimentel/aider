---
parent: Connecting to LLMs
nav_order: 500
---

# StackSpot AI

Aider can connect to StackSpot AI's models. To use StackSpot AI models, you need to set up your API key:

```bash
# Set your API key using environment variables
export STACKSPOT_API_KEY=<key> # Mac/Linux
setx STACKSPOT_API_KEY <key>   # Windows, restart shell after setx

# Use StackSpot AI Chat model
aider --model stackspot-ai-chat

# Use StackSpot AI Code model (optimized for code)
aider --model stackspot-ai-code

# Use StackSpot AI Assistant model
aider --model stackspot-ai-assistant

# List all available StackSpot models
aider --list-models stackspot
```

## Model Settings

Create a `.aider.model.settings.yml` file in your home directory or git project root with settings like this:

```yaml
- name: stackspot-ai-chat
  edit_format: diff
  weak_model_name: null
  use_repo_map: true
  send_undo_reply: true
  lazy: false
  reminder: user
  examples_as_sys_msg: true
  extra_params:
    max_tokens: 8192
    model_type: chat

- name: stackspot-ai-code
  edit_format: diff
  weak_model_name: null
  use_repo_map: true
  send_undo_reply: true
  lazy: false
  reminder: user
  examples_as_sys_msg: true
  extra_params:
    max_tokens: 8192
    model_type: code

- name: stackspot-ai-assistant
  edit_format: diff
  weak_model_name: null
  use_repo_map: true
  send_undo_reply: true
  lazy: false
  reminder: user
  examples_as_sys_msg: true
  extra_params:
    max_tokens: 8192
    model_type: assistant
```

## Model Types

StackSpot AI offers three main model types:

1. **Chat Model (stackspot-ai-chat)**: General purpose chat model optimized for natural conversations and task completion.

2. **Code Model (stackspot-ai-code)**: Specialized model for code-related tasks, including code generation, refactoring, and bug fixing.

3. **Assistant Model (stackspot-ai-assistant)**: Task-specific model designed for software development assistance and project management.

## Best Practices

- Use the Code model (`stackspot-ai-code`) for most programming tasks as it's optimized for code generation and modification
- Use the Chat model (`stackspot-ai-chat`) for general discussions and planning
- Use the Assistant model (`stackspot-ai-assistant`) for project management and documentation tasks

## Getting Help

For more information about StackSpot AI and its capabilities, visit the [StackSpot AI documentation](https://docs.stackspot.com/en/ai). 