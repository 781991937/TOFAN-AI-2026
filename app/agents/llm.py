"""Model provider construction for TOFAN."""

from .providers import AIProvider, OpenAIResponsesProvider


def build_configured_provider(*, model: str | None = None, provider: str | None = None) -> AIProvider:
    """Build the configured AI provider with a data-driven per-agent model."""
    selected_provider = (provider or "openai").strip().lower()
    if selected_provider != "openai":
        raise ValueError(f"Unsupported AI provider: {selected_provider}")
    return OpenAIResponsesProvider(model=model)
