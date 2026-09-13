from .base import (
    GenerationProvider,
    GenerationRequest,
    GenerationResult,
    ProviderUnavailable,
)
from .claude_code import ClaudeCodeProvider
from .mock import MockEchoProvider

_REGISTRY = {
    "claude": ClaudeCodeProvider,
    "mock": MockEchoProvider,
}


def get_provider(name: str) -> GenerationProvider:
    cls = _REGISTRY.get(name)
    if cls is None:
        raise KeyError(f"unknown generation provider '{name}' (available: {', '.join(_REGISTRY)})")
    return cls()


__all__ = [
    "GenerationProvider",
    "GenerationRequest",
    "GenerationResult",
    "ProviderUnavailable",
    "ClaudeCodeProvider",
    "MockEchoProvider",
    "get_provider",
]
