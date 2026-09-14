const historyEl = document.getElementById("history");
const menuEl = document.getElementById("menu");
const actionsEl = document.getElementById("actions");
const formEl = document.getElementById("input-form");
const inputEl = document.getElementById("input-text");

const MAIN_MENU = ["Услуги", "FAQ", "Оставить заявку", "ИИ-консультант", "Обратная связь"];

function getSessionId() {
  let sessionId = localStorage.getItem("session_id");
  if (!sessionId) {
    sessionId = Date.now().toString(36) + Math.random().toString(36).slice(2);
    localStorage.setItem("session_id", sessionId);
  }
  return sessionId;
}

const sessionId = getSessionId();

function addMessage(text, sender) {
  const el = document.createElement("div");
  el.className = "message message--" + sender;
  if (sender === "bot") {
    el.innerHTML = marked.parse(text);
  } else {
    el.textContent = text;
  }
  historyEl.appendChild(el);
  el.scrollIntoView({ block: "start" });
}

function renderButtons(container, items) {
  container.innerHTML = "";
  (items || []).forEach((label) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = label;
    btn.addEventListener("click", () => sendMessage(label));
    container.appendChild(btn);
  });
}

async function sendMessage(text) {
  if (!text) return;
  addMessage(text, "user");

  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, text }),
  });

  const data = await response.json();
  addMessage(data.text, "bot");
  // data.menu — контекстные действия текущего шага (например черновик заявки),
  // главное меню отдельно и остаётся видимым всегда (см. renderButtons(menuEl, MAIN_MENU) ниже).
  renderButtons(actionsEl, data.menu);
}

formEl.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = inputEl.value.trim();
  inputEl.value = "";
  sendMessage(text);
});

addMessage(
  "Здравствуйте! Я чат-консультант салона красоты. Выберите пункт меню или напишите вопрос.",
  "bot"
);
renderButtons(menuEl, MAIN_MENU);
