from __future__ import annotations


def render_agent_demo_page() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>pr_agents Agent Demo</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f3ef;
      --shell: #ffffff;
      --sidebar: #f0ece5;
      --panel: #ffffff;
      --ink: #171717;
      --muted: #6a6a6a;
      --line: #e6e0d7;
      --accent: #111111;
      --accent-soft: #ece8e1;
      --assistant: #ffffff;
      --user: #f4f0e9;
      --system: #faf7f2;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: radial-gradient(circle at top, #faf7f1 0%, #f2ede6 52%, #ece5dc 100%);
      color: var(--ink);
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      height: 100vh;
      overflow: hidden;
    }
    .app {
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
      height: 100vh;
      overflow: hidden;
    }
    .sidebar {
      background: linear-gradient(180deg, #f2eee7 0%, #ece7de 100%);
      border-right: 1px solid var(--line);
      padding: 18px 14px;
      display: flex;
      flex-direction: column;
      gap: 14px;
      min-height: 0;
      overflow: hidden;
    }
    .brand {
      padding: 10px 10px 2px;
    }
    .brand h1 {
      margin: 0;
      font-size: 18px;
      font-weight: 650;
      letter-spacing: -0.02em;
    }
    .brand p {
      margin: 6px 0 0;
      font-size: 13px;
      color: var(--muted);
      line-height: 1.4;
    }
    .sidebar-actions {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .button {
      border: none;
      border-radius: 14px;
      padding: 11px 14px;
      cursor: pointer;
      font: inherit;
      transition: transform 120ms ease, background 120ms ease;
    }
    .button:hover { transform: translateY(-1px); }
    .button.primary {
      background: var(--accent);
      color: #fff;
      font-weight: 600;
    }
    .button.secondary {
      background: #fff;
      color: var(--ink);
      border: 1px solid var(--line);
    }
    .button.ghost {
      background: var(--accent-soft);
      color: var(--ink);
    }
    .sidebar-section {
      display: flex;
      flex-direction: column;
      gap: 10px;
      min-height: 0;
      flex: 1 1 auto;
    }
    .sidebar-title {
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      padding: 0 8px;
    }
    .session-list {
      display: flex;
      flex-direction: column;
      gap: 6px;
      overflow: auto;
      padding-right: 4px;
      min-height: 0;
      flex: 1 1 auto;
    }
    .session-item {
      background: transparent;
      border: 1px solid transparent;
      border-radius: 14px;
      text-align: left;
      padding: 12px;
      cursor: pointer;
    }
    .session-item.active {
      background: #fff;
      border-color: var(--line);
      box-shadow: 0 8px 24px rgba(24, 19, 12, 0.05);
    }
    .session-name {
      display: block;
      font-size: 14px;
      font-weight: 600;
      color: var(--ink);
      margin-bottom: 3px;
    }
    .session-meta {
      display: block;
      font-size: 12px;
      color: var(--muted);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .main {
      min-width: 0;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      background: rgba(255,255,255,0.42);
      backdrop-filter: blur(8px);
      height: 100vh;
      overflow: hidden;
    }
    .topbar {
      padding: 18px 24px 14px;
      border-bottom: 1px solid rgba(230, 224, 215, 0.75);
      background: rgba(255,255,255,0.7);
      position: sticky;
      top: 0;
      z-index: 2;
    }
    .topbar h2 {
      margin: 0;
      font-size: 18px;
      font-weight: 650;
      letter-spacing: -0.02em;
    }
    .topbar p {
      margin: 6px 0 0;
      font-size: 13px;
      color: var(--muted);
    }
    .conversation {
      min-width: 0;
      overflow: auto;
      padding: 28px 24px 18px;
    }
    .conversation-inner {
      max-width: 860px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }
    .empty {
      border: 1px dashed var(--line);
      border-radius: 20px;
      padding: 24px;
      color: var(--muted);
      background: rgba(255,255,255,0.6);
      line-height: 1.6;
    }
    .message-row {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .message-row.user { align-items: flex-end; }
    .message-row.assistant, .message-row.tool { align-items: flex-start; }
    .message-card {
      max-width: min(760px, 100%);
      border-radius: 22px;
      border: 1px solid var(--line);
      padding: 16px 18px;
      background: var(--assistant);
      box-shadow: 0 14px 34px rgba(22, 18, 14, 0.05);
    }
    .message-row.user .message-card {
      background: var(--user);
    }
    .message-label {
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 7px;
    }
    .message-content {
      white-space: pre-wrap;
      line-height: 1.65;
      font-size: 15px;
      color: var(--ink);
    }
    .detail-card {
      width: min(760px, 100%);
      border: 1px solid var(--line);
      border-radius: 18px;
      background: var(--system);
      overflow: hidden;
    }
    .detail-card summary {
      list-style: none;
      cursor: pointer;
      padding: 14px 16px;
      font-size: 13px;
      color: var(--muted);
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
    }
    .detail-card summary::-webkit-details-marker { display:none; }
    .detail-body {
      padding: 0 16px 16px;
      display: grid;
      gap: 8px;
    }
    .detail-line {
      font-size: 13px;
      color: var(--ink);
      line-height: 1.5;
      word-break: break-word;
    }
    .composer-shell {
      padding: 16px 24px 22px;
      border-top: 1px solid rgba(230, 224, 215, 0.75);
      background: linear-gradient(180deg, rgba(245,243,239,0.3), rgba(255,255,255,0.94));
      position: sticky;
      bottom: 0;
    }
    .composer {
      max-width: 860px;
      margin: 0 auto;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: 0 20px 44px rgba(28, 23, 17, 0.08);
      padding: 14px 14px 12px;
    }
    .composer-hint {
      font-size: 12px;
      color: var(--muted);
      margin: 0 4px 10px;
    }
    .composer textarea {
      width: 100%;
      border: none;
      resize: none;
      min-height: 80px;
      max-height: 220px;
      outline: none;
      font: inherit;
      color: var(--ink);
      line-height: 1.55;
      background: transparent;
    }
    .composer-footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-top: 8px;
      flex-wrap: wrap;
    }
    .quick-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .chip {
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fff;
      padding: 8px 12px;
      font-size: 13px;
      cursor: pointer;
      color: var(--ink);
    }
    .status {
      font-size: 13px;
      color: var(--muted);
      margin-left: 4px;
    }
    .send-button {
      border-radius: 999px;
      background: var(--accent);
      color: #fff;
      padding: 10px 16px;
      border: none;
      font: inherit;
      cursor: pointer;
      font-weight: 600;
    }
    .send-button[disabled] { opacity: 0.6; cursor: default; }
    @media (max-width: 900px) {
      .app { grid-template-columns: 1fr; }
      body { height: auto; overflow: auto; }
      .app { height: auto; overflow: visible; }
      .sidebar { border-right: none; border-bottom: 1px solid var(--line); overflow: visible; }
      .main { height: auto; overflow: visible; }
      .conversation { padding: 18px 14px 14px; }
      .topbar, .composer-shell { padding-left: 14px; padding-right: 14px; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="brand">
        <h1>pr_agents</h1>
        <p>Chat with the analysis agent instead of filling backend parameters by hand.</p>
      </div>
      <div class="sidebar-actions">
        <button class="button primary" id="new-session">New chat</button>
        <button class="button ghost" id="run-demo">Run A_DEMO</button>
      </div>
      <section class="sidebar-section">
        <div class="sidebar-title">Conversations</div>
        <div class="session-list" id="session-list"></div>
      </section>
    </aside>
    <main class="main">
      <header class="topbar">
        <h2>Agent Workspace</h2>
        <p id="session-title">Start a conversation and ask the agent to analyze demo data.</p>
      </header>
      <section class="conversation" id="conversation">
        <div class="conversation-inner" id="messages">
          <div class="empty">
            Use the chat composer below or click <strong>Run A_DEMO</strong>.
            The agent will explain its plan, execute a tool, and return a report in the same conversation.
          </div>
        </div>
      </section>
      <footer class="composer-shell">
        <div class="composer">
          <p class="composer-hint">Try: Please use A_DEMO file data to generate a scientific plot and report.</p>
          <textarea id="prompt" placeholder="Message the agent. Press Enter to send, Shift+Enter for a new line."></textarea>
          <div class="composer-footer">
            <div>
              <div class="quick-actions">
                <button class="chip" id="demo-chip">Run A_DEMO</button>
                <button class="chip" id="report-chip">Show latest report</button>
              </div>
              <div class="status" id="status">Creating session...</div>
            </div>
            <button class="send-button" id="send-message">Send</button>
          </div>
        </div>
      </footer>
    </main>
  </div>
  <script>
    const STORAGE_KEY = 'pr_agents_agent_sessions';
    const ACTIVE_SESSION_KEY = 'pr_agents_active_session';
    let sessionId = null;
    let sessions = [];

    function escapeHtml(value) {
      return String(value).replace(/[&<>"]/g, function (ch) {
        return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[ch];
      });
    }

    function truncate(value, size) {
      if (!value) return 'New conversation';
      return value.length > size ? value.slice(0, size - 1) + '…' : value;
    }

    function loadStoredSessions() {
      try {
        const raw = window.localStorage.getItem(STORAGE_KEY);
        sessions = raw ? JSON.parse(raw) : [];
      } catch (_err) {
        sessions = [];
      }
    }

    function saveStoredSessions() {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
    }

    function saveActiveSession() {
      if (sessionId) {
        window.localStorage.setItem(ACTIVE_SESSION_KEY, sessionId);
      }
    }

    function upsertSessionMeta(id, title) {
      const existing = sessions.find(function (item) { return item.session_id === id; });
      if (existing) {
        existing.title = title || existing.title;
      } else {
        sessions.unshift({ session_id: id, title: title || 'New conversation' });
      }
      saveStoredSessions();
      renderSessionList();
    }

    function renderSessionList() {
      const container = document.getElementById('session-list');
      if (!sessions.length) {
        container.innerHTML = '<div class="session-item active"><span class="session-name">New conversation</span><span class="session-meta">No previous sessions yet</span></div>';
        return;
      }
      container.innerHTML = sessions.map(function (item) {
        const active = item.session_id === sessionId ? ' active' : '';
        return '<button class="session-item' + active + '" data-session-id="' + escapeHtml(item.session_id) + '">' +
          '<span class="session-name">' + escapeHtml(truncate(item.title || 'New conversation', 30)) + '</span>' +
          '<span class="session-meta">' + escapeHtml(item.session_id) + '</span>' +
          '</button>';
      }).join('');
      Array.from(container.querySelectorAll('[data-session-id]')).forEach(function (button) {
        button.addEventListener('click', async function () {
          sessionId = this.getAttribute('data-session-id');
          saveActiveSession();
          document.getElementById('status').textContent = 'Loading ' + sessionId + '...';
          renderSessionList();
          await refreshSession();
        });
      });
    }

    function renderMessages(messages) {
      const container = document.getElementById('messages');
      if (!messages.length) {
        container.innerHTML = '<div class="empty">Start with a prompt or click <strong>Run A_DEMO</strong>.</div>';
        return;
      }
      container.innerHTML = messages.map(function (message) {
        if (message.message_type === 'plan' || message.message_type === 'tool_call' || message.message_type === 'tool_result') {
          const title = message.message_type === 'plan'
            ? 'Execution plan'
            : (message.message_type === 'tool_call' ? 'Tool call' : 'Tool result');
          const metadataLines = [];
          if (message.metadata && message.metadata.task_id) metadataLines.push('task=' + message.metadata.task_id);
          if (message.metadata && message.metadata.chart_type) metadataLines.push('chart=' + message.metadata.chart_type);
          if (message.metadata && message.metadata.business_code) metadataLines.push('business=' + message.metadata.business_code);
          return '<div class="message-row tool">' +
            '<details class="detail-card"' + (message.message_type === 'plan' ? ' open' : '') + '>' +
            '<summary><span>' + escapeHtml(title) + '</span><span>' + escapeHtml(metadataLines.join(' · ') || 'details') + '</span></summary>' +
            '<div class="detail-body">' +
              '<div class="detail-line">' + escapeHtml(message.content) + '</div>' +
            '</div>' +
            '</details>' +
          '</div>';
        }

        const roleLabel = message.role === 'user' ? 'You' : 'Agent';
        return '<div class="message-row ' + message.role + '">' +
          '<article class="message-card">' +
            '<div class="message-label">' + escapeHtml(roleLabel) + '</div>' +
            '<div class="message-content">' + escapeHtml(message.content) + '</div>' +
          '</article>' +
        '</div>';
      }).join('');
      const conversation = document.getElementById('conversation');
      conversation.scrollTop = conversation.scrollHeight;
    }

    function deriveTitle(messages) {
      const firstUser = messages.find(function (message) { return message.role === 'user'; });
      return firstUser ? truncate(firstUser.content, 42) : 'New conversation';
    }

    async function createSession() {
      const status = document.getElementById('status');
      status.textContent = 'Creating session...';
      const response = await fetch('/api/v1/agent/sessions', { method: 'POST' });
      const payload = await response.json();
      sessionId = payload.session_id;
      saveActiveSession();
      upsertSessionMeta(sessionId, 'New conversation');
      document.getElementById('session-title').textContent = sessionId;
      status.textContent = 'Session ready.';
      await refreshSession();
    }

    async function refreshSession() {
      if (!sessionId) return;
      const response = await fetch('/api/v1/agent/sessions/' + sessionId);
      const payload = await response.json();
      const title = deriveTitle(payload.messages);
      sessionId = payload.session_id;
      saveActiveSession();
      upsertSessionMeta(sessionId, title);
      document.getElementById('session-title').textContent = title + ' · ' + sessionId;
      renderMessages(payload.messages);
      document.getElementById('status').textContent = 'Ready.';
    }

    async function sendMessage(content) {
      const trimmed = (content || '').trim();
      if (!trimmed) return;
      const prompt = document.getElementById('prompt');
      if (!sessionId) {
        await createSession();
      }
      document.getElementById('status').textContent = 'Agent is thinking...';
      document.getElementById('send-message').disabled = true;
      const response = await fetch('/api/v1/agent/sessions/' + sessionId + '/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: trimmed })
      });
      const payload = await response.json();
      const title = deriveTitle(payload.messages);
      upsertSessionMeta(sessionId, title);
      document.getElementById('session-title').textContent = title + ' · ' + sessionId;
      renderMessages(payload.messages);
      document.getElementById('status').textContent = 'Completed.';
      document.getElementById('send-message').disabled = false;
      prompt.value = '';
      prompt.focus();
    }

    function fillPrompt(value) {
      const prompt = document.getElementById('prompt');
      prompt.value = value;
      prompt.focus();
    }

    document.getElementById('new-session').addEventListener('click', async function () {
      await createSession();
    });

    document.getElementById('run-demo').addEventListener('click', async function () {
      const prompt = 'Please use A_DEMO file data to generate a scientific plot and report.';
      fillPrompt(prompt);
      await sendMessage(prompt);
    });

    document.getElementById('demo-chip').addEventListener('click', function () {
      fillPrompt('Please use A_DEMO file data to generate a scientific plot and report.');
    });

    document.getElementById('report-chip').addEventListener('click', function () {
      fillPrompt('Show me the report again.');
    });

    document.getElementById('send-message').addEventListener('click', async function () {
      await sendMessage(document.getElementById('prompt').value);
    });

    document.getElementById('prompt').addEventListener('keydown', async function (event) {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        await sendMessage(event.target.value);
      }
    });

    loadStoredSessions();
    renderSessionList();
    const rememberedSession = window.localStorage.getItem(ACTIVE_SESSION_KEY);
    if (rememberedSession) {
      sessionId = rememberedSession;
      renderSessionList();
      refreshSession().catch(function () {
        createSession();
      });
    } else {
      createSession();
    }
  </script>
</body>
</html>"""
