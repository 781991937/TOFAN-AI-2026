"""Model provider construction for TOFAN."""

from .providers import AIProvider, OpenAIResponsesProvider


SUPPORTED_AI_PROVIDERS = ("openai", "gemini")


def build_configured_provider(*, model: str | None = None, provider: str | None = None) -> AIProvider:
    """Build the selected provider with a data-driven per-agent model."""
    selected_provider = (provider or "openai").strip().lower()
    if selected_provider not in SUPPORTED_AI_PROVIDERS:
        raise ValueError(f"Unsupported AI provider: {selected_provider}")
    return OpenAIResponsesProvider(model=model, provider=selected_provider)
