const $ = (selector) => document.querySelector(selector);
const dialog = $("#missionDialog");
let dashboard = null;
let currentMission = null;

const viewTitles = {
  mission: "Mission Control",
  copilot: "Copilot Chat",
  projects: "Projects",
  workflow: "Workflow Map",
  agents: "Specialists",
  knowledge: "Knowledge Graph",
  connectors: "Connectors",
  "ai-settings": "AI & Providers",
  "system-health": "System Health",
  reliability: "Reliability Center",
  "network-health": "Network & Desktop Health",
  "brain-vault": "Obsidian Brain Vault",
  "roadmap": "Roadmap & Progress",
  approvals: "Approval Center",
  mobile: "Mobile Control",
};

let aiosCsrfToken = "";

async function api(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (!["GET", "HEAD", "OPTIONS"].includes(method) && aiosCsrfToken) {
    headers["X-CSRF-Token"] = aiosCsrfToken;
  }

  const response = await fetch(path, {
    ...options,
    credentials: "same-origin",
    headers,
    redirect: "follow",
  });

  const contentType = response.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const payload = isJson ? await response.json() : await response.text();

  if (!isJson && typeof payload === "string" && payload.trim().startsWith("<")) {
    const error = new Error(
      "Cloudflare Access session expired or intercepted this request. Re-authenticate to Cloudflare Access, then try again."
    );
    error.code = "cloudflare_access_html";
    error.status = response.status;
    throw error;
  }

  if (!response.ok) {
    const message = typeof payload === "object"
      ? (payload.detail || payload.message || "Request failed")
      : (payload || `Request failed with status ${response.status}`);
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }

  return payload;
}

function switchView(view) {
  document.querySelectorAll(".app-view").forEach(section => section.classList.remove("active"));
  document.querySelectorAll(".nav-item, .mobile-nav-item").forEach(button => button.classList.remove("active"));

  const section = document.querySelector(`#view-${view}`);
  const button = document.querySelector(`.nav-item[data-view="${view}"]`);
  const mobileButton = document.querySelector(`.mobile-nav-item[data-view="${view}"]`);
  if (!section) return;

  section.classList.add("active");
  if (button) button.classList.add("active");
  if (mobileButton) mobileButton.classList.add("active");
  $("#pageTitle").textContent = viewTitles[view] || "AIOS ONE";
  window.location.hash = view;
}

function renderSpecialists(items) {
  $("#specialistList").innerHTML = items.map(agent => `
    <div class="specialist">
      <div class="avatar">${agent.name.slice(0, 2).toUpperCase()}</div>
      <div><strong>${agent.name}</strong><span>${agent.role}</span></div>
      <span class="agent-state">${agent.mode.toUpperCase()}</span>
    </div>`).join("");

  $("#specialistGrid").innerHTML = items.map(agent => `
    <article class="agent-card">
      <div class="agent-card-head">
        <div class="avatar large">${agent.name.slice(0, 2).toUpperCase()}</div>
        <div><h3>${agent.name}</h3><span>${agent.role}</span></div>
      </div>
      <div class="agent-stats">
        <span>STATUS <b>${agent.status.toUpperCase()}</b></span>
        <span>MODE <b>${agent.mode.toUpperCase()}</b></span>
        <span>MODEL <b>${agent.model}</b></span>
      </div>
      <button class="agent-open" data-agent="${agent.id}">Open specialist</button>
    </article>`).join("");

  document.querySelectorAll(".agent-open").forEach(button => {
    button.addEventListener("click", () => {
      switchView('workflow');
      const agent = dashboard?.specialists?.find(item => item.id === button.dataset.agent);
      setBrainControlState(currentMission, `${agent?.name || button.dataset.agent} is operational and will execute when assigned by Copilot.`);
    });
  });
}

let connectorItems = [];

function connectorCard(connector) {
  const state = connector.state.replaceAll("-", " ").toUpperCase();
  const docsButton = connector.docs_url
    ? `<button class="connector-docs" data-url="${connector.docs_url}">Docs</button>`
    : "";
  return `
    <article class="connector-card" data-kind="${connector.kind}" data-search="${(connector.name + " " + connector.kind + " " + (connector.description || "")).toLowerCase()}">
      <div class="connector-icon">${connector.name.slice(0,2).toUpperCase()}</div>
      <div>
        <h3>${connector.name}</h3>
        <p>${connector.kind.toUpperCase()} CONNECTOR</p>
      </div>
      <span class="connector-state">${state}</span>
      ${connector.description ? `<p class="connector-description">${connector.description}</p>` : ""}
      <div class="connector-card-actions">
        ${docsButton}
        <button class="connector-action" data-connector="${connector.id}">
          ${connector.state === "available" ? "Open" : "Configure"}
        </button>
      </div>
    </article>`;
}

function applyConnectorFilters() {
  const query = ($("#connectorSearch")?.value || "").trim().toLowerCase();
  const type = $("#connectorFilter")?.value || "all";
  const filtered = connectorItems.filter(connector => {
    const searchable = `${connector.name} ${connector.kind} ${connector.description || ""}`.toLowerCase();
    return (!query || searchable.includes(query)) && (type === "all" || connector.kind === type);
  });
  $("#connectorGrid").innerHTML = filtered.length
    ? filtered.map(connectorCard).join("")
    : `<div class="empty-approval"><h3>No connector found</h3><p>Try another search or add a new connector.</p></div>`;
  wireConnectorButtons();
}

function wireConnectorButtons() {
  document.querySelectorAll(".connector-action").forEach(button => {
    button.addEventListener("click", () => {
      const item = connectorItems.find(connector => connector.id === button.dataset.connector);
      alert(`${item?.name || button.dataset.connector} configuration will use the Connector Gateway and approval policy.`);
    });
  });
  document.querySelectorAll(".connector-docs, .library-link").forEach(button => {
    button.addEventListener("click", () => window.open(button.dataset.url, "_blank", "noopener,noreferrer"));
  });
}

function renderConnectors(items) {
  const defaults = [
    ...items,
    {id:"mcp-github", name:"GitHub MCP", state:"ready-to-configure", kind:"mcp", docs_url:"https://github.com/modelcontextprotocol/servers", description:"Repository, issue, pull request, and code-context tools through MCP."},
    {id:"mcp-filesystem", name:"Filesystem MCP", state:"local-only", kind:"mcp", docs_url:"https://github.com/modelcontextprotocol/servers", description:"Scoped local file access for approved folders."},
    {id:"mcp-postgres", name:"PostgreSQL MCP", state:"ready-to-configure", kind:"mcp", docs_url:"https://github.com/modelcontextprotocol/servers", description:"Read and inspect approved PostgreSQL databases."},
  ];
  const saved = JSON.parse(localStorage.getItem("aios-connectors") || "[]");
  connectorItems = [...defaults, ...saved];

  $("#connectorList").innerHTML = connectorItems.slice(0, 6).map(connector => `
    <div class="connector"><b>${connector.name}</b><span>${connector.state.replaceAll("-", " ").toUpperCase()}</span></div>
  `).join("");

  applyConnectorFilters();
}


function setBrainControlState(mission, message = "") {
  const runButton = $("#runNextBrain");
  const fullTeamButton = $("#runFullTeam");
  const approveButton = $("#approveBrainStep");
  const status = $("#brainActionStatus");
  const hasMission = Boolean(mission && mission.id);
  const waiting = Boolean(mission?.workflow?.some(step => step.status === "waiting-approval"));
  const complete = mission?.status === "complete";

  if (runButton) runButton.disabled = !hasMission || waiting || complete;
  if (fullTeamButton) fullTeamButton.disabled = !hasMission || waiting || complete;
  if (approveButton) approveButton.disabled = !hasMission || !waiting;

  if (status) {
    status.textContent = message || (!hasMission
      ? "Create a mission first."
      : complete
        ? "Mission complete. All specialist brains finished."
        : waiting
          ? "A specialist is waiting for human approval."
          : `Mission ${mission.id} is ready. Run the next specialist brain.`);
    status.dataset.state = waiting ? "warning" : complete ? "success" : hasMission ? "ready" : "idle";
  }
}

function renderBrainResults(results = []) {
  const target = $("#brainResults");
  if (!target) return;
  if (!results.length) {
    target.innerHTML = `<div class="empty-approval"><h3>No brain result yet</h3><p>Run the next brain to delegate the active workflow step.</p></div>`;
    return;
  }
  target.innerHTML = [...results].reverse().map(result => `
    <article class="brain-result-card">
      <div class="brain-result-head">
        <div><p class="eyebrow">${result.specialist_id.toUpperCase()} BRAIN</p><h3>${result.summary}</h3></div>
        <span class="confidence">${result.confidence}% · ${(result.provider || "local").toUpperCase()}</span>
      </div>
      <ul>${result.findings.map(item => `<li>${item}</li>`).join("")}</ul>
      <div class="brain-result-foot">
        <span>${result.status.toUpperCase()} · ${result.model || "fallback"}</span>
        <span>${result.next_action}</span>
      </div>
    </article>
  `).join("");
}

function workflowMarkup(mission) {
  if (!mission) {
    return `<div class="empty-state"><div class="radar"></div><h3>No active mission</h3><p>Create a mission to populate this workflow.</p></div>`;
  }
  return mission.workflow.map((node, index) => `
    <div class="node ${node.status}">
      <div class="node-top"><span>0${index + 1}</span><span>${node.status.toUpperCase()}</span></div>
      <h3>${node.label}</h3>
      <div class="node-meta"><span>${node.agent}</span><span>${node.location}</span></div>
    </div>
  `).join("");
}

function renderWorkflow(mission) {
  currentMission = mission;
  $("#workflowStatus").textContent = mission.status.toUpperCase();

  const compact = $("#workflow");
  compact.className = "workflow active";
  compact.innerHTML = workflowMarkup(mission);

  const full = $("#workflowFull");
  full.className = "workflow active full-map";
  full.innerHTML = workflowMarkup(mission);

  $("#missionCount").textContent = String(Math.max(dashboard?.missions?.length || 0, 1));
  $("#artifactList").innerHTML = `
    <div class="artifact"><span>IN</span><p>${mission.objective}</p></div>
    ${mission.evidence.map(item => `<div class="artifact"><span>✓</span><p>${item.label}</p></div>`).join("")}
  `;
  renderBrainResults(mission.brain_results || []);
  setBrainControlState(mission);
  localStorage.setItem("aios-active-mission", mission.id);
}

async function loadApprovals() {
  try {
    const approvals = await api("/approvals/default");
    $("#approvalCount").textContent = approvals.length;
    if (!approvals.length) return;

    $("#approvalList").innerHTML = approvals.map(item => `
      <article class="approval-card">
        <div><p class="eyebrow">PENDING ACTION</p><h3>${item.tool_name}</h3><pre>${JSON.stringify(item.tool_input, null, 2)}</pre></div>
        <div class="approval-actions">
          <button data-id="${item.id}" data-decision="false">Reject</button>
          <button class="primary" data-id="${item.id}" data-decision="true">Approve</button>
        </div>
      </article>
    `).join("");
  } catch (error) {
    console.warn("Approvals unavailable", error);
  }
}

async function loadDashboard() {
  dashboard = await api("/api/dashboard");
  $("#agentCount").textContent = dashboard.metrics.online_agents;
  $("#missionCount").textContent = dashboard.metrics.active_missions;
  $("#approvalCount").textContent = dashboard.metrics.pending_approvals;
  renderSpecialists(dashboard.specialists);
  renderConnectors(dashboard.connectors);
  if (dashboard.missions.length) renderWorkflow(dashboard.missions.at(-1));
  else {
    $("#workflowFull").innerHTML = workflowMarkup(null);
    setBrainControlState(null);
  }
  await loadApprovals();
}

function openMission(prefill = "") {
  dialog.showModal();
  if (prefill) {
    dialog.querySelector('[name="title"]').value = prefill.slice(0, 72);
    dialog.querySelector('[name="objective"]').value = prefill;
  }
}

$("#newMissionBtn").addEventListener("click", () => openMission());
$("#workflowNewMission").addEventListener("click", () => openMission());
$("#quickLaunch").addEventListener("click", () => {
  const value = $("#quickObjective").value.trim();
  if (value) openMission(value);
});
$("#closeDialog").addEventListener("click", () => dialog.close());
$("#cancelDialog").addEventListener("click", () => dialog.close());

$("#missionForm").addEventListener("submit", async (event) => {
  event.preventDefault();

  const missionForm = event.currentTarget;
  const submit = event.submitter;

  submit.disabled = true;
  submit.textContent = "Planningâ€¦";

  try {
    const formData = new FormData(missionForm);
    const mission = await api("/api/missions", {
      method: "POST",
      body: JSON.stringify(Object.fromEntries(formData.entries())),
    });

    renderWorkflow(mission);
    missionForm.reset();
    dialog.close();
    switchView("workflow");
  } catch (error) {
    console.error(error);
    alert(error.message);
  } finally {
    submit.disabled = false;
    submit.textContent = "Start mission";
  }
});

document.querySelectorAll(".nav-item").forEach(button => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});


document.querySelectorAll(".mobile-nav-item[data-view]").forEach(button => {
  button.addEventListener("click", () => {
    switchView(button.dataset.view);
    document.querySelector("#mobileMoreMenu")?.classList.remove("open");
  });
});

document.querySelector("#mobileMoreBtn")?.addEventListener("click", () => {
  document.querySelector("#mobileMoreMenu")?.classList.toggle("open");
});

document.querySelectorAll("#mobileMoreMenu [data-view]").forEach(button => {
  button.addEventListener("click", () => {
    switchView(button.dataset.view);
    document.querySelector("#mobileMoreMenu")?.classList.remove("open");
  });
});

document.addEventListener("click", event => {
  const menu = document.querySelector("#mobileMoreMenu");
  const moreButton = document.querySelector("#mobileMoreBtn");
  if (!menu || !menu.classList.contains("open")) return;
  if (!menu.contains(event.target) && !moreButton?.contains(event.target)) {
    menu.classList.remove("open");
  }
});



let budgetPayload = null;

function formatMoney(amount, currency = "USD") {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(Number(amount || 0));
}

function showBrowserBudgetNotification(message) {
  if (!("Notification" in window)) return;
  if (Notification.permission === "granted") {
    new Notification("AIOS Budget", { body: message });
  }
}

