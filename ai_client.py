"""Клиент для Yandex Cloud AI Studio через OpenAI-compatible SDK."""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

AI_STUDIO_BASE_URL = "https://ai.api.cloud.yandex.net/v1"


def get_client() -> OpenAI:
    api_key = os.environ.get("YC_API_KEY")
    folder_id = os.environ.get("YC_FOLDER_ID")
    if not api_key or not folder_id:
        raise RuntimeError(
            "YC_API_KEY / YC_FOLDER_ID не заданы в .env — "
            "ИИ-консультант недоступен, используйте обычный bot-flow."
        )
    return OpenAI(api_key=api_key, project=folder_id, base_url=AI_STUDIO_BASE_URL)


def get_model() -> str:
    model_uri = os.environ.get("YC_MODEL_URI")
    if not model_uri:
        raise RuntimeError("YC_MODEL_URI не задан в .env — ИИ-консультант недоступен.")
    return model_uri


def chat_completion(messages: list[dict], tools: list[dict] | None = None):
    client = get_client()
    kwargs = {"model": get_model(), "messages": messages}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    return client.chat.completions.create(**kwargs)
