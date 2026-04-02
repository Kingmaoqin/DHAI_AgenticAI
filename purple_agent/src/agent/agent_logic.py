"""Agent logic module.

Provides a pluggable agent interface. The default implementation uses
Google ADK Agent with LiteLLM for a simple single-pass LLM call.
This module is designed to be replaceable with more sophisticated
orchestration (e.g., DHAI state machine) later.
"""

import logging
import os
from pathlib import Path

import yaml
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


def load_prompt(name: str = "default") -> dict:
    """Load a prompt config from YAML."""
    path = PROMPTS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Prompt config not found: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _detect_provider() -> tuple[str, str, str]:
    """Auto-detect LLM provider from env vars.

    Returns (litellm_model_string, api_key, base_url_or_empty).
    Supports:
      - OPENAI_API_KEY with sk-... → standard OpenAI
      - OPENAI_API_KEY with sk-or-... → OpenRouter
      - LLM_PROVIDER / LLM_MODEL / LLM_BASE_URL overrides
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    provider = os.getenv("LLM_PROVIDER", "")
    model = os.getenv("LLM_MODEL", "")
    base_url = os.getenv("LLM_BASE_URL", "")

    if provider and model:
        return f"{provider}/{model}", api_key, base_url

    # auto-detect OpenRouter
    if api_key.startswith("sk-or-"):
        return "openrouter/openai/gpt-4o", api_key, ""

    return "openai/gpt-4o", api_key, base_url


def create_model() -> LiteLlm:
    """Create a LiteLlm model instance with auto-detected provider."""
    model_str, api_key, base_url = _detect_provider()
    logger.info("Creating model: %s (base_url=%s)", model_str, base_url or "default")

    kwargs = {"model": model_str, "api_key": api_key}
    if base_url:
        kwargs["api_base"] = base_url
    return LiteLlm(**kwargs)


def build_agent(
    prompt_name: str = "default",
) -> Agent:
    """Build a Google ADK Agent with the specified prompt and model."""
    config = load_prompt(prompt_name)
    model = create_model()

    agent = Agent(
        name=config["name"],
        model=model,
        description=config["description"],
        instruction=config["instructions"],
        tools=[],
    )
    logger.info("Agent built: %s", config["name"])
    return agent