function renderBudget(payload) {
  budgetPayload = payload;
  const { state, summary, alerts } = payload;
  $("#budgetLimit").textContent = formatMoney(summary.limit_usd);
  $("#budgetPaid").textContent = formatMoney(summary.paid_usd);
  $("#budgetPlanned").textContent = formatMoney(summary.planned_usd);
  $("#budgetRemaining").textContent = formatMoney(summary.remaining_usd);
  $("#budgetPercent").textContent = `${summary.used_percent}% used`;

  const settings = state.settings || {};
  $("#monthlyBudgetLimit").value = settings.monthly_limit_usd || 250;
  $("#budgetNotificationEmail").value = settings.notification_email || "";
  $("#browserBudgetNotifications").checked = Boolean(settings.browser_notifications);
  $("#emailBudgetNotifications").checked = Boolean(settings.email_notifications);

  const usage = state.usage || {};
  $("#usageAiCost").value = usage.ai_cost_usd || 0;
  $("#usageInputTokens").value = usage.ai_tokens_input || 0;
  $("#usageOutputTokens").value = usage.ai_tokens_output || 0;
  $("#usageWorkerRequests").value = usage.worker_requests || 0;
  $("#usageStorage").value = usage.storage_gb || 0;
  $("#usageEmailCount").value = usage.email_count || 0;

  $("#budgetAlerts").innerHTML = alerts.length
    ? alerts.map(alert => `<div class="budget-alert ${alert.level}">${alert.message}</div>`).join("")
    : `<div class="budget-alert success">No payment or budget warning is active.</div>`;

  $("#expenseList").innerHTML = (state.expenses || []).map(expense => `
    <article class="expense-row ${expense.status}">
      <div>
        <strong>${expense.vendor}</strong>
        <p>${expense.description}</p>
        <small>${expense.category} · due ${expense.due_date}${expense.recurring ? ` · ${expense.recurrence}` : ""}</small>
      </div>
      <div class="expense-amount">
        <strong>${formatMoney(expense.amount, expense.currency)}</strong>
        <span>${expense.status.toUpperCase()}</span>
        ${expense.status !== "paid" ? `<button data-pay-expense="${expense.id}" class="primary">Mark paid</button>` : ""}
        ${expense.payment_url ? `<a href="${expense.payment_url}" target="_blank" rel="noreferrer">Open payment</a>` : ""}
      </div>
    </article>
  `).join("");

  $("#paymentHistory").innerHTML = (state.payments || []).length
    ? state.payments.slice().reverse().map(payment => `
      <div class="payment-row">
        <div><strong>${payment.vendor}</strong><small>${payment.description}</small></div>
        <div><strong>${formatMoney(payment.amount, payment.currency)}</strong><small>${new Date(payment.paid_at).toLocaleString()}</small></div>
      </div>`).join("")
    : `<p class="muted-copy">No recorded payments yet.</p>`;

  document.querySelectorAll("[data-pay-expense]").forEach(button => {
    button.addEventListener("click", async () => {
      button.disabled = true;
      button.textContent = "Recordingâ€¦";
      try {
        const result = await api(`/api/budget/expenses/${button.dataset.payExpense}/paid`, { method: "POST" });
        showBrowserBudgetNotification(result.notification.message);
        await loadBudget();
      } catch (error) {
        alert(`Payment could not be recorded: ${error.message}`);
      }
    });
  });

  if (settings.browser_notifications && Notification.permission === "granted") {
    alerts.slice(0, 3).forEach(alert => showBrowserBudgetNotification(alert.message));
  }
}

async function loadBudget() {
  try {
    renderBudget(await api("/api/budget"));
  } catch (error) {
    $("#budgetAlerts").innerHTML = `<div class="budget-alert danger">Budget data failed to load: ${error.message}</div>`;
  }
}

$("#openExpenseForm")?.addEventListener("click", () => $("#expenseDialog").showModal());
$("#closeExpenseDialog")?.addEventListener("click", () => $("#expenseDialog").close());
$("#cancelExpenseDialog")?.addEventListener("click", () => $("#expenseDialog").close());

$("#expenseForm")?.addEventListener("submit", async event => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = Object.fromEntries(form.entries());
  payload.amount = Number(payload.amount);
  payload.recurring = form.get("recurring") === "on";
  await api("/api/budget/expenses", { method: "POST", body: JSON.stringify(payload) });
  event.currentTarget.reset();
  $("#expenseDialog").close();
  await loadBudget();
});

$("#saveBudgetSettings")?.addEventListener("click", async () => {
  const payload = {
    monthly_limit_usd: Number($("#monthlyBudgetLimit").value || 250),
    warning_thresholds: [50, 75, 90, 100],
    notification_email: $("#budgetNotificationEmail").value.trim(),
    browser_notifications: $("#browserBudgetNotifications").checked,
    email_notifications: $("#emailBudgetNotifications").checked,
  };
  await api("/api/budget/settings", { method: "POST", body: JSON.stringify(payload) });
  await loadBudget();
});

$("#saveUsage")?.addEventListener("click", async () => {
  const payload = {
    ai_cost_usd: Number($("#usageAiCost").value || 0),
    ai_tokens_input: Number($("#usageInputTokens").value || 0),
    ai_tokens_output: Number($("#usageOutputTokens").value || 0),
    worker_requests: Number($("#usageWorkerRequests").value || 0),
    storage_gb: Number($("#usageStorage").value || 0),
    email_count: Number($("#usageEmailCount").value || 0),
  };
  await api("/api/budget/usage", { method: "POST", body: JSON.stringify(payload) });
  await loadBudget();
});

$("#requestBudgetNotifications")?.addEventListener("click", async () => {
  if (!("Notification" in window)) {
    alert("This browser does not support notifications.");
    return;
  }
  const permission = await Notification.requestPermission();
  alert(`Browser notification permission: ${permission}`);
});

$("#scanBudgetReminders")?.addEventListener("click", async () => {
  const result = await api("/api/budget/scan-reminders", { method: "POST" });
  (result.alerts || []).forEach(alert => showBrowserBudgetNotification(alert.message));
  await loadBudget();
});




const COPILOT_CONVERSATION_KEY = "aios-copilot-conversation-id";
let copilotConversationId =
  localStorage.getItem(COPILOT_CONVERSATION_KEY) ||
  (crypto.randomUUID ? crypto.randomUUID() : `chat-${Date.now()}`);
localStorage.setItem(COPILOT_CONVERSATION_KEY, copilotConversationId);

function escapeChatHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderCopilotMessages(messages) {
  const container = $("#copilotMessages");
  if (!container) return;
  if (!messages?.length) {
    container.innerHTML = `
      <div class="copilot-empty">
        <div class="orb">C</div>
        <h3>Message your AIOS Copilot</h3>
        <p>The provider badge will say OPENAI LIVE when the server can use OPENAI_API_KEY.</p>
      </div>`;
    return;
  }

  container.innerHTML = messages.map(message => `
    <article class="copilot-message ${message.role}">
      <div class="copilot-message-head">
        <strong>${message.role === "assistant" ? "AIOS Copilot" : "You"}</strong>
        <small>${message.created_at ? new Date(message.created_at).toLocaleString() : ""}</small>
      </div>
      ${message.image_url ? `<img class="copilot-input-image" src="${escapeChatHtml(message.image_url)}" alt="Submitted image">` : ""}
      <div class="copilot-message-content">${escapeChatHtml(message.content).replaceAll("\n", "<br>")}</div>
      ${message.role === "assistant" ? `
        <div class="copilot-message-meta">
          <span>${escapeChatHtml(message.provider || "")}</span>
          <span>${escapeChatHtml(message.model || "")}</span>
          <span>${Number(message.input_tokens || 0)} in</span>
          <span>${Number(message.output_tokens || 0)} out</span>
          <span>$${Number(message.estimated_cost_usd || 0).toFixed(6)}</span>
        </div>
        ${message.gateway_error ? `<details><summary>Gateway fallback detail</summary><p>${escapeChatHtml(message.gateway_error)}</p></details>` : ""}
      ` : ""}
    </article>
  `).join("");
  container.scrollTop = container.scrollHeight;
}

async function loadCopilotStatus() {
  const status = await api("/api/copilot/status");
  const dot = $("#copilotProviderDot");
  const label = $("#copilotProviderLabel");
  if (!dot || !label) return;
  dot.dataset.live = String(status.live);
  label.textContent = status.live
    ? `${String(status.provider).toUpperCase()} LIVE · ${status.default_model}`
    : "DETERMINISTIC FALLBACK · key unavailable";
}

async function loadCopilotConversation() {
  const conversation = await api(`/api/copilot/conversations/${copilotConversationId}`);
  renderCopilotMessages(conversation.messages || []);
}

$("#copilotChatForm")?.addEventListener("submit", async event => {
  event.preventDefault();
  const input = $("#copilotMessageInput");
  const image = $("#copilotImageUrl");
  const send = $("#sendCopilotMessage");
  const message = input.value.trim();
  if (!message) return;

  const pending = {
    role: "user",
    content: message,
    image_url: image.value.trim() || null,
    created_at: new Date().toISOString(),
  };
  const existing = await api(`/api/copilot/conversations/${copilotConversationId}`);
  renderCopilotMessages([...(existing.messages || []), pending]);

  send.disabled = true;
  send.textContent = "Thinkingâ€¦";
  $("#copilotChatStatus").textContent = "Copilot is using the live model gateway.";

  try {
    const result = await api("/api/copilot/chat", {
      method: "POST",
      body: JSON.stringify({
        conversation_id: copilotConversationId,
        message,
        image_url: image.value.trim() || null,
        model: $("#copilotModel").value,
        preferred_provider: $("#copilotProvider").value || null,
      }),
    });
    input.value = "";
    image.value = "";
    await loadCopilotConversation();
    await loadCopilotStatus();
    await loadBudget();
    $("#copilotChatStatus").textContent = result.provider_status.live
      ? `Live response completed with ${result.provider_status.model}.`
      : "Fallback response returned. Open gateway details in the message.";
  } catch (error) {
    $("#copilotChatStatus").textContent = `Copilot error: ${error.message}`;
  } finally {
    send.disabled = false;
    send.textContent = "Send";
  }
});

$("#newCopilotConversation")?.addEventListener("click", async () => {
  await api(`/api/copilot/conversations/${copilotConversationId}`, { method: "DELETE" });
  copilotConversationId =
    crypto.randomUUID ? crypto.randomUUID() : `chat-${Date.now()}`;
  localStorage.setItem(COPILOT_CONVERSATION_KEY, copilotConversationId);
  renderCopilotMessages([]);
  $("#copilotChatStatus").textContent = "New conversation created.";
});

$("#createMissionFromChat")?.addEventListener("click", () => {
  const message = $("#copilotMessageInput").value.trim();
  if (!message) {
    $("#copilotChatStatus").textContent = "Type the mission objective in the message box first.";
    return;
  }
  $("#quickObjective").value = message;
  switchView("mission");
  dialog.showModal();
  $("#missionObjective").value = message;
});



$("#classifyPmTask")?.addEventListener("click", async () => {
  const task = $("#pmRouteTask").value.trim();
  if (!task) {
    $("#pmRouteOutput").textContent = "Enter a task description first.";
    return;
  }
  try {
    const result = await api("/api/copilot/route-task", {
      method: "POST",
      body: JSON.stringify({
        task_description: task,
        estimated_tokens: Number($("#pmRouteTokens").value || 1500),
        standard_failures: Number($("#pmRouteFailures").value || 0),
        reused_context: $("#pmRouteReuseCache").checked
      })
    });
    $("#pmRouteOutput").textContent = JSON.stringify(result, null, 2);
  } catch (error) {
    $("#pmRouteOutput").textContent = JSON.stringify({error: error.message}, null, 2);
  }
});



function providerStatusBadge(provider) {
  return provider.connected
    ? `<span class="connection-badge connected">CONNECTED</span>`
    : `<span class="connection-badge missing">NOT CONNECTED</span>`;
}

async function loadProviderConnections() {
  const payload = await api("/api/models/providers");
  $("#providerConnectionList").innerHTML = payload.providers.map(provider => `
    <article class="provider-connection-card">
      <div>
        <strong>${provider.name}</strong>
        <small>${provider.env_var || "Built in"}</small>
      </div>
      <div class="provider-connection-actions">
        ${providerStatusBadge(provider)}
        ${provider.api_key_url ? `<a href="${provider.api_key_url}" target="_blank" rel="noreferrer">Get API key</a>` : ""}
        ${provider.models_url ? `<a href="${provider.models_url}" target="_blank" rel="noreferrer">View models</a>` : ""}
      </div>
    </article>
  `).join("");
}

function formatCatalogPrice(value) {
  if (value === "unknown") return "Unknown";
  const number = Number(value || 0);
  if (!Number.isFinite(number)) return String(value);
  return number === 0 ? "Free" : `$${(number * 1000000).toFixed(3)}/M`;
}

async function loadModelCatalog() {
  const params = new URLSearchParams({
    query: $("#modelSearchInput").value.trim(),
    provider: $("#modelProviderFilter").value,
    free_only: String($("#freeModelsOnly").checked),
    limit: "120",
  });
  $("#modelCatalogResults").innerHTML = `<p class="muted-copy">Searching modelsâ€¦</p>`;
  const payload = await api(`/api/models/catalog?${params.toString()}`);
  $("#modelCatalogSource").textContent = `${payload.count} models · ${payload.source}`;
  $("#modelCatalogResults").innerHTML = payload.models.length
    ? payload.models.map(model => `
      <article class="model-catalog-card">
        <div class="model-catalog-card-head">
          <div>
            <strong>${model.name}</strong>
            <code>${model.id}</code>
          </div>
          <span>${model.provider}</span>
        </div>
        <p>${model.description || "No description available."}</p>
        <div class="model-catalog-meta">
          <span>Context: ${Number(model.context_length || 0).toLocaleString()}</span>
          <span>Input: ${formatCatalogPrice(model.prompt_price)}</span>
          <span>Output: ${formatCatalogPrice(model.completion_price)}</span>
          <span>${(model.input_modalities || []).join(", ") || "text"}</span>
        </div>
        <button class="use-model-button" data-use-model="${model.id}">Use in Copilot</button>
      </article>`).join("")
    : `<p class="muted-copy">No matching models found.</p>`;

  document.querySelectorAll("[data-use-model]").forEach(button => {
    button.addEventListener("click", async () => {
      const modelId = button.dataset.useModel;
      const provider = modelId.includes("/") ? modelId.split("/", 1)[0].replace("~", "") : "openrouter";
      const normalizedProvider =
        provider === "anthropic" ? "openrouter" :
        provider === "openai" ? "openrouter" :
        provider === "google" ? "openrouter" :
        provider === "meta-llama" ? "openrouter" :
        provider === "deepseek" ? "openrouter" :
        provider === "qwen" ? "openrouter" :
        provider === "mistralai" ? "openrouter" :
        "openrouter";

      pendingProviderModel = { provider: normalizedProvider, model: modelId };

      await api("/api/settings/providers/model", {
        method: "POST",
        body: JSON.stringify({
          provider: normalizedProvider,
          model: modelId,
        }),
      });

      const settings = await api("/api/settings/providers");
      const providerInfo = settings.providers.find(item => item.id === normalizedProvider);

      switchView("provider-settings");
      await loadSecureProviderSettings();

      if (providerInfo && !providerInfo.connected) {
        openProviderKeyDialog(
          normalizedProvider,
          modelId,
          providerInfo.api_key_url,
          providerInfo.models_url,
        );
      }
    });
  });
}

$("#refreshProviderStatus")?.addEventListener("click", loadProviderConnections);
$("#searchModels")?.addEventListener("click", loadModelCatalog);
$("#modelSearchInput")?.addEventListener("keydown", event => {
  if (event.key === "Enter") loadModelCatalog();
});




async function renderCopilotProviderQuickStatus() {
  const payload = await api("/api/models/providers");
  const container = $("#copilotProviderQuickStatus");
  if (!container) return;

  container.innerHTML = payload.providers
    .filter(provider => provider.id !== "deterministic")
    .map(provider => `
      <span class="quick-provider-chip ${provider.connected ? "connected" : "missing"}">
        ${provider.name}: ${provider.connected ? "CONNECTED" : "NOT CONNECTED"}
      </span>
    `).join("");
}

document.querySelectorAll(".quick-model-button[data-model]").forEach(button => {
  button.addEventListener("click", () => {
    const provider = button.dataset.provider || "";
    const model = button.dataset.model || "";

    const providerSelect = $("#copilotProvider");
    const modelSelect = $("#copilotModel");

    if (providerSelect) {
      const knownProvider = Array.from(providerSelect.options)
        .some(option => option.value === provider);
      providerSelect.value = knownProvider ? provider : "";
    }

    if (modelSelect) {
      const exists = Array.from(modelSelect.options)
        .some(option => option.value === model);
      if (!exists) modelSelect.add(new Option(model, model));
      modelSelect.value = model;
    }

    document.querySelectorAll(".quick-model-button").forEach(item => item.classList.remove("selected"));
    button.classList.add("selected");

    $("#copilotChatStatus").textContent =
      `Selected ${model}${provider ? ` through ${provider}` : ""}. Type your message and press Send.`;
    $("#copilotMessageInput")?.focus();
  });
});

document.querySelector("[data-open-models='true']")?.addEventListener("click", () => {
  switchView("models");
});

$("#refreshCopilotProviders")?.addEventListener("click", renderCopilotProviderQuickStatus);




let pendingProviderModel = null;

