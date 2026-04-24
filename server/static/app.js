const $ = (s) => document.querySelector(s);
const messagesEl = $("#messages");
const promptEl = $("#prompt");
const sendBtn = $("#send-btn");
const interruptBtn = $("#interrupt-btn");
const statusEl = $("#status");
const clientNameEl = $("#client-name");
const skillsEl = $("#skills");

clientNameEl.value = localStorage.getItem("client_name") || "";
clientNameEl.addEventListener("input", () => {
  localStorage.setItem("client_name", clientNameEl.value);
});

const toolIcon = (name) => {
  switch (name) {
    case "Read": return "📖";
    case "Write": return "✏️";
    case "Edit": return "✂️";
    case "Bash": return "💻";
    case "Glob": return "🔍";
    case "Grep": return "🔎";
    case "WebFetch": return "🌐";
    default: return "🔧";
  }
};

function addMessage(role, content) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  const roleLabel = document.createElement("div");
  roleLabel.className = "role";
  roleLabel.textContent = role === "user" ? "나" : "Claude";
  div.appendChild(roleLabel);
  const body = document.createElement("div");
  body.className = "msg-text";
  body.textContent = content;
  div.appendChild(body);
  messagesEl.appendChild(div);
  scrollBottom();
  return body;
}

function addSystemNote(text, isError = false) {
  const div = document.createElement("div");
  div.className = "system-note" + (isError ? " error" : "");
  div.textContent = text;
  messagesEl.appendChild(div);
  scrollBottom();
}

function addToolUse(name, summary, isError = false) {
  const div = document.createElement("div");
  div.className = "tool-use" + (isError ? " error" : "");
  div.textContent = `${toolIcon(name)} ${name}${summary ? ": " + summary : ""}`;
  messagesEl.appendChild(div);
  scrollBottom();
}

function scrollBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function setStatus(kind, text) {
  statusEl.className = `status ${kind}`;
  statusEl.textContent = text;
}

function setBusy(isBusy) {
  sendBtn.disabled = isBusy;
  interruptBtn.disabled = !isBusy;
  promptEl.disabled = isBusy;
}

async function loadSkills() {
  try {
    const res = await fetch("/api/skills");
    const skills = await res.json();
    skillsEl.innerHTML = "";
    for (const s of skills) {
      const btn = document.createElement("button");
      btn.className = "skill-btn";
      btn.type = "button";
      btn.innerHTML = `<span class="name">/${s.name}</span><span class="desc"></span>`;
      btn.querySelector(".desc").textContent = s.description || "";
      btn.addEventListener("click", () => {
        promptEl.value = `/${s.name} `;
        promptEl.focus();
      });
      skillsEl.appendChild(btn);
    }
  } catch (e) {
    skillsEl.textContent = "스킬 목록을 불러오지 못했습니다.";
  }
}

async function pollStatus() {
  try {
    const res = await fetch("/api/status");
    const st = await res.json();
    if (st.busy) {
      setStatus("busy", `🟡 ${st.client_id || "누군가"}님 작업 중`);
    } else {
      setStatus("idle", "🟢 대기 중");
    }
  } catch {}
}

let currentAbort = null;
let currentAssistantEl = null;

async function sendPrompt() {
  const prompt = promptEl.value.trim();
  if (!prompt) return;
  const clientId = (clientNameEl.value || "anonymous").trim() || "anonymous";

  addMessage("user", prompt);
  promptEl.value = "";
  setBusy(true);
  setStatus("busy", "🟡 요청 전송 중…");

  currentAssistantEl = null;
  currentAbort = new AbortController();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, client_id: clientId }),
      signal: currentAbort.signal,
    });
    if (!res.ok) {
      addSystemNote(`HTTP ${res.status}`, true);
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const chunk = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const line = chunk.split("\n").find((l) => l.startsWith("data:"));
        if (!line) continue;
        const payload = line.slice(5).trim();
        if (!payload) continue;
        try {
          const event = JSON.parse(payload);
          handleEvent(event);
        } catch (e) {
          console.error("parse error", e, payload);
        }
      }
    }
  } catch (e) {
    if (e.name !== "AbortError") {
      addSystemNote(`오류: ${e.message}`, true);
    }
  } finally {
    setBusy(false);
    pollStatus();
    currentAbort = null;
    currentAssistantEl = null;
  }
}

function handleEvent(event) {
  switch (event.type) {
    case "start":
      setStatus("busy", `🟡 ${event.client_id}님 작업 중`);
      break;
    case "busy":
      addSystemNote(event.message || "다른 세션이 진행 중입니다.", true);
      break;
    case "assistant":
      renderAssistant(event.blocks || []);
      break;
    case "user_tool_result":
      for (const b of event.blocks || []) {
        if (b.kind === "tool_result" && b.is_error) {
          addToolUse("결과 오류", (b.content || "").slice(0, 120), true);
        }
      }
      break;
    case "system":
      // 조용히 무시
      break;
    case "result":
      if (event.cost_usd != null) {
        addSystemNote(
          `완료 · ${event.num_turns || "?"}턴 · $${event.cost_usd.toFixed(4)}`
        );
      }
      break;
    case "error":
      addSystemNote(event.message || "오류", true);
      break;
    case "done":
      setStatus("idle", "🟢 대기 중");
      break;
  }
}

function renderAssistant(blocks) {
  for (const b of blocks) {
    if (b.kind === "text") {
      if (!currentAssistantEl) {
        currentAssistantEl = addMessage("assistant", "");
      }
      currentAssistantEl.textContent += b.text;
      scrollBottom();
    } else if (b.kind === "tool_use") {
      currentAssistantEl = null;
      addToolUse(b.name, b.summary || "");
    }
  }
}

async function interruptSession() {
  if (currentAbort) currentAbort.abort();
  try {
    await fetch("/api/interrupt", { method: "POST" });
  } catch {}
  addSystemNote("세션 중단 요청을 보냈습니다.");
  setBusy(false);
  pollStatus();
}

$("#compose").addEventListener("submit", (e) => {
  e.preventDefault();
  sendPrompt();
});
promptEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    sendPrompt();
  }
});
interruptBtn.addEventListener("click", interruptSession);

loadSkills();
pollStatus();
setInterval(pollStatus, 5000);
