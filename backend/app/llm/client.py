from langchain_openai import ChatOpenAI

from app.config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MAX_RETRIES,
    LLM_MODEL,
)


def get_llm(with_tools: bool = False, max_tokens: int | None = None):
    llm = ChatOpenAI(
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        temperature=0.2,
        max_retries=LLM_MAX_RETRIES,
        max_tokens=max_tokens,
    )
    return llm