async function loadSecureProviderSettings() {
  const payload = await api("/api/settings/providers");
  const container = $("#secureProviderCards");
  if (!container) return;

  container.innerHTML = payload.providers.map(provider => `
    <article class="secure-provider-card">
      <div>
        <strong>${provider.name}</strong>
        <small>${provider.credential_source}</small>
      </div>
      <div class="secure-provider-card-actions">
        <span class="connection-badge ${provider.connected ? "connected" : "missing"}">
          ${provider.connected ? "CONNECTED" : "NOT CONNECTED"}
        </span>
        <a href="${provider.api_key_url}" target="_blank" rel="noreferrer">
          ${provider.id === "ollama" ? "Install" : "Get API key"}
        </a>
        <a href="${provider.models_url}" target="_blank" rel="noreferrer">Models</a>
        ${provider.id !== "ollama" ? `
          <button
            type="button"
            data-connect-provider="${provider.id}"
            data-key-url="${provider.api_key_url}"
            data-models-url="${provider.models_url}">
            ${provider.connected ? "Replace key" : "Connect"}
          </button>` : ""}
        ${provider.connected && provider.id !== "ollama" ? `
          <button type="button" data-delete-provider="${provider.id}">Disconnect</button>` : ""}
      </div>
    </article>
  `).join("");

  $("#selectedProviderModel").innerHTML = `
    <strong>${payload.selection.selected_provider || "none"}</strong>
    <code>${payload.selection.selected_model || "No model selected"}</code>
  `;

  bindSecureProviderActions();
  await loadActiveModelIndicator();
}

function openProviderKeyDialog(provider, model, keyUrl, modelsUrl) {
  $("#providerKeyProvider").value = provider;
  $("#providerKeySelectedModel").value = model || "";
  $("#providerKeyModelDisplay").value = model || "Choose after connecting";
  $("#providerKeyDialogTitle").textContent = `Connect ${provider}`;
  $("#providerOfficialKeyLink").href = keyUrl;
  $("#providerOfficialModelsLink").href = modelsUrl;
  $("#providerApiKeyInput").value = "";
  $("#providerApiKeyInput").type = "password";
  $("#showProviderApiKey").checked = false;
  $("#providerKeyDialog").showModal();
}

function bindSecureProviderActions() {
  document.querySelectorAll("[data-connect-provider]").forEach(button => {
    button.addEventListener("click", () => {
      const provider = button.dataset.connectProvider;
      openProviderKeyDialog(
        provider,
        pendingProviderModel?.provider === provider ? pendingProviderModel.model : "",
        button.dataset.keyUrl,
        button.dataset.modelsUrl,
      );
    });
  });

  document.querySelectorAll("[data-delete-provider]").forEach(button => {
    button.addEventListener("click", async () => {
      if (!confirm(`Disconnect ${button.dataset.deleteProvider}?`)) return;
      await api(`/api/settings/providers/${button.dataset.deleteProvider}`, {
        method: "DELETE",
      });
      await loadSecureProviderSettings();
      await loadProviderConnections();
    });
  });
}

$("#providerKeyForm")?.addEventListener("submit", async event => {
  event.preventDefault();
  const provider = $("#providerKeyProvider").value;
  const selectedModel = $("#providerKeySelectedModel").value;
  const apiKey = $("#providerApiKeyInput").value.trim();

  const submit = event.currentTarget.querySelector('button[type="submit"]');
  submit.disabled = true;
  submit.textContent = "Savingâ€¦";

  try {
    await api("/api/settings/providers/key", {
      method: "POST",
      body: JSON.stringify({
        provider,
        api_key: apiKey,
        selected_model: selectedModel,
      }),
    });
    $("#providerKeyDialog").close();
    $("#providerApiKeyInput").value = "";
    await loadSecureProviderSettings();
    await loadProviderConnections();
    await renderCopilotProviderQuickStatus();
    alert(`${provider} saved securely. Restart Uvicorn before the gateway uses a newly saved key.`);
  } catch (error) {
    alert(`Could not save provider key: ${error.message}`);
  } finally {
    submit.disabled = false;
    submit.textContent = "Save securely";
  }
});

$("#showProviderApiKey")?.addEventListener("change", event => {
  $("#providerApiKeyInput").type = event.target.checked ? "text" : "password";
});

$("#closeProviderKeyDialog")?.addEventListener("click", () => $("#providerKeyDialog").close());
$("#cancelProviderKeyDialog")?.addEventListener("click", () => $("#providerKeyDialog").close());
$("#refreshSecureProviderSettings")?.addEventListener("click", loadSecureProviderSettings);
$("#openModelSearchFromSettings")?.addEventListener("click", () => switchView("models"));




async function loadUnifiedAiSettings() {
  const [settings, providers] = await Promise.all([
    api("/api/settings/providers"),
    api("/api/models/providers"),
  ]);

  const selection = settings.selection || {};
  $("#unifiedSelectedModel").innerHTML = `
    <strong>${selection.selected_provider || "none"}</strong>
    <code>${selection.selected_model || "No model selected"}</code>
  `;

  $("#unifiedProviderStatus").innerHTML = settings.providers.map(provider => `
    <span class="quick-provider-chip ${provider.connected ? "connected" : "missing"}">
      ${provider.name}: ${provider.connected ? "CONNECTED" : "NOT CONNECTED"}
    </span>
  `).join("");

  $("#unifiedProviderCards").innerHTML = settings.providers.map(provider => `
    <article class="secure-provider-card">
      <div>
        <strong>${provider.name}</strong>
        <small>${provider.credential_source}</small>
      </div>
      <div class="secure-provider-card-actions">
        <span class="connection-badge ${provider.connected ? "connected" : "missing"}">
          ${provider.connected ? "CONNECTED" : "NOT CONNECTED"}
        </span>
        <a href="${provider.api_key_url}" target="_blank" rel="noreferrer">
          ${provider.id === "ollama" ? "Install" : "Get API key"}
        </a>
        <a href="${provider.models_url}" target="_blank" rel="noreferrer">Models</a>
        ${provider.id !== "ollama" ? `
          <button
            type="button"
            data-unified-connect-provider="${provider.id}"
            data-key-url="${provider.api_key_url}"
            data-models-url="${provider.models_url}">
            ${provider.connected ? "Replace key" : "Connect"}
          </button>` : ""}
        ${provider.connected && provider.id !== "ollama" ? `
          <button type="button" data-unified-delete-provider="${provider.id}">
            Disconnect
          </button>` : ""}
      </div>
    </article>
  `).join("");

  document.querySelectorAll("[data-unified-connect-provider]").forEach(button => {
    button.addEventListener("click", () => {
      openProviderKeyDialog(
        button.dataset.unifiedConnectProvider,
        selection.selected_model || "",
        button.dataset.keyUrl,
        button.dataset.modelsUrl,
      );
    });
  });

  document.querySelectorAll("[data-unified-delete-provider]").forEach(button => {
    button.addEventListener("click", async () => {
      const provider = button.dataset.unifiedDeleteProvider;
      if (!confirm(`Disconnect ${provider}?`)) return;
      await api(`/api/settings/providers/${provider}`, { method: "DELETE" });
      await loadUnifiedAiSettings();
    });
  });
}

async function loadUnifiedModelCatalog() {
  const params = new URLSearchParams({
    query: $("#unifiedModelSearchInput").value.trim(),
    provider: $("#unifiedModelProviderFilter").value,
    free_only: String($("#unifiedFreeModelsOnly").checked),
    limit: "120",
  });

  $("#unifiedModelCatalogResults").innerHTML =
    `<p class="muted-copy">Searching modelsâ€¦</p>`;

  const payload = await api(`/api/models/catalog?${params.toString()}`);
  $("#unifiedModelCatalogSource").textContent =
    `${payload.count} models · ${payload.source}`;

  $("#unifiedModelCatalogResults").innerHTML = payload.models.length
    ? payload.models.map(model => `
      <article class="model-catalog-card">
        <div class="model-catalog-card-head">
          <div>
            <strong>${model.name}</strong>
            <code>${model.id}</code>
          </div>
          <span>${model.provider}</span>
        </div>
        <p>${model.description || "No description available."}</p>
        <div class="model-catalog-meta">
          <span>Context: ${Number(model.context_length || 0).toLocaleString()}</span>
          <span>Input: ${formatCatalogPrice(model.prompt_price)}</span>
          <span>Output: ${formatCatalogPrice(model.completion_price)}</span>
          <span>${(model.input_modalities || []).join(", ") || "text"}</span>
        </div>
        <button
          class="primary"
          data-unified-select-model="${model.id}">
          Select model
        </button>
      </article>
    `).join("")
    : `<p class="muted-copy">No matching models found.</p>`;

  document.querySelectorAll("[data-unified-select-model]").forEach(button => {
    button.addEventListener("click", async () => {
      const modelId = button.dataset.unifiedSelectModel;
      const provider = modelId.includes("/") ? "openrouter" : "ollama";

      await api("/api/settings/providers/model", {
        method: "POST",
        body: JSON.stringify({
          provider,
          model: modelId,
        }),
      });

      const settings = await api("/api/settings/providers");
      const providerInfo = settings.providers.find(item => item.id === provider);

      await loadUnifiedAiSettings();

      if (providerInfo && !providerInfo.connected) {
        openProviderKeyDialog(
          provider,
          modelId,
          providerInfo.api_key_url,
          providerInfo.models_url,
        );
      } else {
        alert(`Selected model: ${modelId}`);
      }
    });
  });
}

$("#refreshUnifiedAiSettings")?.addEventListener("click", async () => {
  await loadUnifiedAiSettings();
  await loadUnifiedModelCatalog();
});

$("#openAiBudgetSettings")?.addEventListener("click", () => {
  switchView("budget");
});

$("#unifiedSearchModels")?.addEventListener("click", loadUnifiedModelCatalog);

$("#unifiedModelSearchInput")?.addEventListener("keydown", event => {
  if (event.key === "Enter") loadUnifiedModelCatalog();
});

Promise.allSettled([
  loadUnifiedAiSettings(),
  loadUnifiedModelCatalog(),
]);




let activeOllamaPullTimer = null;

function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (!value) return "Unknown size";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(index >= 3 ? 2 : 1)} ${units[index]}`;
}

async function loadOllamaManager() {
  const payload = await api("/api/ollama/status");
  $("#ollamaManagerStatus").textContent = payload.connected
    ? `CONNECTED · ${payload.count} installed`
    : "NOT RUNNING";

  $("#ollamaManagerStatus").classList.toggle("connected", payload.connected);

  $("#installedOllamaModels").innerHTML = payload.models.length
    ? payload.models.map(model => `
      <article class="installed-ollama-card">
        <div>
          <strong>${model.name}</strong>
          <small>${formatBytes(model.size || 0)}</small>
        </div>
        <div class="installed-ollama-actions">
          <button type="button" data-select-ollama="${model.id}">Select</button>
          <button type="button" data-test-ollama="${model.id}">Test</button>
          <button type="button" data-delete-ollama="${model.id}">Remove</button>
        </div>
      </article>
    `).join("")
    : `<p class="muted-copy">No installed Ollama models were found.</p>`;

  document.querySelectorAll("[data-select-ollama]").forEach(button => {
    button.addEventListener("click", async () => {
      const model = button.dataset.selectOllama;
      await api("/api/settings/providers/model", {
        method: "POST",
        body: JSON.stringify({ provider: "ollama", model }),
      });
      await loadUnifiedAiSettings();
      alert(`Selected local model: ${model}`);
    });
  });

  document.querySelectorAll("[data-test-ollama]").forEach(button => {
    button.addEventListener("click", async () => {
      const model = button.dataset.testOllama;
      button.disabled = true;
      button.textContent = "Testingâ€¦";
      try {
        const result = await api("/api/ollama/test", {
          method: "POST",
          body: JSON.stringify({
            model,
            prompt: "Reply exactly: AIOS OLLAMA WEB TEST PASSED",
          }),
        });
        alert(`${model}\n\n${result.response}`);
      } catch (error) {
        alert(`Test failed: ${error.message}`);
      } finally {
        button.disabled = false;
        button.textContent = "Test";
      }
    });
  });

  document.querySelectorAll("[data-delete-ollama]").forEach(button => {
    button.addEventListener("click", async () => {
      const model = button.dataset.deleteOllama;
      if (!confirm(`Remove ${model} from this desktop?`)) return;
      await api("/api/ollama/models", {
        method: "DELETE",
        body: JSON.stringify({ model }),
      });
      await loadOllamaManager();
      await loadUnifiedModelCatalog();
    });
  });
}

async function pollOllamaPull(jobId) {
  clearInterval(activeOllamaPullTimer);
  activeOllamaPullTimer = setInterval(async () => {
    try {
      const job = await api(`/api/ollama/jobs/${jobId}`);
      $("#ollamaProgressText").textContent =
        `${job.status}${job.percent ? ` · ${job.percent}%` : ""}`;
      $("#ollamaProgressBar").value = job.percent || 0;

      if (job.state === "completed") {
        clearInterval(activeOllamaPullTimer);
        $("#ollamaProgressText").textContent = "Download complete";
        $("#ollamaProgressBar").value = 100;
        await loadOllamaManager();
        await loadUnifiedModelCatalog();
        await loadUnifiedAiSettings();
      }

      if (job.state === "failed") {
        clearInterval(activeOllamaPullTimer);
        $("#ollamaProgressText").textContent = `Failed: ${job.error}`;
      }
    } catch (error) {
      clearInterval(activeOllamaPullTimer);
      $("#ollamaProgressText").textContent = `Status error: ${error.message}`;
    }
  }, 1200);
}

$("#installOllamaModel")?.addEventListener("click", async () => {
  const model = $("#ollamaModelNameInput").value.trim();
  if (!model) {
    alert("Enter an Ollama model name first.");
    return;
  }

  const button = $("#installOllamaModel");
  button.disabled = true;
  button.textContent = "Startingâ€¦";

  try {
    const job = await api("/api/ollama/pull", {
      method: "POST",
      body: JSON.stringify({ model }),
    });

    $("#ollamaDownloadProgress").classList.remove("hidden");
    $("#ollamaProgressModel").textContent = model;
    $("#ollamaProgressText").textContent = "Starting downloadâ€¦";
    $("#ollamaProgressBar").value = 0;
    pollOllamaPull(job.job_id);
  } catch (error) {
    alert(`Could not start download: ${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "Download model";
  }
});




async function loadActiveModelIndicator() {
  const badge = $("#globalActiveBrain");
  const card = $("#unifiedSelectedModel");
  try {
    const active = await api("/api/models/active");
    const stateClass = active.ready ? (active.fallback_active ? "fallback" : "ready") : "offline";
    const stateText = active.ready ? (active.fallback_active ? "FALLBACK ACTIVE" : "READY") : "OFFLINE";
    if (badge) {
      badge.className = `global-active-brain ${stateClass}`;
      badge.innerHTML = `<span class="brain-dot ${stateClass}"></span><span><small>${stateText}</small><strong>${active.effective_provider} · ${active.effective_model}</strong></span>`;
    }
    if (card) {
      card.innerHTML = `
        <div class="active-model-primary">
          <span class="brain-dot ${stateClass}"></span>
          <div><small>${stateText}</small><strong>${active.effective_provider}</strong><code>${active.effective_model}</code></div>
        </div>
        ${active.fallback_active
          ? `<p class="active-model-warning">Requested ${active.requested_provider} · ${active.requested_model}, but AIOS is using fallback.</p>`
          : `<p class="active-model-success">This is the model AIOS will use first.</p>`}
        <div class="active-model-actions">
          <button type="button" id="testActiveModel">Test active model</button>
          <button type="button" id="refreshActiveModel">Refresh</button>
        </div>`;
      $("#refreshActiveModel")?.addEventListener("click", loadActiveModelIndicator);
      $("#testActiveModel")?.addEventListener("click", async event => {
        const button = event.currentTarget;
        button.disabled = true;
        button.textContent = "Testingâ€¦";
        try {
          if (active.effective_provider === "ollama") {
            const result = await api("/api/ollama/test", {
              method: "POST",
              body: JSON.stringify({model: active.effective_model, prompt: "Reply exactly: AIOS ACTIVE MODEL TEST PASSED"}),
            });
            alert(`${active.effective_model}\n\n${result.response}`);
          } else {
            alert("Use Copilot Chat to test this hosted provider.");
          }
        } catch (error) {
          alert(`Active model test failed: ${error.message}`);
        } finally {
          button.disabled = false;
          button.textContent = "Test active model";
        }
      });
    }
  } catch (error) {
    if (badge) badge.innerHTML = `<span class="brain-dot offline"></span><span><small>STATUS ERROR</small><strong>Open AI & Providers</strong></span>`;
    if (card) card.innerHTML = `<p class="active-model-warning">Could not load active model: ${error.message}</p><button id="retryActiveModel">Retry</button>`;
    $("#retryActiveModel")?.addEventListener("click", loadActiveModelIndicator);
  }
}
$("#globalActiveBrain")?.addEventListener("click", () => switchView("ai-settings"));



