"""Model provider construction for TOFAN."""

from .providers import AIProvider, OpenAIResponsesProvider


def build_configured_provider() -> AIProvider:
    return OpenAIResponsesProvider()
