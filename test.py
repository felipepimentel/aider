import os

import litellm

from aider.litellm_init import init_litellm


def test_litellm_integration():
    """Test the LiteLLM integration with StackSpot."""
    print("Testing LiteLLM integration...")

    # Initialize LiteLLM
    success = init_litellm()
    assert success, "LiteLLM initialization failed"
    print("✓ LiteLLM initialized successfully")

    # Test API key configuration
    api_key = os.getenv("STACKSPOT_API_KEY")
    assert api_key, "STACKSPOT_API_KEY not found in environment"
    print("✓ API key configured correctly")

    # Test model configuration
    messages = [{"role": "user", "content": "Hello, how are you?"}]

    try:
        # Enable debug mode for detailed logging
        litellm._turn_on_debug()

        # Configure completion parameters
        completion_params = {
            "model": "openai/stackspot-ai-code",
            "messages": messages,
            "max_tokens": 8192,
            "temperature": 0.7,
            "api_base": "https://genai-code-buddy-api.stackspot.com/v1/code",
            "api_key": api_key,
            "headers": {
                "Authorization": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        }

        print("Sending request with parameters:", completion_params)

        # Handle potential exceptions
        try:
            response = litellm.completion(**completion_params)
            print("✓ Model completion request successful")

            # Print the response
            if hasattr(response, "__iter__"):
                print("Streaming response:")
                for chunk in response:
                    if chunk and hasattr(chunk, "choices") and chunk.choices:
                        content = chunk.choices[0].delta.get("content", "")
                        if content:
                            print(f"Response chunk: {content}")
            else:
                print(f"Response: {response.choices[0].message.content}")

        except litellm.exceptions.BadRequestError as e:
            print(f"Bad request error: {e.message}")
            print(f"Status code: {e.status_code}")
            print(f"Provider: {e.llm_provider}")
            raise
        except litellm.exceptions.AuthenticationError as e:
            print(f"Authentication error: {e.message}")
            print(f"Status code: {e.status_code}")
            print(f"Provider: {e.llm_provider}")
            raise
        except litellm.exceptions.APIError as e:
            print(f"API error: {e.message}")
            print(f"Status code: {e.status_code}")
            print(f"Provider: {e.llm_provider}")
            raise

    except Exception as e:
        print(f"Error during model completion: {str(e)}")
        raise


if __name__ == "__main__":
    test_litellm_integration()