function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatHealthBytes(bytes) {
  const value = Number(bytes || 0);
  if (!value) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(index >= 3 ? 2 : 1)} ${units[index]}`;
}

function healthState(healthy) {
  return healthy
    ? '<span class="health-state good">HEALTHY</span>'
    : '<span class="health-state bad">ATTENTION</span>';
}

function showFrontendBoundary(error, context = "UI operation") {
  const target = $("#frontendErrorBoundary");
  if (!target) return;
  target.classList.remove("hidden");
  target.innerHTML = `
    <strong>${escapeHtml(context)} failed</strong>
    <p>${escapeHtml(error?.message || error)}</p>
    <button type="button" id="dismissFrontendError">Dismiss</button>
  `;
  $("#dismissFrontendError")?.addEventListener("click", () => {
    target.classList.add("hidden");
    target.innerHTML = "";
  });
}

window.addEventListener("error", event => {
  showFrontendBoundary(event.error || event.message, "Frontend");
});

window.addEventListener("unhandledrejection", event => {
  showFrontendBoundary(event.reason || "Unknown promise rejection", "Async request");
});

async function loadSystemHealthDashboard() {
  try {
    const health = await api("/api/system/health");

    $("#healthRuntimeCard").innerHTML = `
      <div class="health-line"><span>Application</span><strong>${escapeHtml(health.application.status)}</strong></div>
      <div class="health-line"><span>Active provider</span><strong>${escapeHtml(health.active_model.effective_provider)}</strong></div>
      <div class="health-line"><span>Active model</span><code>${escapeHtml(health.active_model.effective_model)}</code></div>
      <div class="health-line"><span>Process ID</span><strong>${health.backend.process.pid}</strong></div>
      <div class="health-line"><span>Threads</span><strong>${health.backend.process.threads}</strong></div>
    `;

    $("#healthResourceCard").innerHTML = `
      <div class="health-line"><span>Disk</span>${healthState(health.disk.healthy)}</div>
      <progress max="100" value="${health.disk.percent}"></progress>
      <small>${health.disk.percent}% used · ${formatHealthBytes(health.disk.free_bytes)} free</small>
      <div class="health-line"><span>Memory</span>${healthState(health.memory.healthy)}</div>
      <progress max="100" value="${health.memory.percent}"></progress>
      <small>${health.memory.percent}% used · ${formatHealthBytes(health.memory.available_bytes)} available</small>
    `;

    $("#healthNetworkCard").innerHTML = `
      <div class="health-line"><span>Cloudflare</span><strong>${health.cloudflare.running ? "RUNNING" : "NOT DETECTED"}</strong></div>
      <div class="health-line"><span>Public URL</span><code>${escapeHtml(health.cloudflare.public_url)}</code></div>
      <div class="health-line"><span>Ollama</span><strong>${health.ollama.connected ? "CONNECTED" : "OFFLINE"}</strong></div>
      <div class="health-line"><span>Installed local models</span><strong>${health.ollama.count}</strong></div>
    `;

    const stopped = Boolean(health.emergency_stop.enabled);
    $("#healthEmergencyCard").innerHTML = `
      <div class="emergency-state ${stopped ? "stopped" : "running"}">
        ${stopped ? "EXECUTION STOPPED" : "EXECUTION ENABLED"}
      </div>
      <p>${escapeHtml(health.emergency_stop.reason || "No emergency stop reason recorded.")}</p>
      <textarea id="emergencyStopReason" placeholder="Reason for emergency stop">${escapeHtml(health.emergency_stop.reason || "")}</textarea>
      <button id="toggleEmergencyStop" class="${stopped ? "" : "danger"}">
        ${stopped ? "Resume AIOS execution" : "Activate emergency stop"}
      </button>
    `;

    $("#toggleEmergencyStop")?.addEventListener("click", async () => {
      const enabled = !stopped;
      const reason = $("#emergencyStopReason").value.trim();
      if (enabled && !confirm("Stop all AIOS write and execution requests?")) return;
      await api("/api/system/emergency-stop", {
        method: "POST",
        body: JSON.stringify({ enabled, reason }),
      });
      await loadSystemHealthDashboard();
    });

    $("#healthBackupCard").innerHTML = `
      <div class="health-line"><span>Available backups</span><strong>${health.backup.count}</strong></div>
      <div class="health-line"><span>Latest backup</span><code>${escapeHtml(health.backup.latest || "None")}</code></div>
      <div class="health-line"><span>Latest size</span><strong>${formatHealthBytes(health.backup.latest_size_bytes)}</strong></div>
    `;

    $("#failedRequestCount").textContent = String(health.failed_request_count);
    $("#failedRequestList").innerHTML = health.recent_failed_requests.length
      ? health.recent_failed_requests.map(item => `
        <article class="failed-request-card">
          <div>
            <strong>${escapeHtml(item.method)} ${escapeHtml(item.path)}</strong>
            <span>${escapeHtml(item.time)}</span>
          </div>
          <span class="failure-status">${escapeHtml(item.status)}</span>
          <p>${escapeHtml(item.error || "Request failed")}</p>
        </article>
      `).join("")
      : '<p class="muted-copy">No failed requests have been recorded.</p>';
  } catch (error) {
    showFrontendBoundary(error, "System health dashboard");
  }
}

$("#refreshSystemHealth")?.addEventListener("click", loadSystemHealthDashboard);

$("#createSystemBackup")?.addEventListener("click", async () => {
  try {
    const result = await api("/api/system/backup", { method: "POST" });
    alert(`Backup created: ${result.filename}`);
    await loadSystemHealthDashboard();
  } catch (error) {
    showFrontendBoundary(error, "Create backup");
  }
});

$("#restoreLatestBackup")?.addEventListener("click", async () => {
  if (!confirm("Restore the latest backup? AIOS will create a safety backup first.")) return;
  try {
    const result = await api("/api/system/restore-latest", { method: "POST" });
    alert(`Restored from ${result.restored_from}. Restart AIOS now.`);
    await loadSystemHealthDashboard();
  } catch (error) {
    showFrontendBoundary(error, "Restore backup");
  }
});

loadSystemHealthDashboard();



async function loadObsidianStatus() {
  try {
    const status = await api("/api/connectors/obsidian/status");
    $("#obsidianConnectionStatus").textContent = status.connected
      ? `CONNECTED · ${status.note_count} notes`
      : "NOT CONNECTED";
    $("#obsidianConnectionStatus").classList.toggle("connected", status.connected);
    $("#obsidianVaultPath").value = status.vault_path || $("#obsidianVaultPath").value;
    $("#obsidianPermissionMode").value = status.mode;
    $("#obsidianBackupBeforeWrite").checked = Boolean(status.backup_before_write);
    $("#obsidianAllowOverwrite").checked = Boolean(status.allow_overwrite);
  } catch (error) {
    $("#obsidianConnectionStatus").textContent = "STATUS ERROR";
    showFrontendBoundary(error, "Obsidian connector");
  }
}

$("#saveObsidianSettings")?.addEventListener("click", async () => {
  try {
    const result = await api("/api/connectors/obsidian/settings", {
      method: "POST",
      body: JSON.stringify({
        vault_path: $("#obsidianVaultPath").value.trim(),
        mode: $("#obsidianPermissionMode").value,
        backup_before_write: $("#obsidianBackupBeforeWrite").checked,
        allow_overwrite: $("#obsidianAllowOverwrite").checked,
      }),
    });
    alert(`Obsidian connected: ${result.note_count} notes found.`);
    await loadObsidianStatus();
  } catch (error) {
    showFrontendBoundary(error, "Save Obsidian settings");
  }
});

async function searchObsidianNotes() {
  try {
    const query = encodeURIComponent($("#obsidianSearchInput").value.trim());
    const result = await api(`/api/connectors/obsidian/search?query=${query}`);
    $("#obsidianSearchResults").innerHTML = result.items.length
      ? result.items.map(item => `
        <button class="obsidian-result-card" data-obsidian-note="${escapeHtml(item.relative_path)}">
          <strong>${escapeHtml(item.title)}</strong>
          <small>${escapeHtml(item.relative_path)}</small>
          <p>${escapeHtml(item.snippet)}</p>
        </button>
      `).join("")
      : '<p class="muted-copy">No matching notes found.</p>';

    document.querySelectorAll("[data-obsidian-note]").forEach(button => {
      button.addEventListener("click", async () => {
        $("#obsidianNotePath").value = button.dataset.obsidianNote;
        await readObsidianSelectedNote();
      });
    });
  } catch (error) {
    showFrontendBoundary(error, "Search Obsidian");
  }
}

async function readObsidianSelectedNote() {
  const relativePath = $("#obsidianNotePath").value.trim();
  if (!relativePath) return alert("Enter or select a note path.");
  try {
    const result = await api(
      `/api/connectors/obsidian/note?relative_path=${encodeURIComponent(relativePath)}`
    );
    $("#obsidianNoteContent").value = result.content;
  } catch (error) {
    showFrontendBoundary(error, "Read Obsidian note");
  }
}

$("#searchObsidianNotes")?.addEventListener("click", searchObsidianNotes);
$("#obsidianSearchInput")?.addEventListener("keydown", event => {
  if (event.key === "Enter") searchObsidianNotes();
});
$("#readObsidianNote")?.addEventListener("click", readObsidianSelectedNote);

$("#createObsidianNote")?.addEventListener("click", async () => {
  try {
    const result = await api("/api/connectors/obsidian/note", {
      method: "POST",
      body: JSON.stringify({
        relative_path: $("#obsidianNotePath").value.trim(),
        content: $("#obsidianNoteContent").value,
        overwrite: $("#obsidianAllowOverwrite").checked,
      }),
    });
    alert(`Saved: ${result.relative_path}`);
    await searchObsidianNotes();
    await loadObsidianStatus();
  } catch (error) {
    showFrontendBoundary(error, "Create Obsidian note");
  }
});

$("#appendObsidianNote")?.addEventListener("click", async () => {
  try {
    const result = await api("/api/connectors/obsidian/append", {
      method: "POST",
      body: JSON.stringify({
        relative_path: $("#obsidianNotePath").value.trim(),
        content: $("#obsidianNoteContent").value,
      }),
    });
    alert(`Appended: ${result.relative_path}`);
    await readObsidianSelectedNote();
  } catch (error) {
    showFrontendBoundary(error, "Append Obsidian note");
  }
});

$("#openSelectedObsidianNote")?.addEventListener("click", () => {
  const path = $("#obsidianNotePath").value.trim().replace(/\.md$/i, "");
  if (!path) return alert("Enter or select a note path.");
  const uri = `obsidian://open?vault=${encodeURIComponent("AIOS Knowledge")}&file=${encodeURIComponent(path)}`;
  window.location.href = uri;
});

loadObsidianStatus();



async function loadObsidianExportSettings() {
  try {
    const payload = await api("/api/connectors/obsidian/export-settings");
    const settings = payload.settings;
    $("#obsidianAutoExportEnabled").checked = Boolean(settings.enabled);
    $("#obsidianExportMissions").checked = Boolean(settings.export_missions);
    $("#obsidianExportResearch").checked = Boolean(settings.export_research);
    $("#obsidianExportAgentReports").checked = Boolean(settings.export_agent_reports);
    $("#obsidianExportDecisions").checked = Boolean(settings.export_decisions);
    $("#obsidianOnlyValidated").checked = Boolean(settings.only_validated);
    $("#obsidianAutoExportStatus").textContent = settings.enabled
      ? "AUTO-EXPORT ON"
      : "AUTO-EXPORT OFF";

    $("#obsidianRecentExports").innerHTML = payload.recent_exports.length
      ? payload.recent_exports.map(item => `
        <article class="obsidian-export-record">
          <div>
            <strong>${escapeHtml(item.mission_title || item.mission_id)}</strong>
            <small>${escapeHtml(item.exported_at)}</small>
          </div>
          <span>${item.validated ? "VALIDATED" : "MANUAL"}</span>
          <p>${item.files.map(file => escapeHtml(file.relative_path)).join("<br>")}</p>
        </article>
      `).join("")
      : '<p class="muted-copy">No mission exports recorded yet.</p>';
  } catch (error) {
    showFrontendBoundary(error, "Obsidian export settings");
  }
}

$("#saveObsidianExportSettings")?.addEventListener("click", async () => {
  try {
    await api("/api/connectors/obsidian/export-settings", {
      method: "POST",
      body: JSON.stringify({
        enabled: $("#obsidianAutoExportEnabled").checked,
        export_missions: $("#obsidianExportMissions").checked,
        export_research: $("#obsidianExportResearch").checked,
        export_agent_reports: $("#obsidianExportAgentReports").checked,
        export_decisions: $("#obsidianExportDecisions").checked,
        only_validated: $("#obsidianOnlyValidated").checked,
      }),
    });
    await loadObsidianExportSettings();
    alert("Obsidian automatic export settings saved.");
  } catch (error) {
    showFrontendBoundary(error, "Save Obsidian export settings");
  }
});

$("#exportCurrentMissionToObsidian")?.addEventListener("click", async () => {
  if (!currentMission?.id) {
    alert("Load or create a mission first.");
    return;
  }
  try {
    const result = await api(
      `/api/connectors/obsidian/reexport-mission/${currentMission.id}`,
      { method: "POST" },
    );
    alert(
      result.exported
        ? `Exported ${result.files.length} Obsidian notes.`
        : `Export skipped: ${result.reason}`
    );
    await loadObsidianExportSettings();
    await searchObsidianNotes();
  } catch (error) {
    showFrontendBoundary(error, "Export mission to Obsidian");
  }
});

loadObsidianExportSettings();



function missionStatusLabel(status) {
  return String(status || "unknown").replaceAll("_", " ").toUpperCase();
}

