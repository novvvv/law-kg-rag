const chatEl = document.getElementById("chat");
const formEl = document.getElementById("composer");
const inputEl = document.getElementById("question");
const sendBtn = document.getElementById("send");
const welcomeEl = document.getElementById("welcome");
const citeListEl = document.getElementById("cite-list");
const docListEl = document.getElementById("doc-list");
const pdfInput = document.getElementById("pdf-input");
const uploadZone = document.querySelector(".upload-zone");
const uploadLabel = document.getElementById("upload-label");
const uploadStatus = document.getElementById("upload-status");

let busy = false;

function hideWelcome() {
  if (welcomeEl) welcomeEl.remove();
}

function scrollToBottom() {
  chatEl.scrollTop = chatEl.scrollHeight;
}

function addMessage(role, html) {
  hideWelcome();
  const wrap = document.createElement("div");
  wrap.className = `message ${role}`;
  wrap.innerHTML = html;
  chatEl.appendChild(wrap);
  scrollToBottom();
  return wrap;
}

function addTyping() {
  hideWelcome();
  const wrap = document.createElement("div");
  wrap.className = "message assistant";
  wrap.id = "typing";
  wrap.innerHTML =
    '<div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div>';
  chatEl.appendChild(wrap);
  scrollToBottom();
}

function removeTyping() {
  document.getElementById("typing")?.remove();
}

function escapeHtml(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderSidebar(sources) {
  if (!sources?.length) {
    citeListEl.innerHTML = '<li class="empty">검색 결과가 없습니다</li>';
    docListEl.innerHTML = '<li class="empty">검색 결과가 없습니다</li>';
    return;
  }

  citeListEl.innerHTML = sources
    .map((s) => {
      const ref = s.citation || s.article || "—";
      const hangs = (s.hangs || []).length
        ? (s.hangs || []).join(" · ")
        : s.hang || "항 정보 없음";
      return `<li class="cite-item">
        <span class="cite-ref">${escapeHtml(ref)}</span>
        <span class="cite-meta">${escapeHtml(hangs)} · ${escapeHtml(s.law)}</span>
      </li>`;
    })
    .join("");

  docListEl.innerHTML = sources
    .map(
      (s) => `<li class="doc-item">
        <div class="doc-title">${escapeHtml(s.law)}</div>
        <div class="doc-ref">${escapeHtml(s.citation || s.article || "")}</div>
        <div class="doc-preview">${escapeHtml(s.preview)}</div>
        <div class="doc-score">${Number(s.score).toFixed(3)}</div>
      </li>`
    )
    .join("");
}

async function sendQuestion(question) {
  if (!question.trim() || busy) return;
  busy = true;
  sendBtn.disabled = true;
  inputEl.disabled = true;

  addMessage("user", `<div class="bubble">${escapeHtml(question)}</div>`);
  addTyping();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();
    removeTyping();

    if (!res.ok) {
      addMessage(
        "assistant",
        `<div class="bubble">${escapeHtml(data.detail || "요청에 실패했습니다.")}</div>`
      );
      return;
    }

    renderSidebar(data.sources || []);
    addMessage(
      "assistant",
      `<div class="bubble">${escapeHtml(data.answer)}</div>`
    );
  } catch {
    removeTyping();
    addMessage(
      "assistant",
      `<div class="bubble">서버에 연결할 수 없습니다. 웹 서버가 실행 중인지 확인해 주세요.</div>`
    );
  } finally {
    busy = false;
    sendBtn.disabled = false;
    inputEl.disabled = false;
    inputEl.focus();
  }
}

async function uploadPdf(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    uploadStatus.textContent = "PDF 파일만 업로드할 수 있습니다.";
    uploadStatus.className = "upload-status err";
    return;
  }

  uploadStatus.textContent = "업로드 · 인덱싱 중…";
  uploadStatus.className = "upload-status";
  uploadLabel.textContent = file.name;

  const body = new FormData();
  body.append("file", file);

  try {
    const res = await fetch("/api/upload-pdf", { method: "POST", body });
    const data = await res.json();
    if (!res.ok) {
      uploadStatus.textContent = data.detail || "업로드 실패";
      uploadStatus.className = "upload-status err";
      return;
    }
    uploadStatus.textContent = data.message || "업로드 완료";
    uploadStatus.className = "upload-status ok";
  } catch {
    uploadStatus.textContent = "업로드에 실패했습니다.";
    uploadStatus.className = "upload-status err";
  }
}

formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  const q = inputEl.value.trim();
  if (!q) return;
  inputEl.value = "";
  sendQuestion(q);
});

document.querySelectorAll(".suggestion").forEach((btn) => {
  btn.addEventListener("click", () => sendQuestion(btn.textContent.trim()));
});

pdfInput.addEventListener("change", () => {
  const file = pdfInput.files?.[0];
  uploadPdf(file);
  pdfInput.value = "";
});

["dragenter", "dragover"].forEach((ev) => {
  uploadZone.addEventListener(ev, (e) => {
    e.preventDefault();
    uploadZone.classList.add("dragover");
  });
});

["dragleave", "drop"].forEach((ev) => {
  uploadZone.addEventListener(ev, (e) => {
    e.preventDefault();
    uploadZone.classList.remove("dragover");
  });
});

uploadZone.addEventListener("drop", (e) => {
  const file = e.dataTransfer?.files?.[0];
  uploadPdf(file);
});

inputEl.focus();
