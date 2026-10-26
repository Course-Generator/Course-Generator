"""Shared LangChain chat model, created lazily on first use."""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from langchain.chat_models import ChatOpenAI

from coursegen.config import get_settings
from coursegen.errors import ConfigurationError

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    settings = get_settings()
    if not os.getenv("OPENAI_API_KEY"):
        raise ConfigurationError(
            "OPENAI_API_KEY is not set. Add it to your .env file before generating a course."
        )
    try:
        return ChatOpenAI(
            temperature=settings.openai_temperature,
            model_name=settings.openai_model,
        )
    except Exception as exc:
        logger.error("Could not initialise the OpenAI client: %s", exc)
        raise ConfigurationError("Could not initialise the OpenAI client. Check your API key.") from exc
