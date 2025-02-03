# StackSpot AI Integration

This document describes the integration between StackSpot AI services and LiteLLM in the Aider project.

## Overview

The StackSpot AI integration enables access to StackSpot's AI models through a standardized interface using LiteLLM. This allows you to use StackSpot's models in the same way you would use other LLM providers like OpenAI.

## Available Models

StackSpot provides three specialized AI models:

| Model Name | Alias | Description | Best For |
|------------|-------|-------------|-----------|
| `stackspot-ai-chat` | `stackspot` | General chat completion model | General conversations and text generation |
| `stackspot-ai-code` | `stackspot-code` | Code-specific completion model | Code generation, completion, and analysis |
| `stackspot-ai-assistant` | `stackspot-assistant` | Assistant-style completion model | Task-specific assistance and workflows |

## Configuration

### Prerequisites

1. A StackSpot account with API access
2. A valid StackSpot API key

### Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `STACKSPOT_API_KEY` | Yes | Your StackSpot API key | `your-api-key` or `sk-your-api-key` |

The API key can be provided with or without the 'sk-' prefix. If the prefix is missing, it will be automatically added.

### Basic Usage

```python
from aider.providers.stackspot_config import configure_stackspot
import litellm

# Configure StackSpot provider
configure_stackspot()

# Use with LiteLLM
response = litellm.completion(
    model="stackspot-code",  # or use aliases: "stackspot", "stackspot-assistant"
    messages=[
        {
            "role": "user",
            "content": "Your prompt here"
        }
    ],
    temperature=0.7,
    max_tokens=50
)
```

## API Parameters

### Common Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | str | Required | The model to use (see Available Models) |
| `messages` | List[Dict] | Required | List of messages with 'role' and 'content' |
| `temperature` | float | 0.7 | Controls response randomness (0.0 to 1.0) |
| `max_tokens` | int | 8192 | Maximum tokens to generate |
| `stream` | bool | True | Whether to stream the response |

### Response Format

The response follows the LiteLLM ModelResponse format:

```python
{
    "id": str,           # Unique response ID
    "choices": List,     # List of completion choices
    "model": str,        # Model used for completion
    "usage": Dict        # Token usage statistics
}
```

## Error Handling

The integration includes comprehensive error handling and logging:

- API key validation
- Model configuration validation
- Request/response logging
- Detailed error messages

Common errors:

- `ValueError`: Missing or invalid API key
- `ValueError`: Invalid model name
- HTTP errors (401, 403, etc.): Authentication or authorization issues

## Logging

The integration uses Python's logging system with the following loggers:

- `stackspot_config`: Configuration and setup logging
- Debug logs include:
  - API key validation
  - Request data
  - Response details
  - Error information

## Best Practices

1. **API Key Security**
   - Never hardcode the API key
   - Use environment variables
   - Keep your API key secure

2. **Model Selection**
   - Use `stackspot-ai-chat` for general conversations
   - Use `stackspot-ai-code` for code-related tasks
   - Use `stackspot-ai-assistant` for specific workflow assistance

3. **Error Handling**
   - Always handle potential exceptions
   - Check response status
   - Validate API key before making requests

4. **Performance**
   - Use streaming for long responses
   - Set appropriate max_tokens
   - Handle rate limits appropriately

## Troubleshooting

Common issues and solutions:

1. **403 Forbidden**
   - Check API key format
   - Verify API key is valid
   - Ensure proper authorization

2. **Invalid Model**
   - Verify model name/alias
   - Check available models list
   - Use correct model for task

3. **Request Failures**
   - Check network connectivity
   - Verify request format
   - Review error messages in logs

## Support

For issues or questions:
1. Check the logs for detailed error messages
2. Review the troubleshooting section
3. Contact StackSpot support with relevant logs 