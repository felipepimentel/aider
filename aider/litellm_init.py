import logging
import sys

import litellm

from aider.providers.stackspot_config import configure_stackspot


def setup_logging():
    """Setup logging to both file and console"""
    log_file = "/tmp/litellm_debug.log"

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, mode="w"),
            logging.StreamHandler(sys.stderr),
        ],
    )

    # Also write directly to the file for immediate feedback
    with open(log_file, "w") as f:
        f.write("Starting LiteLLM logging...\n")

    return logging.getLogger("litellm_init")


def init_litellm():
    """Initialize LiteLLM with appropriate provider"""
    # Write directly to the log file
    with open("/tmp/litellm_debug.log", "a") as f:
        f.write("\n=== Starting LiteLLM Initialization ===\n")

    logger = setup_logging()
    logger.info("Logger initialized")

    try:
        # Basic LiteLLM configuration
        logger.info("Configuring LiteLLM base settings...")
        litellm.set_verbose = True
        litellm.drop_params = True
        litellm.cache = False

        logger.info("LiteLLM base configuration:")
        logger.info(f"- Verbose mode: {litellm.set_verbose}")
        logger.info(f"- Drop params: {litellm.drop_params}")
        logger.info(f"- Cache enabled: {litellm.cache}")

        # Configure StackSpot provider
        logger.info("Configuring StackSpot provider...")
        configure_stackspot()
        logger.info("StackSpot provider configured successfully")

        # Test the configuration
        logger.info("Testing LiteLLM configuration...")
        try:
            # Test a simple completion
            test_messages = [{"role": "user", "content": "Hello, are you working?"}]
            response = litellm.completion(
                model="openai/stackspot-ai-code",
                messages=test_messages,
                max_tokens=50,
                temperature=0.7,
            )
            logger.info("Test completion successful!")
            logger.info(f"Response: {response}")
        except Exception as e:
            logger.warning(f"Test completion failed: {str(e)}")
            logger.info("This might indicate a configuration issue.")
            with open("/tmp/litellm_debug.log", "a") as f:
                f.write(f"Warning: Test completion failed: {str(e)}\n")
                f.write("This might indicate a configuration issue.\n")

        logger.info("=== LiteLLM Initialization Complete ===")
        with open("/tmp/litellm_debug.log", "a") as f:
            f.write("=== LiteLLM Initialization Complete ===\n")

        return litellm

    except Exception as e:
        logger.error("Error during LiteLLM initialization:")
        logger.error(str(e))
        logger.error("Traceback:", exc_info=True)
        with open("/tmp/litellm_debug.log", "a") as f:
            f.write("Error during LiteLLM initialization:\n")
            f.write(f"{str(e)}\n")
            f.write("See traceback in logs\n")
        raise