function missionDate(value) {
  if (!value) return "No date";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

async function openMissionFromHistory(missionId, switchToWorkflow = false) {
  try {
    const mission = await api(`/api/missions/${missionId}`);
    renderWorkflow(mission);
    dashboard = dashboard || {};
    dashboard.missions = dashboard.missions || [];
    const existingIndex = dashboard.missions.findIndex(item => item.id === mission.id);
    if (existingIndex >= 0) dashboard.missions[existingIndex] = mission;
    else dashboard.missions.push(mission);

    if (switchToWorkflow) switchView("workflow");
    else switchView("mission");

    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (error) {
    showFrontendBoundary(error, "Open mission");
  }
}

async function loadMissionHistory() {
  const target = $("#missionHistoryList");
  if (!target) return;

  const params = new URLSearchParams({
    query: $("#missionHistorySearch")?.value.trim() || "",
    status: $("#missionHistoryStatus")?.value || "",
    include_archived: String(Boolean($("#missionHistoryArchived")?.checked)),
    limit: "300",
  });

  target.innerHTML = '<p class="muted-copy">Loading mission historyâ€¦</p>';

  try {
    const payload = await api(`/api/missions?${params.toString()}`);
    $("#missionHistoryCount").textContent = `${payload.count} mission${payload.count === 1 ? "" : "s"}`;

    target.innerHTML = payload.items.length
      ? payload.items.map(mission => {
          const provider = mission.providers?.[0] || "not recorded";
          const model = mission.models?.[0] || "not recorded";
          const workflowText = `${mission.workflow_complete}/${mission.workflow_total}`;
          return `
            <article class="mission-history-card ${mission.archived ? "archived" : ""}">
              <div class="mission-history-card-main">
                <div class="mission-history-card-head">
                  <div>
                    <span class="mission-history-id">${escapeHtml(mission.id)}</span>
                    <h3>${escapeHtml(mission.title)}</h3>
                  </div>
                  <span class="mission-status ${escapeHtml(mission.status)}">
                    ${escapeHtml(missionStatusLabel(mission.status))}
                  </span>
                </div>

                <p>${escapeHtml(mission.objective)}</p>

                <div class="mission-history-meta">
                  <span>Progress ${mission.progress}%</span>
                  <span>Workflow ${workflowText}</span>
                  <span>${mission.validated ? "Validated" : "Not validated"}</span>
                  <span>${escapeHtml(provider)}</span>
                  <span>${escapeHtml(model)}</span>
                  <span>$${Number(mission.estimated_cost_usd || 0).toFixed(6)}</span>
                </div>

                <div class="mission-history-dates">
                  <span>Created: ${escapeHtml(missionDate(mission.created_at))}</span>
                  <span>Updated: ${escapeHtml(missionDate(mission.updated_at))}</span>
                  ${mission.obsidian_exported ? '<span class="exported-badge">OBSIDIAN EXPORTED</span>' : ""}
                  ${mission.archived ? '<span class="archived-badge">ARCHIVED</span>' : ""}
                </div>
              </div>

              <div class="mission-history-actions">
                <button data-open-history="${mission.id}">Open</button>
                ${mission.status !== "complete"
                  ? `<button class="primary" data-resume-history="${mission.id}">Resume</button>`
                  : `<button class="primary" data-reexport-history="${mission.id}">Re-export</button>`}
                <button data-archive-history="${mission.id}" data-archived="${mission.archived}">
                  ${mission.archived ? "Unarchive" : "Archive"}
                </button>
              </div>
            </article>
          `;
        }).join("")
      : '<div class="empty-state"><h3>No matching missions</h3><p>Create a mission or change the history filters.</p></div>';

    document.querySelectorAll("[data-open-history]").forEach(button => {
      button.addEventListener("click", () => openMissionFromHistory(button.dataset.openHistory, false));
    });

    document.querySelectorAll("[data-resume-history]").forEach(button => {
      button.addEventListener("click", () => openMissionFromHistory(button.dataset.resumeHistory, true));
    });

    document.querySelectorAll("[data-reexport-history]").forEach(button => {
      button.addEventListener("click", async () => {
        button.disabled = true;
        button.textContent = "Exportingâ€¦";
        try {
          const result = await api(
            `/api/connectors/obsidian/reexport-mission/${button.dataset.reexportHistory}`,
            { method: "POST" },
          );
          alert(
            result.exported
              ? `Exported ${result.files.length} notes to Obsidian.`
              : `Export skipped: ${result.reason}`
          );
          await loadMissionHistory();
    if ((mission.status || "").toLowerCase() === "complete") await notifyMissionExport(mission);
        } catch (error) {
          showFrontendBoundary(error, "Re-export mission");
        } finally {
          button.disabled = false;
          button.textContent = "Re-export";
        }
      });
    });

    document.querySelectorAll("[data-archive-history]").forEach(button => {
      button.addEventListener("click", async () => {
        const archived = button.dataset.archived === "true";
        if (!confirm(`${archived ? "Unarchive" : "Archive"} this mission?`)) return;
        try {
          await api(`/api/missions/${button.dataset.archiveHistory}/archive`, {
            method: "POST",
            body: JSON.stringify({ archived: !archived }),
          });
          await loadMissionHistory();
          await loadDashboard();
        } catch (error) {
          showFrontendBoundary(error, "Archive mission");
        }
      });
    });
  } catch (error) {
    target.innerHTML = `
      <div class="frontend-error-boundary">
        <strong>Mission history failed to load</strong>
        <p>${escapeHtml(error.message)}</p>
        <button id="retryMissionHistory">Retry</button>
      </div>`;
    $("#retryMissionHistory")?.addEventListener("click", loadMissionHistory);
  }
}

$("#refreshMissionHistory")?.addEventListener("click", loadMissionHistory);
$("#searchMissionHistory")?.addEventListener("click", loadMissionHistory);
$("#missionHistoryStatus")?.addEventListener("change", loadMissionHistory);
$("#missionHistoryArchived")?.addEventListener("change", loadMissionHistory);
$("#missionHistorySearch")?.addEventListener("keydown", event => {
  if (event.key === "Enter") loadMissionHistory();
});

loadMissionHistory();



let missionHistoryAutoRefreshTimer = null;
let lastKnownMissionStates = new Map();
let notifiedMissionExports = new Set();

function showAiosToast({ title, message, type = "success", actions = [] }) {
  const region = $("#aiosToastRegion");
  if (!region) return;

  const toast = document.createElement("article");
  toast.className = `aios-toast ${type}`;
  toast.innerHTML = `
    <div class="aios-toast-copy">
      <strong>${escapeHtml(title)}</strong>
      <p>${escapeHtml(message)}</p>
    </div>
    <div class="aios-toast-actions"></div>
    <button class="aios-toast-close" type="button" aria-label="Close">Ã—</button>
  `;

  const actionsTarget = toast.querySelector(".aios-toast-actions");
  actions.forEach(action => {
    const button = document.createElement(action.href ? "a" : "button");
    button.textContent = action.label;
    if (action.href) {
      button.href = action.href;
      button.rel = "noreferrer";
    } else {
      button.type = "button";
      button.addEventListener("click", action.onClick);
    }
    actionsTarget.appendChild(button);
  });

  toast.querySelector(".aios-toast-close").addEventListener("click", () => toast.remove());
  region.appendChild(toast);

  setTimeout(() => {
    if (toast.isConnected) toast.remove();
  }, 12000);
}

function obsidianMissionUri(missionTitle) {
  const file = `Missions/${missionTitle}`;
  return `obsidian://open?vault=${encodeURIComponent("AIOS Knowledge")}&file=${encodeURIComponent(file)}`;
}

async function notifyMissionExport(mission) {
  if (!mission?.id || notifiedMissionExports.has(mission.id)) return;
  notifiedMissionExports.add(mission.id);

  try {
    const status = await api(`/api/connectors/obsidian/export-status/${mission.id}`);
    if (status.exported) {
      showAiosToast({
        title: "Mission completed",
        message: `${mission.title} was exported to Obsidian.`,
        type: "success",
        actions: [
          {
            label: "Open in Obsidian",
            href: obsidianMissionUri(mission.title),
          },
          {
            label: "View Connectors",
            onClick: () => switchView("connectors"),
          },
        ],
      });
    } else if (status.error) {
      showAiosToast({
        title: "Obsidian export failed",
        message: status.error,
        type: "error",
        actions: [
          {
            label: "Open Connectors",
            onClick: () => switchView("connectors"),
          },
        ],
      });
    }
  } catch (error) {
    showFrontendBoundary(error, "Check Obsidian export");
  }
}

async function autoRefreshMissionHistory() {
  try {
    const params = new URLSearchParams({
      query: $("#missionHistorySearch")?.value.trim() || "",
      status: $("#missionHistoryStatus")?.value || "",
      include_archived: String(Boolean($("#missionHistoryArchived")?.checked)),
      limit: "300",
    });
    const payload = await api(`/api/missions?${params.toString()}`);

    let changed = false;
    payload.items.forEach(mission => {
      const previous = lastKnownMissionStates.get(mission.id);
      const signature = `${mission.status}|${mission.progress}|${mission.workflow_complete}|${mission.validated}|${mission.obsidian_exported}`;
      if (previous && previous !== signature) changed = true;
      lastKnownMissionStates.set(mission.id, signature);

      if (mission.status === "complete" && mission.validated) {
        notifyMissionExport(mission);
      }
    });

    if (changed) {
      await loadMissionHistory();
      const completedMission = payload.items.find(
        mission => mission.status === "complete" && mission.validated
      );
      if (completedMission) {
        showAiosToast({
          title: "Mission status updated",
          message: `${completedMission.title} is complete and validated.`,
          type: "success",
        });
      }
    }
  } catch (error) {
    console.warn("Mission auto-refresh failed", error);
  }
}

function startMissionHistoryAutoRefresh() {
  clearInterval(missionHistoryAutoRefreshTimer);
  autoRefreshMissionHistory();
  missionHistoryAutoRefreshTimer = setInterval(autoRefreshMissionHistory, 5000);
}

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    clearInterval(missionHistoryAutoRefreshTimer);
  } else {
    startMissionHistoryAutoRefresh();
  }
});

startMissionHistoryAutoRefresh();



async function loadDesktopCompanion() {
  try {
    const [status, requests] = await Promise.all([
      api("/api/desktop-companion/status"),
      api("/api/desktop-companion/requests"),
    ]);

    $("#desktopCompanionStatus").textContent = status.connected
      ? `CONNECTED · ${status.pending_approvals} pending`
      : "NOT ON WINDOWS";
    $("#desktopCompanionStatus").classList.toggle("connected", status.connected);

    $("#desktopCompanionSummary").innerHTML = `
      <div><span>Host</span><strong>${escapeHtml(status.hostname)}</strong></div>
      <div><span>Platform</span><strong>${escapeHtml(status.platform)}</strong></div>
      <div><span>Working directory</span><code>${escapeHtml(status.working_directory)}</code></div>
      <div><span>Allowlisted tools</span><strong>${status.tools.length}</strong></div>
    `;

    $("#desktopCompanionRequests").innerHTML = requests.items.length
      ? requests.items.map(item => `
        <article class="desktop-request-card">
          <div class="desktop-request-head">
            <div>
              <strong>${escapeHtml(item.tool)}</strong>
              <small>${escapeHtml(item.id)} · ${escapeHtml(item.created_at)}</small>
            </div>
            <span class="desktop-request-status ${escapeHtml(item.status)}">
              ${escapeHtml(String(item.status).replaceAll("_", " ").toUpperCase())}
            </span>
          </div>
          <p>${escapeHtml(item.reason || "No reason supplied.")}</p>
          ${item.stdout ? `<pre>${escapeHtml(item.stdout)}</pre>` : ""}
          ${item.stderr ? `<pre class="error-output">${escapeHtml(item.stderr)}</pre>` : ""}
          ${item.status === "pending_approval" ? `
            <div class="connector-actions">
              <button class="primary" data-approve-desktop="${item.id}">Approve once</button>
              <button data-reject-desktop="${item.id}">Reject</button>
            </div>` : ""}
        </article>
      `).join("")
      : '<p class="muted-copy">No desktop tool requests yet.</p>';

    document.querySelectorAll("[data-approve-desktop]").forEach(button => {
      button.addEventListener("click", async () => {
        if (!confirm("Approve this desktop operation once?")) return;
        await api(`/api/desktop-companion/requests/${button.dataset.approveDesktop}/approval`, {
          method: "POST",
          body: JSON.stringify({ approved: true, note: "Approved from AIOS web app" }),
        });
        await loadDesktopCompanion();
      });
    });

    document.querySelectorAll("[data-reject-desktop]").forEach(button => {
      button.addEventListener("click", async () => {
        await api(`/api/desktop-companion/requests/${button.dataset.rejectDesktop}/approval`, {
          method: "POST",
          body: JSON.stringify({ approved: false, note: "Rejected from AIOS web app" }),
        });
        await loadDesktopCompanion();
      });
    });
  } catch (error) {
    showFrontendBoundary(error, "Desktop Companion");
  }
}

async function requestDesktopTool(tool) {
  const path = $("#desktopCompanionPath").value.trim();
  const zipPath = $("#desktopCompanionZip").value.trim();
  const reason = $("#desktopCompanionReason").value.trim() || `Test ${tool}`;

  let argumentsPayload = {};
  if (tool === "file.exists") argumentsPayload = { path };
  if (tool === "git.status") argumentsPayload = { repo_path: path };
  if (tool === "tests.run") argumentsPayload = { project_path: path };
  if (tool === "update.stage") argumentsPayload = { zip_path: zipPath };

  try {
    const result = await api("/api/desktop-companion/request", {
      method: "POST",
      body: JSON.stringify({
        tool,
        arguments: argumentsPayload,
        reason,
      }),
    });

    if (result.status === "pending_approval") {
      showAiosToast({
        title: "Approval required",
        message: `${tool} is waiting in the Desktop Companion queue.`,
        type: "success",
        actions: [{ label: "Review request", onClick: loadDesktopCompanion }],
      });
    } else {
      showAiosToast({
        title: result.success ? "Desktop tool completed" : "Desktop tool failed",
        message: `${tool} finished with exit code ${result.exit_code}.`,
        type: result.success ? "success" : "error",
      });
    }
    await loadDesktopCompanion();
  } catch (error) {
    showFrontendBoundary(error, `Desktop tool: ${tool}`);
  }
}

document.querySelectorAll("[data-desktop-tool]").forEach(button => {
  button.addEventListener("click", () => requestDesktopTool(button.dataset.desktopTool));
});

loadDesktopCompanion();
setInterval(() => {
  if (!document.hidden) loadDesktopCompanion();
}, 7000);



$("#recoverStaleDesktopRequests")?.addEventListener("click", async () => {
  try {
    const result = await api("/api/desktop-companion/recover-stale", {
      method: "POST",
    });
    alert(`Recovered ${result.count} stale request(s).`);
    await loadDesktopCompanion();
  } catch (error) {
    showFrontendBoundary(error, "Recover stale desktop requests");
  }
});



async function loadModelFlowGuard() {
  try {
    const active = await api("/api/models/active");
    $("#modelFlowGuardStatus").textContent = active.ready
      ? "FLOW GUARD READY"
      : "MODEL OFFLINE";

    $("#modelFlowGuardSummary").innerHTML = `
      <div><span>Requested provider</span><strong>${escapeHtml(active.requested_provider)}</strong></div>
      <div><span>Requested model</span><code>${escapeHtml(active.requested_model)}</code></div>
      <div><span>Effective provider</span><strong>${escapeHtml(active.effective_provider)}</strong></div>
      <div><span>Effective model</span><code>${escapeHtml(active.effective_model)}</code></div>
      <div><span>Fallback active</span><strong>${active.fallback_active ? "YES" : "NO"}</strong></div>
      <div><span>Workflow state</span><strong>MODEL-INDEPENDENT</strong></div>
    `;
  } catch (error) {
    $("#modelFlowGuardStatus").textContent = "STATUS ERROR";
  }
}

$("#runModelPreflight")?.addEventListener("click", async () => {
  try {
    const active = await api("/api/models/active");
    const result = await api("/api/models/preflight", {
      method: "POST",
      body: JSON.stringify({
        provider: active.effective_provider,
        model: active.effective_model,
        requires_json: $("#modelNeedsJson").checked,
        requires_tools: $("#modelNeedsTools").checked,
        requires_vision: $("#modelNeedsVision").checked,
      }),
    });

    $("#modelPreflightResult").innerHTML = `
      <div class="preflight-state ${result.ready ? "ready" : "blocked"}">
        ${result.ready ? "COMPATIBLE AND READY" : "BLOCKED"}
      </div>
      <p>${result.errors.length
        ? result.errors.map(item => escapeHtml(item)).join("<br>")
        : "The active model is compatible with the selected mission requirements."}</p>
    `;
  } catch (error) {
    showFrontendBoundary(error, "Model compatibility preflight");
  }
});

loadModelFlowGuard();



