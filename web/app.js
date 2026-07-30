const dateInput = document.querySelector("#date-input");
const title = document.querySelector("#summary-title");
const summaryLine = document.querySelector("#summary-line");
const cards = document.querySelector("#cards");
const dialog = document.querySelector("#evidence-dialog");
const evidenceContent = document.querySelector("#evidence-content");
const closeDialog = document.querySelector("#close-dialog");
const quarterlyReview = document.querySelector("#quarterly-review");
const operationStatus = document.querySelector("#operation-status");
const diagnosticStatus = document.querySelector("#diagnostic-status");

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }
  return payload;
}

const api = {
  async analyzeCompany(tsCode, period) {
    return requestJson("/api/analyze/company", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ts_code: tsCode, period }),
    });
  },

  async analyzeDisclosureDay(date) {
    return requestJson("/api/analyze/disclosure-day", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date }),
    });
  },

  async scanDisclosureDay(date) {
    return requestJson("/api/scan/disclosure-day", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date }),
    });
  },

  async sendFeishuDisclosureDay(date) {
    return requestJson(`/api/notify/feishu/disclosure-day/${date}`, { method: "POST" });
  },

  async pollRss() {
    return requestJson("/api/rss/poll", { method: "POST" });
  },
};

function setStatus(payload) {
  operationStatus.textContent = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
}

function severityClass(card) {
  if (card.max_severity === "RED") return "red";
  if (card.max_severity === "YELLOW") return "yellow";
  return "ok";
}

function severityIcon(card) {
  if (card.max_severity === "RED") return "🔴";
  if (card.max_severity === "YELLOW") return "🟡";
  return "✅";
}

async function showEvidence(card, finding) {
  const response = await fetch(`/api/evidence/${card.ts_code}/${card.period}/${finding.rule_id}`);
  const evidence = await response.json();
  evidenceContent.textContent = JSON.stringify(evidence, null, 2);
  dialog.showModal();
}

function renderCard(card) {
  const el = document.createElement("article");
  el.className = `card ${severityClass(card)}`;
  el.innerHTML = `
    <h2>${severityIcon(card)} ${card.ts_code} ${card.period}</h2>
    <p>${card.fact_line}</p>
    <div class="findings"></div>
    <p>${card.attribution || "归因生成失败或未启用"}</p>
    <p>${card.market_line}</p>
  `;
  const findingsEl = el.querySelector(".findings");
  if (card.findings.length === 0) {
    findingsEl.innerHTML = `<p>未见异常</p>`;
  } else {
    for (const finding of card.findings) {
      const item = document.createElement("div");
      item.className = "finding";
      item.innerHTML = `<strong>${finding.title}</strong><p>${finding.detail}</p>`;
      const button = document.createElement("button");
      button.textContent = "依据";
      button.addEventListener("click", () => showEvidence(card, finding));
      item.appendChild(button);
      findingsEl.appendChild(item);
    }
  }
  return el;
}

function renderDaily(summary) {
  title.textContent = `${summary.date} 财报研判 · 覆盖池 ${summary.coverage_count} 只`;
  summaryLine.textContent = `今日披露 ${summary.disclosed_count} 家 | 需优先关注 ${summary.red_count} | 留意 ${summary.yellow_count} | 未见异常 ${summary.ok_count}`;
  cards.innerHTML = "";
  for (const card of summary.cards) {
    cards.appendChild(renderCard(card));
  }
}

function renderDiagnostics(result) {
  diagnosticStatus.innerHTML = `
    <h2>扫描诊断</h2>
    <p>披露 ${result.disclosed_count} / 覆盖 ${result.coverage_count} | OK ${result.ok_count} | 待数据 ${result.data_not_ready_count} | 不完整 ${result.data_incomplete_count} | 错误 ${result.error_count}</p>
    <table>
      <thead><tr><th>代码</th><th>报告期</th><th>行业</th><th>状态</th><th>原因</th></tr></thead>
      <tbody>${result.events.map((event) => `<tr><td>${event.ts_code}</td><td>${event.period}</td><td>${event.industry || "unknown"}</td><td>${event.status}</td><td>${event.message}</td></tr>`).join("")}</tbody>
    </table>
  `;
}

async function loadDaily(date) {
  const response = await fetch(`/api/daily/${date}`);
  if (!response.ok) return;
  renderDaily(await response.json());
}

async function loadQuarterly() {
  const response = await fetch("/api/quarterly");
  if (!response.ok) return;
  const review = await response.json();
  quarterlyReview.innerHTML = `
    <div class="metric"><span>区间</span><strong>${review.period_label}</strong></div>
    <div class="metric"><span>覆盖池</span><strong>${review.coverage_count}</strong></div>
    <div class="metric"><span>已披露</span><strong>${review.disclosed_count}</strong></div>
    <div class="metric"><span>命中</span><strong>${review.finding_count}</strong></div>
    <div class="metric"><span>精确率</span><strong>${review.precision_pct ?? "待复核"}</strong></div>
  `;
  for (const item of review.top_rules) {
    const metric = document.createElement("div");
    metric.className = "metric";
    metric.innerHTML = `<span>${item.rule_id}</span><strong>${item.count}</strong>`;
    quarterlyReview.appendChild(metric);
  }
}

closeDialog.addEventListener("click", () => dialog.close());
dateInput.addEventListener("change", () => loadDaily(dateInput.value));

document.querySelector("#analyze-company").addEventListener("click", async () => {
  try {
    const tsCode = document.querySelector("#company-ts-code").value.trim();
    const period = document.querySelector("#company-period").value.trim();
    const result = await api.analyzeCompany(tsCode, period);
    setStatus(result);
    if (result.card) {
      cards.innerHTML = "";
      cards.appendChild(renderCard(result.card));
    }
  } catch (error) {
    setStatus({ error: error.message });
  }
});

document.querySelector("#analyze-disclosure-day").addEventListener("click", async () => {
  try {
    const date = document.querySelector("#disclosure-date").value.trim();
    const summary = await api.analyzeDisclosureDay(date);
    setStatus(summary);
    renderDaily(summary);
  } catch (error) {
    setStatus({ error: error.message });
  }
});

document.querySelector("#scan-disclosure-day").addEventListener("click", async () => {
  try {
    const date = document.querySelector("#disclosure-date").value.trim();
    const result = await api.scanDisclosureDay(date);
    setStatus(result);
    renderDiagnostics(result);
  } catch (error) {
    setStatus({ error: error.message });
  }
});

document.querySelector("#send-feishu").addEventListener("click", async () => {
  try {
    const date = document.querySelector("#disclosure-date").value.trim();
    setStatus(await api.sendFeishuDisclosureDay(date));
  } catch (error) {
    setStatus({ error: error.message });
  }
});

document.querySelector("#poll-rss").addEventListener("click", async () => {
  try {
    setStatus(await api.pollRss());
  } catch (error) {
    setStatus({ error: error.message });
  }
});

loadDaily(dateInput.value);
loadQuarterly();
