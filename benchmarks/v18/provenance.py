"""Non-secret provenance for reproducible RETRACE experiments."""

import os
from urllib.parse import urlsplit

from codepilot import agent


PROVIDERS = {
    "groq": ("openai/gpt-oss-120b", "https://api.groq.com/openai/v1"),
    "gemini": (
        "gemini-2.5-flash",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    ),
    "openai": ("gpt-4o-mini", "https://api.openai.com/v1"),
}



def validate_provider_defaults():
    """Ensure recorded provider defaults match the agent's configuration."""
    from unittest.mock import patch

    key_names = {
        "groq": "GROQ_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
    }

    for provider, expected in PROVIDERS.items():
        environment = {
            "CODEPILOT_PROVIDER": provider,
            key_names[provider]: "provenance-validation-placeholder",
        }
        with patch.dict(os.environ, environment, clear=True):
            _, model, endpoint = agent.provider_config()

        if (model, endpoint) != expected:
            raise ValueError(
                "Provenance provider defaults differ from agent defaults"
            )


def experiment_provenance(offline=False):
    """Read model settings without requiring credentials or making HTTP calls."""
    if offline:
        return {
            "execution": "scripted_offline",
            "provider": None,
            "model": None,
            "temperature": None,
            "json_mode": None,
            "max_retries": None,
            "format_retries": None,
            "endpoint": None,
        }

    provider = os.environ.get("CODEPILOT_PROVIDER", "groq").strip().lower()
    if provider not in PROVIDERS:
        raise ValueError("Unsupported experiment provider")

    default_model, endpoint = PROVIDERS[provider]
    model = os.environ.get("CODEPILOT_MODEL", default_model).strip()
    if not model:
        raise ValueError("Experiment model cannot be empty")

    temperature = float(os.environ.get("CODEPILOT_TEMPERATURE", "0"))
    if not 0 <= temperature <= 2:
        raise ValueError("Experiment temperature must be between 0 and 2")

    max_retries = int(os.environ.get("CODEPILOT_MAX_RETRIES", "3"))
    format_retries = int(os.environ.get("CODEPILOT_FORMAT_RETRIES", "2"))

    if not 0 <= max_retries <= 10:
        raise ValueError("Invalid model retry configuration")
    if not 0 <= format_retries <= 10:
        raise ValueError("Invalid format retry configuration")

    parsed = urlsplit(endpoint)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Invalid provider endpoint")

    return {
        "execution": "live_provider",
        "provider": provider,
        "model": model,
        "temperature": temperature,
        "json_mode": os.environ.get("CODEPILOT_JSON_MODE", "0") == "1",
        "max_retries": max_retries,
        "format_retries": format_retries,
        "endpoint": endpoint,
    }