async function loadRoadmap() {
  try {
    const roadmap = await api("/api/roadmap");
    $("#roadmapCurrentPhase").textContent = roadmap.current_phase;

    $("#roadmapSummary").innerHTML = `
      <article>
        <span>Overall progress</span>
        <strong>${roadmap.summary.overall_progress}%</strong>
      </article>
      <article>
        <span>Completed milestones</span>
        <strong>${roadmap.summary.completed_milestones}</strong>
      </article>
      <article>
        <span>Remaining milestones</span>
        <strong>${roadmap.summary.remaining_milestones}</strong>
      </article>
      <article>
        <span>Last reviewed</span>
        <strong>${escapeHtml(missionDate(roadmap.last_reviewed_at))}</strong>
      </article>
    `;

    $("#roadmapNextActions").innerHTML = roadmap.next_actions.map(action => `
      <article class="roadmap-action-card">
        <span class="roadmap-priority">${action.priority}</span>
        <div>
          <small>${escapeHtml(action.area)}</small>
          <strong>${escapeHtml(action.title)}</strong>
          <p>${escapeHtml(action.description)}</p>
        </div>
      </article>
    `).join("");

    $("#roadmapPhases").innerHTML = roadmap.phases.map(phase => `
      <article class="panel roadmap-phase ${escapeHtml(phase.status)}">
        <div class="roadmap-phase-head">
          <div>
            <span>${escapeHtml(phase.status.replaceAll("-", " ").toUpperCase())}</span>
            <h3>${escapeHtml(phase.name)}</h3>
          </div>
          <strong>${phase.progress}%</strong>
        </div>
        <progress max="100" value="${phase.progress}"></progress>
        <div class="roadmap-columns">
          <div>
            <h4>Completed</h4>
            ${phase.completed.length
              ? `<ul>${phase.completed.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
              : '<p class="muted-copy">Nothing completed yet.</p>'}
          </div>
          <div>
            <h4>Remaining</h4>
            ${phase.remaining.length
              ? `<ul>${phase.remaining.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
              : '<p class="muted-copy">No remaining milestones.</p>'}
          </div>
        </div>
      </article>
    `).join("");
  } catch (error) {
    showFrontendBoundary(error, "Roadmap");
  }
}

async function loadCopilotReminders() {
  try {
    const payload = await api("/api/copilot/reminders");
    $("#copilotReminderCount").textContent = String(payload.count);
    $("#copilotReminderList").innerHTML = payload.items.length
      ? payload.items.map(item => `
        <article class="copilot-reminder-card ${escapeHtml(item.priority)}">
          <div>
            <small>${escapeHtml(item.type.toUpperCase())}</small>
            <strong>${escapeHtml(item.title)}</strong>
            <p>${escapeHtml(item.message)}</p>
          </div>
          <div class="copilot-reminder-actions">
            <button data-open-reminder="${escapeHtml(item.action_view)}">Open</button>
            <button data-dismiss-reminder="${escapeHtml(item.id)}">Dismiss</button>
          </div>
        </article>
      `).join("")
      : '<p class="muted-copy">Nothing needs your attention right now.</p>';

    document.querySelectorAll("[data-open-reminder]").forEach(button => {
      button.addEventListener("click", () => switchView(button.dataset.openReminder));
    });

    document.querySelectorAll("[data-dismiss-reminder]").forEach(button => {
      button.addEventListener("click", async () => {
        await api(`/api/copilot/reminders/${button.dataset.dismissReminder}/dismiss`, {
          method: "POST",
          body: JSON.stringify({ dismissed: true }),
        });
        await loadCopilotReminders();
      });
    });

    const highPriority = payload.items.find(item => item.priority === "high");
    if (highPriority && !sessionStorage.getItem(`reminder-${highPriority.id}`)) {
      sessionStorage.setItem(`reminder-${highPriority.id}`, "shown");
      showAiosToast({
        title: highPriority.title,
        message: highPriority.message,
        type: "success",
        actions: [
          {
            label: "Review now",
            onClick: () => switchView(highPriority.action_view),
          },
        ],
      });
    }
  } catch (error) {
    console.warn("Copilot reminders failed", error);
  }
}

$("#refreshRoadmap")?.addEventListener("click", loadRoadmap);

loadRoadmap();
loadCopilotReminders();

setInterval(() => {
  if (!document.hidden) loadCopilotReminders();
}, 30000);



async function loadQualityGate() {
  try {
    const gate = await api("/api/quality-gate");
    const label = gate.status === "passed"
      ? "PASS"
      : gate.status === "failed"
        ? "BLOCKED"
        : gate.status === "error"
          ? "ERROR"
          : "NOT RUN";

    $("#qualityGateStatus").textContent = label;
    $("#qualityGateStatus").dataset.state = gate.status;

    $("#qualityGateSummary").innerHTML = `
      <article><span>Passed</span><strong>${gate.summary.passed}</strong></article>
      <article><span>Failed</span><strong>${gate.summary.failed}</strong></article>
      <article><span>Skipped</span><strong>${gate.summary.skipped}</strong></article>
      <article><span>Last run</span><strong>${gate.generated_at ? escapeHtml(missionDate(gate.generated_at)) : "Never"}</strong></article>
    `;

    $("#qualityGateChecks").innerHTML = gate.checks.map(check => `
      <article class="quality-check ${escapeHtml(check.status)}">
        <span>${escapeHtml(check.status.toUpperCase())}</span>
        <div>
          <strong>${escapeHtml(check.name)}</strong>
          <code>${escapeHtml(check.command || "")}</code>
          ${(check.stderr || check.stdout)
            ? `<details><summary>Output</summary><pre>${escapeHtml(check.stderr || check.stdout)}</pre></details>`
            : ""}
        </div>
      </article>
    `).join("");
  } catch (error) {
    showFrontendBoundary(error, "Development quality gate");
  }
}

$("#refreshQualityGate")?.addEventListener("click", loadQualityGate);
loadQualityGate();



async function loadSecuritySession() {
  try {
    const response = await fetch("/api/auth/status", {credentials: "same-origin"});
    const status = await response.json();
    if (!status.configured) {
      $("#securityLogin").classList.remove("hidden");
      $("#securityLoginError").textContent =
        "Owner login is not configured. Run scripts\\configure_owner.py first.";
      return false;
    }
    if (!status.authenticated) {
      $("#securityLogin").classList.remove("hidden");
      return false;
    }
    aiosCsrfToken = status.csrf_token || "";
    $("#securityLogin").classList.add("hidden");
    $("#securityLogout")?.classList.remove("hidden");
    return true;
  } catch (error) {
    $("#securityLogin").classList.remove("hidden");
    $("#securityLoginError").textContent = "Security status is unavailable.";
    return false;
  }
}

$("#securityLoginForm")?.addEventListener("submit", async event => {
  event.preventDefault();
  $("#securityLoginError").textContent = "";
  try {
    const payload = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: $("#securityUsername").value,
        password: $("#securityPassword").value,
      }),
    });
    aiosCsrfToken = payload.csrf_token || "";
    $("#securityPassword").value = "";
    $("#securityLogin").classList.add("hidden");
    $("#securityLogout")?.classList.remove("hidden");
    location.reload();
  } catch (error) {
    if (error.code === "cloudflare_access_html") {
      $("#securityLoginError").innerHTML =
        'Cloudflare Access session expired. <a href="/cdn-cgi/access/logout">Sign in to Cloudflare again</a>, then retry.';
    } else {
      $("#securityLoginError").textContent = error.message || "Login failed";
    }
  }
});

$("#securityLogout")?.addEventListener("click", async () => {
  try {
    await api("/api/auth/logout", {method: "POST"});
  } finally {
    aiosCsrfToken = "";
    location.reload();
  }
});

loadSecuritySession();

window.addEventListener("hashchange", () => {
  const view = window.location.hash.replace("#", "");
  if (viewTitles[view]) switchView(view);
});



$("#runNextBrain")?.addEventListener("click", async () => {
  const button = $("#runNextBrain");
  if (!currentMission?.id) {
    setBrainControlState(null, "No active mission is loaded. Create a mission first.");
    return;
  }
  button.disabled = true;
  button.textContent = "Agent running…";
  setBrainControlState(currentMission, "Delegating the active task to its specialist brain…");
  try {
    const payload = await api(`/api/missions/${currentMission.id}/run-next`, {method: "POST"});
    renderWorkflow(payload.mission);
    setBrainControlState(payload.mission, payload.result
      ? `${payload.result.specialist_id} brain finished with ${payload.result.confidence}% confidence.`
      : payload.message || "Mission complete.");
  } catch (error) {
    console.error(error);
    setBrainControlState(currentMission, `Brain request failed: ${error.message}`);
  } finally {
    button.textContent = "Run next agent";
    setBrainControlState(currentMission, $("#brainActionStatus").textContent);
  }
});


$("#runFullTeam")?.addEventListener("click", async () => {
  if (!currentMission?.id) {
    setBrainControlState(null, "Create a mission first.");
    return;
  }

  const button = $("#runFullTeam");
  button.disabled = true;
  button.textContent = "Team executing…";
  setBrainControlState(currentMission, "Copilot is delegating the mission to the specialist team.");

  try {
    const payload = await api(`/api/missions/${currentMission.id}/run-team`, {
      method: "POST",
    });
    renderWorkflow(payload.mission);
    setBrainControlState(
      payload.mission,
      payload.mission.status === "waiting-approval"
        ? "Team paused at an approval gate."
        : `Team executed ${payload.steps_executed} specialist task(s).`
    );
  } catch (error) {
    setBrainControlState(currentMission, `Team error: ${error.message}`);
  } finally {
    button.textContent = "Run full team";
    setBrainControlState(currentMission, $("#brainActionStatus")?.textContent || "");
  }
});

$("#approveBrainStep")?.addEventListener("click", async () => {
  if (!currentMission?.id) {
    setBrainControlState(null, "No active mission is loaded.");
    return;
  }
  const button = $("#approveBrainStep");
  button.disabled = true;
  button.textContent = "Approving…";
  try {
    const mission = await api(`/api/missions/${currentMission.id}/approve`, {method: "POST"});
    renderWorkflow(mission);
    setBrainControlState(mission, "Waiting step approved. The next specialist can now run.");
  } catch (error) {
    console.error(error);
    setBrainControlState(currentMission, `Approval failed: ${error.message}`);
  } finally {
    button.textContent = "Approve waiting step";
    setBrainControlState(currentMission, $("#brainActionStatus").textContent);
  }
});

document.querySelectorAll(".suggestion-chip").forEach(button => {
  button.addEventListener("click", () => openMission(button.dataset.mission));
});

$("#connectorSearch").addEventListener("input", applyConnectorFilters);
$("#connectorFilter").addEventListener("change", applyConnectorFilters);

const connectorDialog = $("#connectorDialog");
$("#addConnectorBtn").addEventListener("click", () => connectorDialog.showModal());
$("#closeConnectorDialog").addEventListener("click", () => connectorDialog.close());
$("#cancelConnectorDialog").addEventListener("click", () => connectorDialog.close());

$("#connectorForm").addEventListener("submit", event => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form).entries());
  const connector = {
    id: `custom-${Date.now()}`,
    name: data.name,
    kind: data.kind,
    transport: data.transport,
    endpoint: data.endpoint,
    docs_url: data.docs_url,
    description: data.description,
    state: "configured",
    requires_approval: data.requires_approval === "on",
  };
  const saved = JSON.parse(localStorage.getItem("aios-connectors") || "[]");
  saved.push(connector);
  localStorage.setItem("aios-connectors", JSON.stringify(saved));
  connectorItems.push(connector);
  applyConnectorFilters();
  form.reset();
  connectorDialog.close();
});


function mobileToken() {
  return localStorage.getItem("aios-mobile-device-token");
}

async function loadPairedDevices() {
  try {
    const devices = await api("/api/mobile/devices");
    $("#pairedDevices").innerHTML = devices.length
      ? devices.map(device => `<div class="artifact"><span>✓</span><p>${device.name} — paired ${new Date(device.paired_at).toLocaleString()}</p></div>`).join("")
      : `<div class="brain-action-status">No paired devices yet.</div>`;
  } catch (error) {
    $("#pairedDevices").innerHTML = `<div class="brain-action-status">Error: ${error.message}</div>`;
  }
}

$("#generatePairingCode").addEventListener("click", async () => {
  try {
    const result = await api("/api/mobile/pairing-code", {method: "POST"});
    $("#pairingCodeBox").textContent = result.code;
  } catch (error) {
    $("#pairingCodeBox").textContent = `Error: ${error.message}`;
  }
});

$("#pairThisDevice").addEventListener("click", async () => {
  const deviceName = $("#mobileDeviceName").value.trim();
  const code = $("#mobilePairingCode").value.trim();
  if (!deviceName || code.length !== 6) {
    $("#mobilePairStatus").textContent = "Enter a device name and the six-digit code.";
    return;
  }

  try {
    const result = await api("/api/mobile/pair", {
      method: "POST",
      body: JSON.stringify({device_name: deviceName, code}),
    });
    localStorage.setItem("aios-mobile-device-token", result.device_token);
    $("#mobilePairStatus").textContent = `Paired as ${result.name}`;
    await loadPairedDevices();
  } catch (error) {
    $("#mobilePairStatus").textContent = `Error: ${error.message}`;
  }
});

document.querySelectorAll("[data-mobile-command]").forEach(button => {
  button.addEventListener("click", async () => {
    const token = mobileToken();
    if (!token) {
      $("#remoteCommandStatus").textContent = "This device is not paired.";
      return;
    }

    const command = button.dataset.mobileCommand;
    button.disabled = true;
    $("#remoteCommandStatus").textContent = `Sending ${command.replaceAll("_", " ")}â€¦`;

    try {
      const result = await api("/api/mobile/command", {
        method: "POST",
        body: JSON.stringify({
          device_token: token,
          command,
          mission_id: currentMission?.id || null,
        }),
      });
      $("#remoteCommandStatus").textContent = `${command.replaceAll("_", " ")} executed successfully.`;
      if (result.result?.mission) renderWorkflow(result.result.mission);
      else if (result.result?.id) renderWorkflow(result.result);
    } catch (error) {
      $("#remoteCommandStatus").textContent = `Error: ${error.message}`;
    } finally {
      button.disabled = false;
    }
  });
});

loadPairedDevices();
if (mobileToken()) {
  $("#mobilePairStatus").textContent = "This browser is paired.";
}

loadDashboard().then(() => {
  const startView = window.location.hash.replace("#", "");
  switchView(viewTitles[startView] ? startView : "mission");
}).catch(error => {
  console.error(error);
  $("#workflow").innerHTML = `<div class="empty-state"><h3>Backend unavailable</h3><p>${error.message}</p></div>`;
});

loadBudget();


Promise.allSettled([
  loadCopilotStatus(),
  loadCopilotConversation(),
]).then(() => {});




loadOllamaManager();

loadActiveModelIndicator();


function securityDate(timestamp) {
  if (!timestamp) return "Unknown";
  return new Date(timestamp * 1000).toLocaleString();
}

