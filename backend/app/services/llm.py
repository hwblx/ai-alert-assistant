from app.settings import settings
from app.errors import ModelInitializationError

index = settings.INFERENCE_PROVIDER
PROVIDER_NAME = getattr(settings, f"PROVIDER_NAME_{index}", None)
PROVIDER_MODEL = getattr(settings, f"PROVIDER_MODEL_{index}", None)
PROVIDER_KEY = getattr(settings, f"PROVIDER_KEY_{index}", None)
PROVIDER_URL = getattr(settings, f"PROVIDER_URL_{index}", None)


def get_model():
    if not (PROVIDER_NAME and PROVIDER_MODEL):
        raise ModelInitializationError("Missing provider name or model.")

    try:
        if PROVIDER_NAME.lower() == "ollama":
            from pydantic_ai.models.ollama import OllamaModel
            from pydantic_ai.providers.ollama import OllamaProvider

            if not PROVIDER_URL:
                raise ValueError("Missing provider URL")

            return OllamaModel(
                PROVIDER_MODEL,
                provider=OllamaProvider(
                    base_url=PROVIDER_URL,
                ),
            )

        elif PROVIDER_NAME.lower() == "openrouter":
            from pydantic_ai.models.openrouter import OpenRouterModel
            from pydantic_ai.providers.openrouter import OpenRouterProvider

            if not PROVIDER_KEY:
                raise ValueError("Missing provider api key")

            return OpenRouterModel(
                PROVIDER_MODEL,
                provider=OpenRouterProvider(
                    api_key=PROVIDER_KEY,
                ),
            )

        else:
            raise ValueError(
                f"Unknown provider name '{PROVIDER_NAME}'"
            )

    except Exception as e:
        raise ModelInitializationError(
            f"Model initialization failed: {e}"
        ) from e

