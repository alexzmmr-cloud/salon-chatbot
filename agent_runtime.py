import json
import logging
from pathlib import Path

import openai

import ai_client
from agent import tools

logger = logging.getLogger("chatbot")

SOUL_PATH = Path(__file__).resolve().parent / "agent" / "soul.md"
MAX_TOOL_STEPS = 6

DRAFT_ACTIONS = ["Отправить заявку", "Изменить", "Отмена"]

# save_confirmed_lead намеренно НЕ входит сюда — модель никогда не получает
# этот tool в списке доступных функций. Единственный путь его вызова —
# явный вызов из handle_message() в ответ на команду "отправить заявку"
# при активном черновике (см. _handle_draft_command).
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Ищет информацию об услугах, ценах, FAQ и правилах салона по ключевому слову.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Слово или фраза для поиска"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_knowledge_file",
            "description": "Читает файл базы знаний целиком по имени (services.md, faq.md, rules.md).",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Имя файла внутри базы знаний"},
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_lead_draft",
            "description": (
                "Готовит черновик заявки для показа пользователю перед сохранением. "
                "Не сохраняет заявку — только формирует черновик, который пользователь должен подтвердить."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {"type": "string"},
                    "contact": {"type": "string"},
                    "problem_text": {"type": "string"},
                    "agent_summary": {"type": "string", "description": "Короткая выжимка запроса клиента"},
                    "missing_info": {"type": "string"},
                },
                "required": ["service", "problem_text", "agent_summary"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "search_knowledge": lambda session_id, args: tools.search_knowledge(**args),
    "read_knowledge_file": lambda session_id, args: tools.read_knowledge_file(**args),
    "prepare_lead_draft": lambda session_id, args: tools.prepare_lead_draft(**args),
}

_histories: dict[str, list[dict]] = {}
_drafts: dict[str, dict] = {}


def _load_soul() -> str:
    return SOUL_PATH.read_text(encoding="utf-8")


def _get_history(session_id: str) -> list[dict]:
    if session_id not in _histories:
        _histories[session_id] = [{"role": "system", "content": _load_soul()}]
    return _histories[session_id]


def reset_session(session_id: str) -> None:
    _histories.pop(session_id, None)
    _drafts.pop(session_id, None)


def _format_draft(draft: dict) -> str:
    lines = [
        "Проверьте черновик заявки:",
        f"- Услуга: {draft.get('service') or '—'}",
        f"- Задача: {draft.get('agent_summary') or draft.get('problem_text') or '—'}",
        f"- Контакт: {draft.get('contact') or '—'}",
    ]
    if draft.get("missing_info"):
        lines.append(f"- Не хватает: {draft['missing_info']}")
    lines.append("")
    lines.append("Отправить заявку, Изменить или Отменить?")
    return "\n".join(lines)


def _handle_draft_command(session_id: str, normalized_text: str) -> dict | None:
    """Перехватывает Отправить/Изменить/Отмена при активном черновике. None — не команда."""
    draft = _drafts.get(session_id)
    if draft is None:
        return None

    if normalized_text == "отправить заявку":
        tools.save_confirmed_lead(
            session_id=session_id,
            service=draft.get("service"),
            contact=draft.get("contact"),
            problem_text=draft.get("problem_text"),
            agent_summary=draft.get("agent_summary"),
            missing_info=draft.get("missing_info"),
        )
        _drafts.pop(session_id, None)
        return {"text": "Заявка сохранена. Мы свяжемся с вами по указанному контакту. Спасибо!", "menu": []}

    if normalized_text == "изменить":
        _drafts.pop(session_id, None)
        history = _get_history(session_id)
        history.append(
            {
                "role": "user",
                "content": "Пользователь хочет поправить черновик заявки. Спроси, что именно нужно изменить.",
            }
        )
        return _run_model_loop(session_id, history)

    if normalized_text == "отмена":
        _drafts.pop(session_id, None)
        return {
            "text": "Хорошо, заявка не сохранена. Могу ещё чем-то помочь по услугам салона?",
            "menu": [],
        }

    return None


def handle_message(session_id: str, text: str) -> dict:
    stripped = text.strip()
    normalized = stripped.lower()

    draft_result = _handle_draft_command(session_id, normalized)
    if draft_result is not None:
        return draft_result

    history = _get_history(session_id)

    if session_id in _drafts:
        # Черновик активен, но текст не команда — уходит в модель как обычное
        # сообщение, черновик не сбрасывается (см. Plan.md, шаг 4.1).
        history.append(
            {
                "role": "user",
                "content": (
                    f"{stripped}\n\n"
                    "(Есть неподтверждённый черновик заявки — НЕ вызывай prepare_lead_draft повторно. "
                    "Просто ответь на вопрос пользователя своими словами (используй search_knowledge при "
                    "необходимости) и напомни, что заявка ждёт: Отправить заявку, Изменить или Отмена.)"
                ),
            }
        )
    else:
        history.append({"role": "user", "content": stripped})

    result = _run_model_loop(session_id, history)
    if session_id in _drafts and not result["menu"]:
        result["menu"] = DRAFT_ACTIONS
    return result


AI_UNAVAILABLE_REPLY = {
    "text": "ИИ-консультант сейчас недоступен, воспользуйтесь обычным сценарием или оставьте заявку через меню.",
    "menu": [],
}


def _run_model_loop(session_id: str, history: list[dict]) -> dict:
    for _ in range(MAX_TOOL_STEPS):
        try:
            response = ai_client.chat_completion(history, tools=TOOL_SCHEMAS)
        except (RuntimeError, openai.OpenAIError):
            logger.exception("ai_client call failed session=%s", session_id)
            # Последнее сообщение — вопрос пользователя без ответа модели (иначе
            # мы бы сюда не попали): убираем его, чтобы история не осталась с
            # "осиротевшим" user-сообщением на следующий вызов этой сессии.
            if history and history[-1]["role"] == "user":
                history.pop()
            return AI_UNAVAILABLE_REPLY
        message = response.choices[0].message

        if not message.tool_calls:
            history.append({"role": "assistant", "content": message.content})
            return {"text": message.content, "menu": []}

        history.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [tc.model_dump() for tc in message.tool_calls],
            }
        )

        draft_created_this_turn = False

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            logger.info("agent tool call session=%s tool=%s", session_id, name)

            try:
                args = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                result = {"error": "invalid tool arguments"}
            else:
                func = TOOL_FUNCTIONS.get(name)
                if func is None:
                    result = {"error": "tool not available in this context"}
                elif name == "prepare_lead_draft":
                    draft = func(session_id, args)
                    if "error" in draft:
                        result = draft
                    else:
                        _drafts[session_id] = draft
                        draft_created_this_turn = True
                        result = {"status": "draft_ready"}
                else:
                    result = func(session_id, args)

            history.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )

        if draft_created_this_turn:
            draft_text = _format_draft(_drafts[session_id])
            history.append({"role": "assistant", "content": draft_text})
            return {"text": draft_text, "menu": DRAFT_ACTIONS}

    logger.info("agent tool loop limit reached session=%s", session_id)
    return {
        "text": "Не получилось обработать запрос полностью. Предлагаю оставить обычную заявку через меню.",
        "menu": [],
    }