async function loadSecurityAdmin() {
  try {
    const [summary, sessions, audit] = await Promise.all([
      api("/api/security/summary"),
      api("/api/security/sessions"),
      api("/api/security/audit?limit=100"),
    ]);

    $("#securitySummaryCards").innerHTML = `
      <article><span>Active sessions</span><strong>${summary.active_sessions}</strong></article>
      <article><span>Failed logins · 1h</span><strong>${summary.failed_logins_last_hour}</strong></article>
      <article><span>Denied requests · 1h</span><strong>${summary.access_denied_last_hour}</strong></article>
      <article class="${summary.suspicious ? "security-warning" : ""}">
        <span>Security posture</span>
        <strong>${summary.suspicious ? "REVIEW" : "NORMAL"}</strong>
      </article>
    `;

    $("#securitySessions").innerHTML = sessions.items.length
      ? sessions.items.map(item => `
          <article class="security-session-item">
            <div>
              <strong>${escapeHtml(item.username || "Owner")}</strong>
              <span>${item.current ? "Current session" : "Other session"}</span>
              <small>Created ${securityDate(item.created_at)} · Expires ${securityDate(item.expires_at)}</small>
            </div>
            ${item.current
              ? '<span class="status-chip">CURRENT</span>'
              : `<button data-revoke-session="${escapeHtml(item.id)}">Revoke</button>`}
          </article>
        `).join("")
      : '<p class="muted-copy">No active sessions.</p>';

    $("#securityAuditEvents").innerHTML = audit.items.length
      ? audit.items.map(item => `
          <article class="security-audit-item">
            <strong>${escapeHtml(item.event || "event")}</strong>
            <span>${securityDate(item.at)}</span>
            <small>${escapeHtml(item.ip || "unknown")} · ${escapeHtml(item.path || "")}</small>
          </article>
        `).join("")
      : '<p class="muted-copy">No security events recorded.</p>';
  } catch (error) {
    showFrontendBoundary(error, "Security administration");
  }
}

$("#refreshSecurityAdmin")?.addEventListener("click", loadSecurityAdmin);

$("#securitySessions")?.addEventListener("click", async event => {
  const button = event.target.closest("[data-revoke-session]");
  if (!button) return;
  if (!confirm("Revoke this session?")) return;
  await api("/api/security/sessions/revoke", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({session_id: button.dataset.revokeSession}),
  });
  await loadSecurityAdmin();
});

$("#revokeOtherSessions")?.addEventListener("click", async () => {
  if (!confirm("Revoke every session except this one?")) return;
  await api("/api/security/sessions/revoke-others", {method: "POST"});
  await loadSecurityAdmin();
});

$("#passwordRotateForm")?.addEventListener("submit", async event => {
  event.preventDefault();
  const currentPassword = $("#currentOwnerPassword").value;
  const newPassword = $("#newOwnerPassword").value;
  const confirmation = $("#confirmOwnerPassword").value;
  if (newPassword !== confirmation) {
    $("#passwordRotateStatus").textContent = "New passwords do not match.";
    return;
  }
  try {
    const result = await api("/api/security/password/rotate", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    });
    $("#passwordRotateStatus").textContent =
      `Password rotated. ${result.sessions_revoked} session(s) revoked. Sign in again.`;
    setTimeout(() => location.reload(), 1200);
  } catch (error) {
    $("#passwordRotateStatus").textContent = error.message;
  }
});

if (location.hash === "#security-admin") loadSecurityAdmin();
window.addEventListener("hashchange", () => {
  if (location.hash === "#security-admin") loadSecurityAdmin();
});


async function loadToolsSkills() {
  try {
    const registry = await api("/api/tools/registry");
    $("#mcpServerList").innerHTML = registry.servers.length ? registry.servers.map(server => `<article class="mcp-server-item"><div><strong>${escapeHtml(server.name)}</strong><span>${escapeHtml(server.endpoint)}</span><small>${escapeHtml(server.permission)} / ${escapeHtml(server.last_status || "not_tested")}</small></div><div class="mcp-server-actions"><button data-mcp-test="${escapeHtml(server.id)}">Test</button><button data-mcp-toggle="${escapeHtml(server.id)}" data-enabled="${server.enabled}">${server.enabled ? "Disable" : "Enable"}</button><button data-mcp-remove="${escapeHtml(server.id)}">Remove</button></div></article>`).join("") : '<p class="muted-copy">No remote MCP servers registered.</p>';
    $("#registeredToolList").innerHTML = registry.tools.map(tool => `<article class="registered-tool-item"><div><strong>${escapeHtml(tool.name)}</strong><span>${escapeHtml(tool.description)}</span><small>${escapeHtml(tool.specialist)} / ${escapeHtml(tool.source)}</small></div><div><span class="status-chip">${escapeHtml(tool.permission)}</span>${tool.enabled && tool.permission === "read" ? `<button data-tool-run="${escapeHtml(tool.id)}">Run</button>` : ""}</div></article>`).join("");
    $("#registeredSkillList").innerHTML = registry.skills.map(skill => `<article class="registered-skill-item"><div><strong>${escapeHtml(skill.name)}</strong><span>${escapeHtml(skill.purpose)}</span><small>${escapeHtml(skill.specialist)} / risk ${escapeHtml(skill.risk)}</small></div><span class="status-chip">${skill.enabled ? "ENABLED" : "DISABLED"}</span></article>`).join("");
  } catch (error) { showFrontendBoundary(error, "Tools and skills"); }
}

$("#mcpServerForm")?.addEventListener("submit", async event => {
  event.preventDefault();
  await api("/api/mcp/servers", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({id: $("#mcpServerId").value.trim().toLowerCase(), name: $("#mcpServerName").value.trim(), transport: $("#mcpServerEndpoint").value.startsWith("https://") ? "https" : "http", endpoint: $("#mcpServerEndpoint").value.trim(), permission: $("#mcpServerPermission").value, notes: ""})});
  event.target.reset();
  await loadToolsSkills();
});

$("#mcpServerList")?.addEventListener("click", async event => {
  const testButton = event.target.closest("[data-mcp-test]");
  const toggleButton = event.target.closest("[data-mcp-toggle]");
  const removeButton = event.target.closest("[data-mcp-remove]");
  if (testButton) { const result = await api(`/api/mcp/servers/${testButton.dataset.mcpTest}/test`, {method: "POST"}); alert(`Server status: ${result.status}\n${result.detail || ""}`); await loadToolsSkills(); }
  if (toggleButton) { await api(`/api/mcp/servers/${toggleButton.dataset.mcpToggle}/toggle`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({enabled: toggleButton.dataset.enabled !== "true"})}); await loadToolsSkills(); }
  if (removeButton && confirm("Remove this MCP server registration?")) { await api(`/api/mcp/servers/${removeButton.dataset.mcpRemove}`, {method: "DELETE"}); await loadToolsSkills(); }
});

$("#registeredToolList")?.addEventListener("click", async event => {
  const button = event.target.closest("[data-tool-run]");
  if (!button) return;
  const argumentsValue = {};
  if (button.dataset.toolRun === "network.dns") { const hostname = prompt("Hostname to resolve:", "aios.bossayan.com"); if (!hostname) return; argumentsValue.hostname = hostname; }
  const result = await api("/api/tools/invoke", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({tool_id: button.dataset.toolRun, arguments: argumentsValue})});
  alert(JSON.stringify(result, null, 2).slice(0, 5000));
});

$("#refreshToolsSkills")?.addEventListener("click", loadToolsSkills);
if (location.hash === "#tools-skills") loadToolsSkills();
window.addEventListener("hashchange", () => { if (location.hash === "#tools-skills") loadToolsSkills(); });


