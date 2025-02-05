from packaging import version

__version__ = "0.73.1.dev"
safe_version = __version__

try:
    from aider._version import __version__
except Exception:
    __version__ = safe_version + "+import"

if type(__version__) is not str:
    __version__ = safe_version + "+type"
else:
    try:
        if version.parse(__version__) < version.parse(safe_version):
            __version__ = safe_version + "+less"
    except Exception:
        __version__ = safe_version + "+parse"

__all__ = [__version__]


def check_dependencies():
    """Check if all required dependencies are installed."""
    try:
        import tiktoken
    except ImportError:
        print(
            "Warning: tiktoken not found. Installing tiktoken for better token counting..."
        )
        try:
            import subprocess

            subprocess.check_call(["pip", "install", "tiktoken"])
        except Exception as e:
            print(f"Failed to install tiktoken: {e}")
            print("Will fall back to rough token estimation.")

    try:
        import httpx
    except ImportError:
        raise ImportError(
            "httpx is required for StackSpot integration. Please install it with: pip install httpx"
        )


# Run dependency check on import
check_dependencies()
