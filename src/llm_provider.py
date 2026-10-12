"""Groq LLM wrapper — domain-agnostic. Copy as-is; do not edit."""
import logging

from langchain_groq import ChatGroq

from . import config

logger = logging.getLogger(__name__)


class LLMProvider:
    """
    Wraps ChatGroq for use with LangChain AgentExecutor.

    Usage:
        provider = LLMProvider()
        llm = provider.get_chat_model()
    """

    def __init__(self) -> None:
        if not config.GROQ_API_KEY:
            logger.warning(
                "[LLM] GROQ_API_KEY not set — set it in .env before running live questions"
            )
        logger.info(f"[LLM] Initialised — model={config.GROQ_MODEL}")

    def get_chat_model(self) -> ChatGroq:
        return ChatGroq(
            api_key=config.GROQ_API_KEY,
            model_name=config.GROQ_MODEL,
            temperature=0,
        )
