# StackSpot AI Integration

This document describes the integration between StackSpot AI services and Aider.

## Overview

The StackSpot AI integration enables access to StackSpot's AI models through a standardized interface. This allows you to use StackSpot's models for code generation, completion, and analysis.

## Prerequisites

1. A StackSpot account with API access
2. Client credentials:
   - Client ID
   - Client Key
   - Client Realm (optional, defaults to "stackspot")

## Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `STACKSPOTAI_CLIENT_ID` | Yes | Your StackSpot Client ID | `client-id-xxx` |
| `STACKSPOTAI_CLIENT_KEY` | Yes | Your StackSpot Client Key | `client-key-xxx` |
| `STACKSPOTAI_REALM` | No | Your StackSpot Realm (default: "stackspot") | `my-realm` |

## Available Models

StackSpot provides three specialized AI models:

| Model Name | Description | Best For |
|------------|-------------|-----------|
| `stackspot-ai` | Default model | General code generation and analysis |
| `stackspot-ai-chat` | Chat-optimized model | Interactive conversations and explanations |
| `stackspot-ai-code` | Code-specific model | Code generation, completion, and refactoring |

## Model Capabilities

All models support:
- Maximum input tokens: 16,384
- Maximum output tokens: 8,192
- Temperature range: 0.0 to 1.0 (default: 0.7)
- Streaming responses
- Conversation context

## Authentication

The integration uses OAuth2 client credentials flow:
1. Obtain access token using client credentials
2. Token is automatically refreshed when expired
3. All API requests use Bearer token authentication

## Usage Example

```python
from aider.providers.stackspot import StackSpotProvider

# Initialize provider (will use environment variables)
provider = StackSpotProvider()

# Use the provider
response = await provider.completion(
    messages=[
        {
            "role": "user",
            "content": "Write a Python function to calculate factorial"
        }
    ],
    model="stackspot-ai-code",
    temperature=0.7
)

# Get the generated code
code = response["choices"][0]["message"]["content"]
```

## Error Handling

The integration handles various error scenarios:

| Error Code | Description | Action |
|------------|-------------|---------|
| 400 | Bad Request | Check input parameters |
| 401 | Unauthorized | Verify credentials |
| 403 | Forbidden | Check access permissions |
| 404 | Not Found | Verify endpoint URLs |
| 429 | Too Many Requests | Implement rate limiting |
| 500+ | Server Error | Retry with backoff |

## Configuration

The integration can be configured through the `.aider.litellm.yml` file:

```yaml
providers:
  stackspot:
    api_base: "https://genai-code-buddy-api.stackspot.com"
    api_key: "${STACKSPOTAI_CLIENT_KEY}"
    client_id: "${STACKSPOTAI_CLIENT_ID}"
    client_realm: "${STACKSPOTAI_REALM}"
    models:
      stackspot-ai:
        provider: stackspot
        model: stackspot-ai
        max_tokens: 8192
        model_type: code
      stackspot-ai-chat:
        provider: stackspot
        model: stackspot-ai-chat
        max_tokens: 8192
        model_type: chat
      stackspot-ai-code:
        provider: stackspot
        model: stackspot-ai-code
        max_tokens: 8192
        model_type: code
```

## Best Practices

1. **Environment Variables**
   - Store credentials in environment variables
   - Never hardcode credentials in code
   - Use a secure method to manage secrets

2. **Error Handling**
   - Implement proper error handling
   - Use exponential backoff for retries
   - Log errors appropriately

3. **Performance**
   - Reuse provider instances
   - Implement proper timeouts
   - Monitor token usage

4. **Security**
   - Keep credentials secure
   - Regularly rotate credentials
   - Monitor access patterns

## Troubleshooting

Common issues and solutions:

1. **Authentication Failures**
   - Verify credentials are correct
   - Check environment variables are set
   - Ensure proper access rights

2. **Timeout Errors**
   - Check network connectivity
   - Increase timeout settings
   - Implement retry logic

3. **Rate Limiting**
   - Implement backoff strategy
   - Monitor API usage
   - Contact support for limit increases

## Support

For issues or questions:
1. Check the [documentation](https://docs.stackspot.com)
2. Open an issue on GitHub
3. Contact StackSpot support 