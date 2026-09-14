import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import bot_flow
import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chatbot")

BASE_DIR = Path(__file__).resolve().parent
INTERFACE_DIR = BASE_DIR / "interface"

app = FastAPI()
db.init_db()


class ChatRequest(BaseModel):
    session_id: str
    text: str


@app.post("/api/chat")
def chat(payload: ChatRequest) -> dict:
    logger.info("chat message received session=%s len=%d", payload.session_id, len(payload.text))
    return bot_flow.handle_message(payload.session_id, payload.text)


app.mount("/static", StaticFiles(directory=INTERFACE_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(INTERFACE_DIR / "index.html")
