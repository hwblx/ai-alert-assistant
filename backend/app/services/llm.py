from app.settings import settings
from app.errors import ModelInitializationError


def get_model():
    index = settings.INFERENCE_PROVIDER
    provider_name = getattr(settings, f"PROVIDER_NAME_{index}", None)
    provider_model = getattr(settings, f"PROVIDER_MODEL_{index}", None)
    provider_key = getattr(settings, f"PROVIDER_KEY_{index}", None)
    provider_url = getattr(settings, f"PROVIDER_URL_{index}", None)

    if not (provider_name and provider_model):
        raise ModelInitializationError("Missing provider name or model.")

    try:
        if provider_name.lower() == "ollama":
            from pydantic_ai.models.ollama import OllamaModel
            from pydantic_ai.providers.ollama import OllamaProvider

            if not provider_url:
                raise ValueError("Missing provider URL")

            return OllamaModel(
                provider_model,
                provider=OllamaProvider(
                    base_url=provider_url,
                ),
            )

        elif provider_name.lower() == "openrouter":
            from pydantic_ai.models.openrouter import OpenRouterModel
            from pydantic_ai.providers.openrouter import OpenRouterProvider

            if not provider_key:
                raise ValueError("Missing provider api key")

            return OpenRouterModel(
                provider_model,
                provider=OpenRouterProvider(
                    api_key=provider_key,
                ),
            )

        else:
            raise ValueError(
                f"unknown provider name '{provider_name}'"
            )

    except Exception as e:
        raise ModelInitializationError(
            f"Model initialization failed: {e}"
        ) from e

