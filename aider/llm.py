import os
import sys
import traceback
import warnings

from aider.litellm_init import init_litellm

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

AIDER_SITE_URL = "https://aider.chat"
AIDER_APP_NAME = "Aider"

os.environ["OR_SITE_URL"] = AIDER_SITE_URL
os.environ["OR_APP_NAME"] = AIDER_APP_NAME
os.environ["LITELLM_MODE"] = "PRODUCTION"

VERBOSE = True

print("\n=== Debug: Starting LLM Module ===", file=sys.stderr)
print(f"Current working directory: {os.getcwd()}", file=sys.stderr)
print(f"Python path: {sys.path}", file=sys.stderr)
print("Environment variables:", file=sys.stderr)
print(
    f"- STACKSPOT_API_KEY present: {bool(os.getenv('STACKSPOT_API_KEY'))}",
    file=sys.stderr,
)
print(f"- LITELLM_MODE: {os.getenv('LITELLM_MODE')}", file=sys.stderr)

try:
    print("Initializing LiteLLM...", file=sys.stderr)
    litellm = init_litellm()
    print("LiteLLM initialized successfully!", file=sys.stderr)
except Exception as e:
    print("\nError initializing LiteLLM:", file=sys.stderr)
    print(str(e), file=sys.stderr)
    print("\nTraceback:", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    raise

print("=== Debug: LLM Module Loaded ===\n", file=sys.stderr)

__all__ = [litellm]
