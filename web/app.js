let authToken = localStorage.getItem("aris_token") || "";
let currentUser = localStorage.getItem("aris_user") || "";
let conversationHistory = [];
let daemonSocket = null;
let deferredPrompt = null;

// ================= INITIALIZATION =================
window.addEventListener("DOMContentLoaded", () => {
  if (authToken) {
    document.getElementById("auth-modal").style.display = "none";
    initSession();
  } else {
    document.getElementById("auth-modal").style.display = "flex";
  }
  connectDaemon();
  setupInstallButton();
});

// ================= AUTHENTICATION =================
document.getElementById("btn-login").addEventListener("click", () => handleAuth("login"));
document.getElementById("btn-register").addEventListener("click", () => handleAuth("register"));
document.getElementById("btn-logout").addEventListener("click", () => {
  localStorage.clear();
  location.reload();
});

async function handleAuth(mode) {
  const uid = document.getElementById("auth-uid").value.trim();
  const pwd = document.getElementById("auth-pwd").value.trim();
  const errBox = document.getElementById("auth-err");
  errBox.textContent = "";

  try {
    const res = await fetch("/api/auth", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: uid, password: pwd, mode: mode })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Authentication failed");

    authToken = data.token;
    currentUser = data.user_id;
    localStorage.setItem("aris_token", authToken);
    localStorage.setItem("aris_user", currentUser);

    document.getElementById("auth-modal").style.display = "none";
    initSession();
  } catch (err) {
    errBox.textContent = err.message;
  }
}

function initSession() {
  document.getElementById("user-badge").textContent = `ID: ${currentUser.toUpperCase()}`;
  loadEcosystemNodes();
}

// ================= ECOSYSTEM NODES (SSO) =================
async function loadEcosystemNodes() {
  const container = document.getElementById("nodes-list");
  try {
    const res = await fetch("/api/sso/nodes", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (!res.ok) throw new Error("Could not fetch nodes");
    const data = await res.json();

    container.innerHTML = "";
    Object.keys(data.nodes).forEach(key => {
      const node = data.nodes[key];
      const card = document.createElement("div");
      card.className = "node-card";
      card.innerHTML = `
        <h4>${node.name} ${node.sso_enabled ? '<span class="badge">SSO</span>' : ''}</h4>
        <p>${node.role}</p>
        <a href="${node.sso_link}" target="_blank" class="node-link">Connect Gateway →</a>
      `;
      container.appendChild(card);
    });
  } catch (e) {
    container.innerHTML = `<div class="error-text">Failed to sync neural nodes.</div>`;
  }
}

// ================= LOCAL DESKTOP DAEMON (WEBSOCKET) =================
function connectDaemon() {
  try {
    daemonSocket = new WebSocket("ws://localhost:8765");
    daemonSocket.onopen = () => {
      const status = document.getElementById("daemon-status");
      status.textContent = "DAEMON: ACTIVE (LOCAL)";
      status.style.color = "#10b981";
      document.getElementById("daemon-banner").style.display = "none";
    };
    daemonSocket.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.output) {
        document.getElementById("term-output").textContent = msg.output;
      }
    };
    daemonSocket.onclose = () => {
      const status = document.getElementById("daemon-status");
      status.textContent = "DAEMON: OFFLINE";
      status.style.color = "#ef4444";
      setTimeout(connectDaemon, 5000);
    };
  } catch (e) {
    console.log("Local Daemon bridge not found.");
  }
}

function triggerApp(appName) {
  if (daemonSocket && daemonSocket.readyState === WebSocket.OPEN) {
    daemonSocket.send(JSON.stringify({ action: "launch_app", payload: { app: appName } }));
  } else {
    alert("Local Daemon offline! Run 'python aris_daemon.py' locally first.");
  }
}

document.getElementById("btn-term-run").addEventListener("click", () => {
  const cmd = document.getElementById("term-cmd").value.trim();
  if (!cmd) return;
  if (daemonSocket && daemonSocket.readyState === WebSocket.OPEN) {
    document.getElementById("term-output").textContent = "Executing...";
    daemonSocket.send(JSON.stringify({ action: "run_command", payload: { command: cmd } }));
  } else {
    alert("Local Daemon offline! Run 'python aris_daemon.py' locally first.");
  }
});

// ================= CHAT, VOICE & MATH RENDERING =================
document.getElementById("btn-send").addEventListener("click", sendPrompt);
document.getElementById("txt-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendPrompt();
});

async function sendPrompt() {
  const input = document.getElementById("txt-input");
  const prompt = input.value.trim();
  if (!prompt) return;

  appendMessage("user", prompt);
  input.value = "";

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ prompt: prompt, history: conversationHistory })
    });
    const data = await res.json();

    document.getElementById("ai-model-tag").textContent = data.model || "ONLINE";
    appendMessage("ai", data.reply);
    
    conversationHistory.push({ role: "user", content: prompt });
    conversationHistory.push({ role: "assistant", content: data.reply });

    if (data.speech) {
      playVoiceOutput(data.speech);
    }
  } catch (e) {
    appendMessage("system", "Neural link transmission failed.");
  }
}

function appendMessage(role, text) {
  const stage = document.getElementById("chat-stage");
  const box = document.createElement("div");
  box.className = `msg ${role}-msg`;
  box.innerHTML = role === "ai" ? `<strong>ARIS:</strong> <div>${text}</div>` : text;
  stage.appendChild(box);
  stage.scrollTop = stage.scrollHeight;

  // Auto-render KaTeX math formulas
  if (window.renderMathInElement) {
    window.renderMathInElement(box, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "$", right: "$", display: false }
      ]
    });
  }
}

async function playVoiceOutput(cleanText) {
  try {
    const res = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: cleanText })
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const audio = new Audio(URL.createObjectURL(blob));
    audio.play();
  } catch (e) {
    console.error("Audio playback error:", e);
  }
}

// ================= INSTALL APP & DESKTOP HOOK =================
function setupInstallButton() {
  const installBtn = document.getElementById("btn-install-app");

  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
  });

  installBtn.addEventListener("click", async () => {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      if (outcome === "accepted") {
        installBtn.style.display = "none";
      }
      deferredPrompt = null;
    } else {
      const confirmDownload = confirm("ARIS CORE Desktop Launcher (.bat) download karna hai?");
      if (confirmDownload) {
        const batContent = `@echo off\r\ntitle ARIS CORE Desktop Daemon\r\necho Starting ARIS Automation Daemon...\r\npython aris_daemon.py\r\npause\r\n`;
        const blob = new Blob([batContent], { type: "application/bat" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "start_aris_daemon.bat";
        a.click();
      }
    }
  });
}
