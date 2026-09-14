import re
from pathlib import Path

import db

KNOWLEDGE_DIR = (Path(__file__).resolve().parent.parent / "knowledge").resolve()

_PHONE_DIGITS_RE = re.compile(r"\d")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def looks_like_contact(contact: str | None) -> bool:
    """Грубая проверка: контакт похож на телефон (10-11 цифр) или email."""
    if not contact or not contact.strip():
        return False
    value = contact.strip()
    if _EMAIL_RE.match(value):
        return True
    digit_count = len(_PHONE_DIGITS_RE.findall(value))
    return 10 <= digit_count <= 11


def read_knowledge_file(filename: str) -> str:
    """Читает файл строго внутри knowledge/. Отклоняет выход за пределы папки."""
    if not filename or not isinstance(filename, str):
        return "Ошибка: не указано имя файла."

    candidate = (KNOWLEDGE_DIR / filename).resolve()

    try:
        candidate.relative_to(KNOWLEDGE_DIR)
    except ValueError:
        return "Ошибка: доступ запрещён — файл вне базы знаний."

    if not candidate.is_file():
        return "Ошибка: файл не найден в базе знаний."

    return candidate.read_text(encoding="utf-8")


def search_knowledge(query: str) -> list[dict]:
    """Ищет фрагменты, содержащие query (без учёта регистра), по всем файлам knowledge/."""
    if not query or not query.strip():
        return []

    needle = query.strip().lower()
    results = []

    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        content = read_knowledge_file(path.name)
        if content.startswith("Ошибка:"):
            continue
        for block in content.split("\n\n"):
            if needle in block.lower():
                results.append({"file": path.name, "excerpt": block.strip()})

    return results


def prepare_lead_draft(
    service: str,
    contact: str | None,
    problem_text: str,
    agent_summary: str,
    missing_info: str | None = None,
) -> dict:
    """Формирует черновик заявки без сохранения в БД. Отклоняет явно невалидный контакт."""
    if not looks_like_contact(contact):
        return {
            "error": "invalid_contact",
            "message": (
                "Контакт не похож на телефон или email. Попроси пользователя прислать "
                "настоящий номер телефона, email или ссылку на мессенджер."
            ),
        }

    return {
        "service": service,
        "contact": contact,
        "problem_text": problem_text,
        "agent_summary": agent_summary,
        "missing_info": missing_info,
        "status": "draft",
    }


def save_confirmed_lead(
    session_id: str,
    service: str,
    contact: str,
    problem_text: str,
    agent_summary: str,
    missing_info: str | None = None,
) -> dict:
    """Сохраняет подтверждённую пользователем заявку от ИИ-консультанта."""
    db.save_lead(
        session_id=session_id,
        source="ai_consultant",
        service=service,
        contact=contact,
        problem_text=problem_text,
        agent_summary=agent_summary,
        missing_info=missing_info,
        status="new",
    )
    return {"status": "saved"}
