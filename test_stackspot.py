import asyncio
import os
from aider.providers.stackspot import StackSpotProvider


async def test_stackspot():
    # Check API key
    api_key = os.getenv("STACKSPOT_API_KEY")
    print(f"\nAPI Key check:")
    print(f"API Key present: {bool(api_key)}")
    print(f"API Key format: {'sk_stackspot_' in str(api_key) if api_key else 'Invalid'}")
    print(f"API Key length: {len(str(api_key)) if api_key else 0} characters")
    
    try:
        provider = StackSpotProvider()
        print("\nProvider initialized successfully")
        
        # Test message
        messages = [
            {
                "role": "user",
                "content": "Write a simple Python function that adds two numbers."
            }
        ]
        
        print("\nSending request to StackSpot AI...")
        print("URL:", f"{provider.api_base}/v1/quick-commands/create-execution/")
        print("Model: stackspot-ai-code")
        
        response = await provider.completion(
            messages=messages,
            model="stackspot-ai-code",
            temperature=0.7
        )
        
        print("\nResponse received:")
        print("Status: Success")
        print("Model:", response.get("model"))
        print("Content:", response["choices"][0]["message"]["content"])
        
    except ValueError as ve:
        print(f"\nValidation Error: {str(ve)}")
    except Exception as e:
        print(f"\nError occurred: {str(e)}")
        if hasattr(e, '__cause__') and e.__cause__:
            print(f"Caused by: {str(e.__cause__)}")
    finally:
        if 'provider' in locals():
            await provider.close()


if __name__ == "__main__":
    asyncio.run(test_stackspot())
