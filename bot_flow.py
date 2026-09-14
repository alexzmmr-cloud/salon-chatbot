from pathlib import Path

import agent_runtime
import db
from agent.tools import looks_like_contact

KNOWLEDGE_DIR = Path(__file__).resolve().parent / "knowledge"

MAIN_MENU = ["Услуги", "FAQ", "Оставить заявку", "ИИ-консультант", "Обратная связь"]

_MENU_COMMANDS = {
    "услуги": "services",
    "/услуги": "services",
    "faq": "faq",
    "/faq": "faq",
    "оставить заявку": "lead",
    "заявка": "lead",
    "ии-консультант": "ai_consultant",
    "ai": "ai_consultant",
    "консультант": "ai_consultant",
    "обратная связь": "feedback",
    "отзыв": "feedback",
}

# session_id -> {"mode": str, "step": str, "draft": dict}
_sessions: dict[str, dict] = {}


def _get_session(session_id: str) -> dict:
    if session_id not in _sessions:
        _sessions[session_id] = {"mode": None, "step": None, "draft": {}}
    return _sessions[session_id]


def _reset_session(session_id: str) -> None:
    session = _get_session(session_id)
    session.clear()
    session.update(mode=None, step=None, draft={})


def _menu_reply(text: str) -> dict:
    # menu пустой: главное меню теперь статичная панель на фронте (interface/app.js),
    # это поле используется только для контекстных действий шага (например черновик заявки).
    return {"text": text, "menu": []}


def _read_knowledge(filename: str) -> str:
    path = KNOWLEDGE_DIR / filename
    return path.read_text(encoding="utf-8")


def handle_message(session_id: str, text: str) -> dict:
    session = _get_session(session_id)
    stripped = text.strip()
    normalized = stripped.lower()
    command = _MENU_COMMANDS.get(normalized)

    # Клик по любому пункту главного меню прерывает текущий под-сценарий
    # (заявка/отзыв/ИИ-консультант) — меню теперь статичная панель, всегда доступная.
    if session["mode"] in ("lead_flow", "feedback_flow", "ai_consultant") and command is not None:
        if session["mode"] == "ai_consultant":
            agent_runtime.reset_session(session_id)
        _reset_session(session_id)
    elif session["mode"] == "lead_flow":
        return _handle_lead_step(session_id, session, stripped)
    elif session["mode"] == "feedback_flow":
        return _handle_feedback_step(session_id, session, stripped)
    elif session["mode"] == "ai_consultant":
        return agent_runtime.handle_message(session_id, stripped)

    if command == "services":
        return _menu_reply(_read_knowledge("services.md"))
    if command == "faq":
        return _menu_reply(_read_knowledge("faq.md"))
    if command == "lead":
        return _start_lead_flow(session_id, session)
    if command == "ai_consultant":
        return _start_ai_consultant(session_id, session)
    if command == "feedback":
        return _start_feedback_flow(session_id, session)

    return _menu_reply(
        "Не совсем понял запрос. Выберите один из пунктов меню: "
        + ", ".join(MAIN_MENU)
    )


def _start_lead_flow(session_id: str, session: dict) -> dict:
    session["mode"] = "lead_flow"
    session["step"] = "service"
    session["draft"] = {}
    return {
        "text": "Оформляем заявку. Напишите, какая услуга вас интересует.",
        "menu": [],
    }


def _handle_lead_step(session_id: str, session: dict, text: str) -> dict:
    step = session["step"]

    if not text:
        return {"text": "Пустое сообщение не подходит, напишите текстом, пожалуйста.", "menu": []}

    if step == "service":
        session["draft"]["service"] = text.strip()
        session["step"] = "contact"
        return {"text": "Оставьте контакт для связи (телефон или мессенджер).", "menu": []}

    if step == "contact":
        if not looks_like_contact(text):
            return {
                "text": "Контакт не похож на телефон или email. Пришлите, пожалуйста, номер телефона "
                "(10-11 цифр) или email.",
                "menu": [],
            }
        session["draft"]["contact"] = text
        session["step"] = "problem"
        return {"text": "Коротко опишите задачу или пожелание.", "menu": []}

    if step == "problem":
        session["draft"]["problem_text"] = text
        draft = session["draft"]
        db.save_lead(
            session_id=session_id,
            source="bot_flow",
            service=draft.get("service"),
            contact=draft.get("contact"),
            problem_text=draft.get("problem_text"),
            agent_summary=None,
            missing_info=None,
            status="new",
        )
        _reset_session(session_id)
        return _menu_reply("Заявка сохранена. Мы свяжемся с вами по указанному контакту. Спасибо!")

    _reset_session(session_id)
    return _menu_reply("Что-то пошло не так с шагом заявки, начните заново — выберите пункт меню.")


def _start_ai_consultant(session_id: str, session: dict) -> dict:
    session["mode"] = "ai_consultant"
    session["step"] = None
    session["draft"] = {}
    return {
        "text": "Вы в режиме ИИ-консультанта. Задайте вопрос об услугах или попросите помочь с заявкой. "
        "Чтобы выйти — выберите любой другой пункт меню.",
        "menu": [],
    }


def _start_feedback_flow(session_id: str, session: dict) -> dict:
    session["mode"] = "feedback_flow"
    session["step"] = "message"
    session["draft"] = {}
    return {"text": "Напишите ваш отзыв или пожелание одним сообщением.", "menu": []}


def _handle_feedback_step(session_id: str, session: dict, text: str) -> dict:
    if not text:
        return {"text": "Пустое сообщение не подходит, напишите текстом, пожалуйста.", "menu": []}

    db.save_feedback(session_id=session_id, message_text=text)
    _reset_session(session_id)
    return _menu_reply("Спасибо за обратную связь!")