async function loadGovernanceCenter() {
  const rulesHost = document.getElementById("governanceRules");
  const approvalsHost = document.getElementById("governanceApprovals");
  if (!rulesHost || !approvalsHost) return;

  try {
    const response = await fetch("/api/governance", { credentials: "same-origin" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const rules = data.rules || [];
    const approvals = data.approvals || [];
    const summary = data.summary || {};

    document.getElementById("governanceRuleCount").textContent = String(rules.length);
    document.getElementById("governancePendingCount").textContent = String(summary.pending || 0);
    document.getElementById("governanceApprovedCount").textContent =
      String((summary.approved || 0) + (summary.consumed || 0));
    document.getElementById("governanceBlockedCount").textContent = String(summary.blocked || 0);
    document.getElementById("governanceGateStatus").textContent = "ENFORCED";

    const ruleSummary = document.getElementById("governanceRuleSummary"); if (ruleSummary) ruleSummary.textContent = `${rules.length} RULES`;

    approvalsHost.innerHTML = approvals.length
      ? approvals.slice().reverse().map(item => `
        <div class="artifact">
          <span>${escapeHtml(String(item.status || "pending").toUpperCase())}</span>
          <p>
            <strong>${escapeHtml(item.tool_id || "unknown tool")}</strong><br>
            ${escapeHtml(item.specialist || "unknown specialist")} · ${escapeHtml(item.risk || "unknown risk")}<br>
            ${escapeHtml(item.reason || "No reason provided")}
          </p>
        </div>
      `).join("")
      : '<p class="muted-copy">No approval requests.</p>';
  } catch (error) {
    document.getElementById("governanceGateStatus").textContent = "ERROR";
    rulesHost.innerHTML = `<p class="muted-copy">Governance API unavailable: ${escapeHtml(String(error.message || error))}</p>`;
  }
}

document.addEventListener("click", event => {
  if (event.target.closest('[data-view="governance"]')) loadGovernanceCenter();
  if (event.target.closest("#refreshGovernance")) loadGovernanceCenter();
});


document.addEventListener("click", event => { if (event.target.closest("#openGovernanceRules")) { window.open("/assets/policy-rules.html?build=phase1d-governance-final", "_blank", "noopener,noreferrer"); } });




function reliabilityErrorMessage(error) {
  const errorId = error?.error_id || error?.payload?.error_id || "";
  return `${error?.message || "Request failed"}${errorId ? ` · Error ID: ${errorId}` : ""}`;
}

async function loadReliability() {
  const defectsHost = $("#reliabilityDefects");
  try {
    const payload = await api("/api/reliability");
    const summary = payload.summary || payload;
    $("#reliabilityOpenCount").textContent = String(summary.open ?? summary.open_defects ?? 0);
    $("#reliabilityCriticalCount").textContent = String(summary.critical ?? summary.critical_defects ?? 0);
    $("#reliabilityVerifiedCount").textContent = String(summary.verified ?? summary.verified_fixes ?? 0);
    $("#reliabilityDiagnosticTime").textContent = summary.last_diagnostic
      ? new Date(summary.last_diagnostic).toLocaleString()
      : "Never";
    const defectsPayload = await api("/api/reliability/defects");
    const defects = defectsPayload.items || defectsPayload.defects || [];
    defectsHost.innerHTML = defects.length
      ? defects.map(item => `
        <article class="reliability-defect-card ${escapeHtml(item.severity || "unknown")}">
          <div>
            <span>${escapeHtml((item.status || "unknown").replaceAll("_", " ").toUpperCase())}</span>
            <strong>${escapeHtml(item.title || "Untitled defect")}</strong>
            <p>${escapeHtml(item.summary || "")}</p>
          </div>
          <small>${escapeHtml(item.error_id || "No error ID")} · ${escapeHtml(item.category || "unknown")}</small>
        </article>`).join("")
      : '<p class="muted-copy">No defects recorded.</p>';
  } catch (error) {
    defectsHost.innerHTML = `<p class="security-login-error">${escapeHtml(reliabilityErrorMessage(error))}</p>`;
  }
}

async function runReliabilityDiagnostics() {
  const host = $("#reliabilityIntegrity");
  host.innerHTML = '<p class="muted-copy">Running safe diagnostics...</p>';
  try {
    const payload = await api("/api/reliability/diagnostics", {method: "POST", body: "{}"});
    const checks = payload.checks || payload.results || [];
    host.innerHTML = checks.length
      ? checks.map(check => `<div class="artifact"><span>${check.ok ? "PASS" : "FAIL"}</span><p><strong>${escapeHtml(check.name || check.id || "Check")}</strong><br>${escapeHtml(check.detail || check.message || "")}</p></div>`).join("")
      : '<p class="muted-copy">Diagnostics completed.</p>';
    await loadReliability();
  } catch (error) {
    host.innerHTML = `<p class="security-login-error">${escapeHtml(reliabilityErrorMessage(error))}</p>`;
  }
}

function openMissionLifecycleDialog(action, mission) {
  const dialog = $("#missionLifecycleDialog");
  $("#missionLifecycleId").value = mission.id;
  $("#missionLifecycleAction").value = action;
  $("#missionLifecycleTitle").textContent =
    action === "archive" ? "Archive mission" :
    action === "restore" ? "Restore mission" :
    "Delete mission permanently";
  $("#missionLifecycleWarning").textContent =
    action === "delete"
      ? `This permanently deletes "${mission.title || "Untitled mission"}" (${mission.id}). This cannot be undone.`
      : action === "archive"
        ? "Archive removes this mission from normal history but keeps it available for restore."
        : "Restore returns this mission to normal Mission History.";
  const deleting = action === "delete";
  $("#missionDeleteConfirmationLabel").classList.toggle("hidden", !deleting);
  $("#missionDeleteTitleLabel").classList.toggle("hidden", !deleting);
  $("#missionDeleteApprovalLabel").classList.toggle("hidden", !deleting);
  $("#missionDeleteConfirmation").value = "";
  $("#missionDeleteTitleConfirmation").value = "";
  $("#missionDeleteApprovalId").value = "";
  $("#missionDeleteTitleConfirmation").dataset.expectedTitle = mission.title || "Untitled mission";
  $("#missionLifecycleStatus").textContent = deleting
    ? "Permanent deletion requires an approved, single-use governance approval."
    : "";
  dialog.showModal();
}

async function executeMissionLifecycle(action, missionId) {
  if (action === "archive") {
    return api(`/api/missions/${missionId}/archive`, {method: "POST", body: "{}"});
  }
  if (action === "restore") {
    return api(`/api/missions/${missionId}/restore`, {method: "POST", body: "{}"});
  }
  return api(`/api/missions/${missionId}`, {
    method: "DELETE",
    body: JSON.stringify({
      confirm_mission_id: $("#missionDeleteConfirmation").value.trim(),
      confirm_title: $("#missionDeleteTitleConfirmation").value.trim(),
      approval_id: $("#missionDeleteApprovalId").value.trim(),
    }),
  });
}

document.addEventListener("click", event => {
  const lifecycleButton = event.target.closest("[data-mission-lifecycle]");
  if (lifecycleButton) {
    openMissionLifecycleDialog(lifecycleButton.dataset.missionLifecycle, {
      id: lifecycleButton.dataset.missionId,
      title: lifecycleButton.dataset.missionTitle,
    });
  }
});

$("#missionLifecycleForm")?.addEventListener("submit", async event => {
  event.preventDefault();
  const action = $("#missionLifecycleAction").value;
  const missionId = $("#missionLifecycleId").value;
  const status = $("#missionLifecycleStatus");
  try {
    status.textContent = "Working...";
    await executeMissionLifecycle(action, missionId);
    $("#missionLifecycleDialog").close();
    if (typeof loadMissionHistory === "function") await loadMissionHistory();
    if (typeof showAiosToast === "function") {
      showAiosToast({
        title: action === "archive" ? "Mission archived" : action === "restore" ? "Mission restored" : "Mission deleted",
        message: action === "archive" ? "The mission can be restored from Archived missions." : "Mission lifecycle updated.",
        type: "success",
      });
    }
  } catch (error) {
    status.textContent = reliabilityErrorMessage(error);
  }
});

$("#cancelMissionLifecycle")?.addEventListener("click", () => $("#missionLifecycleDialog")?.close());
$("#runReliabilityDiagnostics")?.addEventListener("click", runReliabilityDiagnostics);
$("#refreshReliability")?.addEventListener("click", loadReliability);



function networkHealthStatusClass(status) {
  return `network-health-${String(status || "unknown").replaceAll("_", "-")}`;
}

async function loadNetworkHealth() {
  const host = $("#networkHealthCards");
  host.innerHTML = '<p class="muted-copy">Running checks...</p>';
  try {
    const payload = await api("/api/network-health");
    $("#networkOverallStatus").textContent =
      String(payload.status || "unknown").toUpperCase();
    $("#networkCpu").textContent = `${payload.desktop?.cpu_percent ?? 0}%`;
    $("#networkMemory").textContent = `${payload.desktop?.memory_percent ?? 0}%`;
    $("#networkCheckedAt").textContent = payload.checked_at
      ? new Date(payload.checked_at).toLocaleString()
      : "Never";
    host.innerHTML = (payload.checks || []).map(item => `
      <article class="network-health-card ${networkHealthStatusClass(item.status)}">
        <div class="network-health-card-head">
          <div>
            <p class="eyebrow">${escapeHtml(String(item.status || "unknown").toUpperCase())}</p>
            <h3>${escapeHtml(item.name || item.id)}</h3>
          </div>
          <span>${item.latency_ms == null ? "—" : `${escapeHtml(String(item.latency_ms))} ms`}</span>
        </div>
        <p>${escapeHtml(item.detail || "")}</p>
        ${item.likely_cause
          ? `<small><strong>Likely cause:</strong> ${escapeHtml(item.likely_cause)}</small>`
          : ""}
        <small>
          <strong>Recommended:</strong>
          ${escapeHtml(item.recommended_action || "No action required.")}
        </small>
        ${item.error_id
          ? `<code>Error ID: ${escapeHtml(item.error_id)}</code>`
          : ""}
      </article>`).join("");
  } catch (error) {
    host.innerHTML =
      `<p class="security-login-error">${escapeHtml(reliabilityErrorMessage(error))}</p>`;
  }
}

$("#runNetworkHealth")?.addEventListener("click", loadNetworkHealth);



let latestNetworkDiagnosticReport = null;

function renderDiagnosticWorkflow(report) {
  const host = $("#networkWorkflowProgress");
  const workflows = report.workflow || [];
  host.innerHTML = workflows.map(group => `
    <article class="diagnostic-workflow-group">
      <div class="diagnostic-workflow-head">
        <strong>${escapeHtml(group.name || group.id)}</strong>
        <span>COMPLETE</span>
      </div>
      <ol>
        ${(group.steps || []).map(step => `
          <li>
            <span class="diagnostic-step-state">✓</span>
            <span>${escapeHtml(step)}</span>
          </li>`).join("")}
      </ol>
    </article>`).join("");
}

function networkDiagnosticText(report) {
  const lines = [
    `AIOS Network & Desktop Diagnostic`,
    `Generated: ${report.generated_at || "unknown"}`,
    `Status: ${String(report.status || "unknown").toUpperCase()}`,
    `Root cause: ${report.root_cause_summary || "Not available"}`,
    "",
    "Checks:",
  ];
  for (const item of report.checks || []) {
    lines.push(
      `- ${item.name || item.id}: ${String(item.status || "unknown").toUpperCase()}` +
      `${item.latency_ms == null ? "" : ` (${item.latency_ms} ms)`}`,
      `  Detail: ${item.detail || ""}`,
      `  Recommended: ${item.recommended_action || "No action required."}`
    );
  }
  return lines.join("\n");
}

async function loadNetworkDiagnosticWorkflow() {
  const progress = $("#networkWorkflowProgress");
  const started = performance.now();
  progress.innerHTML = `
    <article class="diagnostic-workflow-group running">
      <div class="diagnostic-workflow-head">
        <strong>Running live diagnostic workflow</strong>
        <span id="networkWorkflowElapsed">0.0 s</span>
      </div>
      <ol>
        <li><span class="diagnostic-step-state">…</span><span>Collecting safe health signals</span></li>
        <li><span class="diagnostic-step-state">…</span><span>Comparing local and public health</span></li>
        <li><span class="diagnostic-step-state">…</span><span>Building root-cause summary</span></li>
      </ol>
    </article>`;
  const timer = window.setInterval(() => {
    const elapsed = $("#networkWorkflowElapsed");
    if (elapsed) elapsed.textContent = `${((performance.now() - started) / 1000).toFixed(1)} s`;
  }, 100);

  try {
    const report = await api("/api/network-health/workflow");
    latestNetworkDiagnosticReport = report;
    renderDiagnosticWorkflow(report);
    const rootCause = $("#networkRootCause");
    rootCause.classList.remove("hidden");
    rootCause.innerHTML = `
      <p class="eyebrow">ROOT CAUSE SUMMARY</p>
      <h3>${escapeHtml(report.root_cause_summary || "No summary available.")}</h3>
      <p>Completed in ${((performance.now() - started) / 1000).toFixed(1)} seconds.</p>`;
    return report;
  } finally {
    window.clearInterval(timer);
  }
}

const originalLoadNetworkHealth = loadNetworkHealth;
loadNetworkHealth = async function() {
  await originalLoadNetworkHealth();
  try {
    await loadNetworkDiagnosticWorkflow();
  } catch (error) {
    const progress = $("#networkWorkflowProgress");
    progress.innerHTML = `<p class="security-login-error">${escapeHtml(reliabilityErrorMessage(error))}</p>`;
  }
};

$("#retryNetworkHealth")?.addEventListener("click", loadNetworkHealth);

$("#copyNetworkHealthReport")?.addEventListener("click", async () => {
  if (!latestNetworkDiagnosticReport) {
    await loadNetworkHealth();
  }
  await navigator.clipboard.writeText(networkDiagnosticText(latestNetworkDiagnosticReport));
  if (typeof showAiosToast === "function") {
    showAiosToast({
      title: "Diagnostic report copied",
      message: "The safe health report is in your clipboard.",
      type: "success",
    });
  }
});

$("#downloadNetworkHealthReport")?.addEventListener("click", async () => {
  if (!latestNetworkDiagnosticReport) {
    await loadNetworkHealth();
  }
  const blob = new Blob(
    [JSON.stringify(latestNetworkDiagnosticReport, null, 2)],
    {type: "application/json"}
  );
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `aios-network-diagnostic-${new Date().toISOString().replaceAll(":", "-")}.json`;
  link.click();
  URL.revokeObjectURL(url);
});



async function loadBrainVaultHealth() {
  try {
    const payload = await api("/api/brain-vault/health");
    $("#brainVaultStatus").textContent = String(payload.status || "unknown").toUpperCase();
    $("#brainVaultNotes").textContent = String(payload.note_count ?? 0);
    $("#brainVaultIndexed").textContent = String(payload.indexed_count ?? 0);
    $("#brainVaultPath").textContent = payload.vault_root || "Not configured";
  } catch (error) {
    $("#brainVaultMessage").textContent = reliabilityErrorMessage(error);
  }
}

async function searchBrainVault(query) {
  const host = $("#brainVaultResults");
  host.innerHTML = '<p class="muted-copy">Searching...</p>';
  try {
    const payload = await api(`/api/brain-vault/search?query=${encodeURIComponent(query)}`);
    const items = payload.items || [];
    host.innerHTML = items.length
      ? items.map(item => `
        <article class="brain-vault-result">
          <strong>${escapeHtml(item.name || item.path)}</strong>
          <code>${escapeHtml(item.path || "")}</code>
          <p>${escapeHtml(item.preview || "")}</p>
        </article>`).join("")
      : '<p class="muted-copy">No matching notes found.</p>';
  } catch (error) {
    host.innerHTML = `<p class="security-login-error">${escapeHtml(reliabilityErrorMessage(error))}</p>`;
  }
}

$("#refreshBrainVault")?.addEventListener("click", async () => {
  await Promise.all([loadBrainVaultHealth(), loadBrainVaultSyncStatus()]);
});

$("#brainVaultSearchForm")?.addEventListener("submit", async event => {
  event.preventDefault();
  await searchBrainVault($("#brainVaultSearchInput").value.trim());
});

$("#exportMissionsToVault")?.addEventListener("click", async () => {
  const message = $("#brainVaultMessage");
  try {
    message.textContent = "Exporting missions...";
    const payload = await api("/api/brain-vault/export-missions", {
      method: "POST",
      body: "{}",
    });
    message.textContent = `Exported ${payload.count ?? 0} missions to the Brain Vault.`;
    await loadBrainVaultHealth();
  } catch (error) {
    message.textContent = reliabilityErrorMessage(error);
  }
});

$("#backupBrainVault")?.addEventListener("click", async () => {
  const message = $("#brainVaultMessage");
  try {
    message.textContent = "Creating backup...";
    const payload = await api("/api/brain-vault/backup", {
      method: "POST",
      body: "{}",
    });
    message.textContent = `Backup created: ${payload.path || "unknown"}`;
  } catch (error) {
    message.textContent = reliabilityErrorMessage(error);
  }
});

$("#brainVaultPhaseForm")?.addEventListener("submit", async event => {
  event.preventDefault();
  const message = $("#brainVaultMessage");
  try {
    const payload = await api("/api/brain-vault/phase-summary", {
      method: "POST",
      body: JSON.stringify({
        phase: $("#brainVaultPhaseName").value.trim(),
        status: $("#brainVaultPhaseStatus").value,
        summary: $("#brainVaultPhaseSummary").value.trim(),
      }),
    });
    message.textContent = `Phase summary saved: ${payload.path || "unknown"}`;
    await loadBrainVaultHealth();
  } catch (error) {
    message.textContent = reliabilityErrorMessage(error);
  }
});



async function loadBrainVaultSyncStatus() {
  try {
    const payload = await api("/api/brain-vault/sync-status");
    $("#brainVaultAutosave").textContent =
      payload.autosave_enabled ? "ENABLED" : "DISABLED";
    $("#brainVaultLastSync").textContent = payload.checked_at
      ? new Date(payload.checked_at).toLocaleString()
      : "Never";
  } catch (error) {
    $("#brainVaultMessage").textContent = reliabilityErrorMessage(error);
  }
}

$("#syncBrainVaultNow")?.addEventListener("click", async () => {
  const message = $("#brainVaultMessage");
  try {
    message.textContent = "Synchronizing changed missions...";
    const payload = await api("/api/brain-vault/sync", {
      method: "POST",
      body: "{}",
    });
    message.textContent =
      `Sync completed: ${payload.exported ?? 0} changed, ` +
      `${payload.unchanged ?? 0} unchanged, ${payload.total ?? 0} total.`;
    await Promise.all([loadBrainVaultHealth(), loadBrainVaultSyncStatus()]);
  } catch (error) {
    message.textContent = reliabilityErrorMessage(error);
  }
});



function renderBrainMemoryPreview(payload) {
  const host = $("#brainMemoryPreview");
  const citations = payload.citations || [];
  if (!citations.length) {
    host.innerHTML = '<p class="muted-copy">No relevant Brain Vault notes found.</p>';
    return;
  }
  host.innerHTML = `
    <div class="brain-memory-context">
      <p class="eyebrow">RETRIEVED MEMORY</p>
      <p>${escapeHtml(payload.context || "")}</p>
    </div>
    <div class="brain-memory-citations">
      ${citations.map((item, index) => `
        <article class="brain-memory-citation">
          <div class="brain-memory-citation-head">
            <strong>[${index + 1}] ${escapeHtml(item.title || item.path)}</strong>
            <span>Score ${escapeHtml(String(item.score ?? 0))}</span>
          </div>
          <code>${escapeHtml(item.path || "")}</code>
          <p>${escapeHtml(item.preview || "")}</p>
        </article>`).join("")}
    </div>`;
}

$("#brainMemoryPreviewForm")?.addEventListener("submit", async event => {
  event.preventDefault();
  const host = $("#brainMemoryPreview");
  host.innerHTML = '<p class="muted-copy">Searching Brain Vault...</p>';
  try {
    const payload = await api("/api/brain-vault/memory-preview", {
      method: "POST",
      body: JSON.stringify({
        query: $("#brainMemoryQuery").value.trim(),
        specialist: $("#brainMemorySpecialist").value,
        limit: 5,
      }),
    });
    renderBrainMemoryPreview(payload);
  } catch (error) {
    host.innerHTML =
      `<p class="security-login-error">${escapeHtml(reliabilityErrorMessage(error))}</p>`;
  }
});



function escapeProjectHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function projectCard(project) {
  const specialists = (project.specialists || []).map(escapeProjectHtml).join(", ") || "Not assigned";
  const repository = escapeProjectHtml(project.github_repository || "Not linked");
  const branch = escapeProjectHtml(project.github_branch || "Not linked");
  const vault = escapeProjectHtml(project.brain_vault_path || "Not linked");
  return `
    <article class="panel project-card" data-project-id="${escapeProjectHtml(project.id)}">
      <div class="project-card-head">
        <div><p class="eyebrow">${escapeProjectHtml(project.status).toUpperCase()}</p><h2>${escapeProjectHtml(project.name)}</h2></div>
        <span class="status-chip">${Number(project.progress || 0)}%</span>
      </div>
      <p>${escapeProjectHtml(project.objective)}</p>
      <div class="project-progress"><span style="width:${Number(project.progress || 0)}%"></span></div>
      <dl class="project-meta">
        <div><dt>Specialists</dt><dd>${specialists}</dd></div>
        <div><dt>GitHub</dt><dd>${repository}</dd></div>
        <div><dt>Branch</dt><dd>${branch}</dd></div>
        <div><dt>Brain Vault</dt><dd>${vault}</dd></div>
      </dl>
      <div class="dialog-actions">
        <button class="project-progress-button" data-project-id="${escapeProjectHtml(project.id)}" data-progress="${Number(project.progress || 0)}">Update progress</button>
        <button class="project-open-memory" data-path="${vault}">Open memory</button>
      </div>
    </article>`;
}

async function loadProjects() {
  const grid = $("#projectGrid");
  if (!grid) return;
  try {
    const payload = await api("/api/projects");
    const projects = payload.projects || [];
    $("#projectTotal").textContent = projects.length;
    $("#projectActive").textContent = projects.filter(item => item.status === "active").length;
    $("#projectBlocked").textContent = projects.filter(item => item.status === "blocked").length;
    const average = projects.length
      ? Math.round(projects.reduce((sum, item) => sum + Number(item.progress || 0), 0) / projects.length)
      : 0;
    $("#projectAverageProgress").textContent = `${average}%`;
    grid.innerHTML = projects.length
      ? projects.map(projectCard).join("")
      : `<article class="panel empty-project"><h2>No projects yet</h2><p>Create the first persistent AIOS project.</p></article>`;
    wireProjectCards();
  } catch (error) {
    grid.innerHTML = `<article class="panel"><h2>Projects unavailable</h2><p>${escapeProjectHtml(error.message)}</p></article>`;
  }
}

function wireProjectCards() {
  document.querySelectorAll(".project-progress-button").forEach(button => {
    button.addEventListener("click", async () => {
      const current = Number(button.dataset.progress || 0);
      const raw = window.prompt("Set project progress from 0 to 100:", String(current));
      if (raw === null) return;
      const progress = Math.max(0, Math.min(Number(raw), 100));
      if (!Number.isFinite(progress)) return;
      await api(`/api/projects/${button.dataset.projectId}`, {
        method: "POST",
        body: JSON.stringify({progress}),
      });
      await loadProjects();
    });
  });
  document.querySelectorAll(".project-open-memory").forEach(button => {
    button.addEventListener("click", () => {
      switchView("brain-vault");
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const open = $("#openProjectForm");
  const close = $("#closeProjectForm");
  const panel = $("#projectCreatePanel");
  open?.addEventListener("click", () => panel?.classList.remove("hidden"));
  close?.addEventListener("click", () => panel?.classList.add("hidden"));

  $("#projectForm")?.addEventListener("submit", async event => {
    event.preventDefault();
    const status = $("#projectFormStatus");
    status.textContent = "Creating project...";
    try {
      const payload = {
        name: $("#projectName").value.trim(),
        objective: $("#projectObjective").value.trim(),
        status: $("#projectStatus").value,
        github_repository: $("#projectGithubRepository").value.trim(),
        github_branch: $("#projectGithubBranch").value.trim(),
        brain_vault_path: $("#projectBrainVaultPath").value.trim(),
        specialists: $("#projectSpecialists").value.split(",").map(item => item.trim()).filter(Boolean),
      };
      await api("/api/projects", {method: "POST", body: JSON.stringify(payload)});
      event.target.reset();
      panel?.classList.add("hidden");
      status.textContent = "Project created.";
      await loadProjects();
    } catch (error) {
      status.textContent = error.message;
    }
  });

  document.querySelector('.nav-item[data-view="projects"]')?.addEventListener("click", loadProjects);
  if (window.location.hash === "#projects") loadProjects();
});
