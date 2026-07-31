"use strict";

/* ---------- DOM 引用 ---------- */

const el = (id) => document.getElementById(id);

const appBarTitle = el("app-bar-title");
const appBarCrumb = el("app-bar-crumb");
const summaryTitle = el("summary-title");
const summaryLine = el("summary-line");
const summaryLede = el("summary-lede");
const summaryMetrics = el("summary-metrics");
const summaryChips = el("summary-chips");
const summaryDistribution = el("summary-distribution");
const cardGroups = el("card-groups");
const companyDetail = el("company-detail");
const companyPermalinkHint = el("company-permalink-hint");
const diagnosticStatus = el("diagnostic-status");
const quarterlyReview = el("quarterly-review");
const operationStatus = el("operation-status");
const metaStatus = el("meta-status");
const reviewMetrics = el("review-metrics");
const reviewTable = el("review-table");

const evidenceDialog = el("evidence-dialog");
const evidenceContent = el("evidence-content");
const feishuDialog = el("feishu-dialog");
const feishuPreviewText = el("feishu-preview-text");
const feishuPreviewMeta = el("feishu-preview-meta");
const feishuPreviewHint = el("feishu-preview-hint");
const sendFeishuButton = el("send-feishu");
const scanButton = el("start-disclosure-scan");

const snackbar = el("snackbar");
const snackbarText = el("snackbar-text");

/* ---------- 状态 ---------- */

const REVIEW_STORAGE_KEY = "tradeeye.review.labels.v1";
/* 严重度做双重编码：颜色 + 文字标签，色盲或黑白打印下仍可分辨 */
const SEVERITY_META = {
  RED: { label: "需优先追问", tag: "RED", cls: "red", note: "规则判定为红色，建议当日跟进" },
  YELLOW: { label: "值得留意", tag: "YELLOW", cls: "yellow", note: "阈值边缘，建议结合行业对比" },
  OK: { label: "未见异常", tag: "OK", cls: "ok", note: "6 条算术规则全部未触发" },
  DATA: { label: "数据问题", tag: "DATA", cls: "data", note: "有披露事件但未出卡" },
};

const state = {
  meta: { coverage_count: 0, company_names: {}, tushare_ready: false, feishu_ready: false },
  bundle: null,
  filter: "all",
  previewDate: null,
  activeJobId: null,
  jobPollTimer: null,
  reviewLabels: loadReviewLabels(),
};

/* ---------- 日期与报告期 ---------- */

/* 后端与 hash URL 一律用 YYYYMMDD；<input type="date"> 只接受 YYYY-MM-DD，因此在边界转换 */
function toApiDate(value) {
  return String(value ?? "").replace(/-/g, "").trim();
}

function toInputDate(value) {
  const digits = toApiDate(value);
  if (!/^\d{8}$/.test(digits)) return "";
  return `${digits.slice(0, 4)}-${digits.slice(4, 6)}-${digits.slice(6, 8)}`;
}

function selectedDate() {
  return toApiDate(el("disclosure-date").value);
}

/* 报告期只有四个法定季末，倒序列出已过去的季末，未到的季末不可能有财报 */
function periodOptions(years = 4) {
  const now = new Date();
  const today = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}`;
  const options = [];
  for (let offset = 0; offset < years; offset += 1) {
    const year = now.getFullYear() - offset;
    for (const suffix of ["1231", "0930", "0630", "0331"]) {
      const period = `${year}${suffix}`;
      if (period <= today) options.push(period);
    }
  }
  return options;
}

function periodLabel(period) {
  const quarter = { "0331": "一季报", "0630": "半年报", "0930": "三季报", "1231": "年报" }[period.slice(4)];
  return `${period.slice(0, 4)} ${quarter || period}`;
}

function ensurePeriodOption(period) {
  const select = el("company-period");
  if (!period) return;
  if ([...select.options].some((option) => option.value === period)) {
    select.value = period;
    return;
  }
  const option = document.createElement("option");
  option.value = period;
  option.textContent = periodLabel(period);
  select.prepend(option);
  select.value = period;
}

function initPeriodSelect(defaultPeriod) {
  const select = el("company-period");
  select.replaceChildren(
    ...periodOptions().map((period) => {
      const option = document.createElement("option");
      option.value = period;
      option.textContent = periodLabel(period);
      return option;
    })
  );
  ensurePeriodOption(defaultPeriod);
}

/* ---------- 通用工具 ---------- */

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }
  return payload;
}

const api = {
  async getMeta() {
    return requestJson("/api/meta");
  },

  async analyzeCompany(tsCode, period) {
    return requestJson("/api/analyze/company", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ts_code: tsCode, period }),
    });
  },

  async startDisclosureDayJob(date) {
    return requestJson("/api/disclosure-day/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date }),
    });
  },

  async getDisclosureDayJob(jobId) {
    return requestJson(`/api/disclosure-day/jobs/${jobId}`);
  },

  async cancelDisclosureDayJob(jobId) {
    return requestJson(`/api/disclosure-day/jobs/${jobId}/cancel`, { method: "POST" });
  },

  async previewFeishuDisclosureDay(date) {
    return requestJson(`/api/notify/feishu/disclosure-day/${date}/preview`, { method: "POST" });
  },

  async sendFeishuDisclosureDay(date) {
    return requestJson(`/api/notify/feishu/disclosure-day/${date}`, { method: "POST" });
  },

  async pollRss() {
    return requestJson("/api/rss/poll", { method: "POST" });
  },

  async getEvidence(tsCode, period, ruleId) {
    return requestJson(`/api/evidence/${tsCode}/${period}/${ruleId}`);
  },

  async getQuarterly() {
    return requestJson("/api/quarterly");
  },
};

function setStatus(payload) {
  operationStatus.textContent = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
}

let snackbarTimer = null;
function notify(message, isError = false) {
  snackbarText.textContent = message;
  snackbar.classList.toggle("error", isError);
  snackbar.hidden = false;
  clearTimeout(snackbarTimer);
  snackbarTimer = setTimeout(() => {
    snackbar.hidden = true;
  }, 4200);
}

/* 扫描耗时提示：真实耗时未知，按 M3 规范用 indeterminate 进度条 + 已用时计数，不伪造百分比 */
function createProgress(progressId, messageId, elapsedId) {
  const root = el(progressId);
  const messageEl = el(messageId);
  const elapsedEl = el(elapsedId);
  let timer = null;

  return {
    start(message) {
      messageEl.textContent = message;
      elapsedEl.textContent = "0.0s";
      root.hidden = false;
      root.dataset.mode = "indeterminate";
      const startedAt = performance.now();
      clearInterval(timer);
      timer = setInterval(() => {
        elapsedEl.textContent = `${((performance.now() - startedAt) / 1000).toFixed(1)}s`;
      }, 100);
      return startedAt;
    },
    stop(startedAt, message) {
      clearInterval(timer);
      const seconds = (performance.now() - startedAt) / 1000;
      elapsedEl.textContent = `${seconds.toFixed(1)}s`;
      messageEl.textContent = message;
      // 完成后停掉动画并填满，否则仍在滚动的进度条会被读成还在跑
      root.dataset.mode = "done";
      return seconds;
    },
    hide() {
      clearInterval(timer);
      root.hidden = true;
    },
  };
}

/* 扫描按钮单节点三态。用两个节点互相 hide 的话，disabled 状态要在多处同步——
   之前正是漏在这里：两个 catch 分支和 finishDisclosureJob 各自手动重置了一遍。 */
function setScanState(state) {
  scanButton.dataset.state = state;
  const scanning = state === "scanning" || state === "cancelling";
  scanButton.textContent = scanning ? "停止扫描" : "开始扫描";
  scanButton.classList.toggle("outlined", scanning);
  // cancelling 期间禁用，避免重复发取消请求
  scanButton.disabled = state === "cancelling";
}

const scanProgress = createProgress("scan-progress", "progress-message", "progress-elapsed");
const companyProgress = createProgress("company-progress", "company-progress-message", "company-progress-elapsed");

function displayName(tsCode) {
  return state.meta.company_names[tsCode] || "";
}

function severityKey(card) {
  if (card.max_severity === "RED") return "RED";
  if (card.max_severity === "YELLOW") return "YELLOW";
  return "OK";
}

function makeChip(text, cls) {
  const chip = document.createElement("span");
  chip.className = cls ? `chip ${cls}` : "chip";
  chip.textContent = text;
  return chip;
}

/* 依赖就绪状态：圆点 + 文字，不只靠颜色 */
function makeStatusDot(text, ready) {
  const node = document.createElement("span");
  node.className = `status-dot ${ready ? "ready" : "blocked"}`;
  node.textContent = text;
  return node;
}

function makeEmpty(message) {
  const node = document.createElement("div");
  node.className = "empty";
  node.textContent = message;
  return node;
}

/* 章节头：衬线标题 + 可伸缩分隔线 + 家数，研报式分章 */
function makeChapterHead(title, count, note) {
  const head = document.createElement("div");
  head.className = "card-group__head";
  const heading = document.createElement("h3");
  heading.textContent = title;
  head.append(heading);
  if (note) {
    const hint = document.createElement("span");
    hint.className = "card-group__note";
    hint.textContent = note;
    head.append(hint);
  }
  const rule = document.createElement("span");
  rule.className = "card-group__rule";
  const total = document.createElement("span");
  total.className = "mono";
  total.textContent = count;
  head.append(rule, total);
  return head;
}

/* ---------- 视图路由：hash 稳定 URL ---------- */

const VIEWS = ["workbench", "company", "review"];
const VIEW_TITLES = {
  workbench: "披露日研判",
  company: "单票研判",
  review: "复核队列",
};

function activateView(view) {
  for (const name of VIEWS) {
    el(`view-${name}`).hidden = name !== view;
    el(`tab-${name}`).setAttribute("aria-selected", String(name === view));
  }
  appBarTitle.textContent = VIEW_TITLES[view] || view;
  appBarCrumb.textContent = window.location.hash || "#/workbench";
}

function parseHash() {
  const raw = window.location.hash.replace(/^#\/?/, "");
  const parts = raw.split("/").filter(Boolean);
  if (parts[0] === "day" && parts[1]) return { view: "workbench", date: parts[1] };
  if (parts[0] === "company" && parts[1] && parts[2]) {
    return { view: "company", tsCode: parts[1], period: parts[2] };
  }
  /* 扫描诊断已降为工作台折叠区，旧链接落到工作台并展开该区 */
  if (parts[0] === "diagnostics") return { view: "workbench", expandDiagnostics: true };
  if (VIEWS.includes(parts[0])) return { view: parts[0] };
  return { view: "workbench" };
}

async function applyRoute() {
  const route = parseHash();
  activateView(route.view);

  if (route.expandDiagnostics) {
    el("adv-diagnostics").open = true;
    el("adv-diagnostics").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  if (route.date) {
    el("disclosure-date").value = toInputDate(route.date);
    if (!state.bundle || state.bundle.date !== route.date) {
      await loadDisclosureDay(route.date);
    }
    return;
  }
  if (route.tsCode) {
    el("company-ts-code").value = route.tsCode;
    ensurePeriodOption(route.period);
    await loadCompany(route.tsCode, route.period);
  }
}

function navigate(hash) {
  if (window.location.hash === hash) {
    applyRoute();
    return;
  }
  window.location.hash = hash;
}

/* ---------- 渲染：披露日汇总 ---------- */

/* 严重度分布条：按各段数量分配 flex-grow，数量为 0 的段不渲染 */
function renderDistribution(counts) {
  const segments = [
    { cls: "seg-red", value: counts.red, label: "红色异常" },
    { cls: "seg-yellow", value: counts.yellow, label: "黄色异常" },
    { cls: "seg-ok", value: counts.ok, label: "未见异常" },
    { cls: "seg-data", value: counts.data, label: "数据问题" },
  ].filter((segment) => segment.value > 0);

  if (segments.length === 0) {
    summaryDistribution.hidden = true;
    summaryDistribution.replaceChildren();
    return;
  }

  summaryDistribution.hidden = false;
  summaryDistribution.replaceChildren(
    ...segments.map((segment) => {
      const node = document.createElement("span");
      node.className = segment.cls;
      node.style.flexGrow = String(segment.value);
      node.title = `${segment.label} ${segment.value} 家`;
      return node;
    })
  );
}

/* 导语：把当日结论压成一句话，最值得追问的那家直接点名 */
function renderLede(summary) {
  const findingTotal = summary.cards.reduce((total, card) => total + card.findings.length, 0);
  if (summary.red_count === 0 && summary.yellow_count === 0) {
    summaryLede.textContent = `当日覆盖池 ${summary.disclosed_count} 家披露，规则未触发任何异常。`;
    summaryLede.hidden = false;
    return;
  }

  const lead = [...summary.cards].sort((a, b) => (b.max_score || 0) - (a.max_score || 0))[0];
  const leadName = displayName(lead.ts_code) || lead.ts_code;
  const bucket = summary.red_count > 0
    ? { count: summary.red_count, word: "触发红色异常" }
    : { count: summary.yellow_count, word: "处于阈值边缘" };

  /* 拼接后写入 innerHTML，因此公司名与标题必须转义 */
  summaryLede.innerHTML =
    `当日 <b>${escapeHtml(String(bucket.count))} 家</b>${bucket.word}，共命中 ${findingTotal} 条规则；` +
    `其中 <b>${escapeHtml(leadName)}</b>以「${escapeHtml(lead.findings[0]?.title || "")}」最值得优先追问。`;
  summaryLede.hidden = false;
}

function renderSummary(summary, scan) {
  const dataProblems = scan.data_not_ready_count + scan.data_incomplete_count + scan.error_count;

  summaryTitle.textContent = `${toInputDate(summary.date)} 披露研判`;
  summaryLine.textContent = `覆盖池 ${summary.coverage_count} 家 · 当日披露 ${summary.disclosed_count} 家`;

  const headline =
    summary.red_count > 0
      ? { text: `${summary.red_count} 家需优先追问`, cls: "red" }
      : summary.yellow_count > 0
        ? { text: `${summary.yellow_count} 家值得留意`, cls: "yellow" }
        : { text: "当日无异常命中", cls: "ok" };
  summaryChips.replaceChildren(
    makeChip(headline.text, headline.cls),
    makeChip(`固定链接 #/day/${summary.date}`)
  );

  renderLede(summary);

  renderDistribution({
    red: summary.red_count,
    yellow: summary.yellow_count,
    ok: summary.ok_count,
    data: dataProblems,
  });

  const metrics = [
    { label: "当日披露", value: summary.disclosed_count, cls: "" },
    { label: "需优先追问", value: summary.red_count, cls: "red" },
    { label: "值得留意", value: summary.yellow_count, cls: "yellow" },
    { label: "未见异常", value: summary.ok_count, cls: "ok" },
    { label: "数据问题", value: dataProblems, cls: "" },
  ];

  summaryMetrics.replaceChildren(
    ...metrics.map((item) => {
      const node = document.createElement("div");
      node.className = item.cls ? `metric ${item.cls}` : "metric";
      const label = document.createElement("span");
      label.textContent = item.label;
      const value = document.createElement("strong");
      value.textContent = String(item.value);
      node.append(label, value);
      return node;
    })
  );
}

function makeTag(text, cls) {
  const tag = document.createElement("span");
  tag.className = cls ? `tag ${cls}` : "tag";
  tag.textContent = text;
  return tag;
}

function renderFinding(card, finding) {
  const meta = SEVERITY_META[finding.severity] || SEVERITY_META.OK;
  const item = document.createElement("div");
  item.className = `finding ${meta.cls}`;

  const head = document.createElement("div");
  head.className = "finding__head";
  const title = document.createElement("span");
  title.className = "finding__title";
  title.textContent = finding.title;
  head.append(title, makeTag(`${meta.tag} · ${finding.rule_id}`, meta.cls));

  const detail = document.createElement("p");
  detail.className = "finding__detail";
  detail.textContent = finding.detail;

  const foot = document.createElement("div");
  foot.className = "finding__foot";
  /* 依据行直接列出字段与取值，点「查看依据」再看完整快照 */
  for (const item of finding.evidence.slice(0, 3)) {
    const cell = document.createElement("span");
    cell.textContent = `${item.field} = ${item.value} @${item.period}`;
    foot.append(cell);
  }
  const score = document.createElement("span");
  score.textContent = `score ${finding.score.toFixed(1)}`;
  const evidenceButton = document.createElement("button");
  evidenceButton.className = "text";
  evidenceButton.textContent = "查看依据";
  evidenceButton.addEventListener("click", () => showEvidence(card, finding));
  foot.append(score, evidenceButton);

  item.append(head, detail, foot);
  return item;
}

function renderReviewActions(card) {
  const wrap = document.createElement("div");
  wrap.className = "review-actions";
  const current = state.reviewLabels[reviewKey(card.ts_code, card.period)];

  for (const label of ["TRUE", "FALSE", "UNREVIEWED"]) {
    const chip = makeChip(reviewLabelText(label));
    chip.setAttribute("role", "button");
    chip.setAttribute("tabindex", "0");
    chip.setAttribute("aria-pressed", String((current?.label || "UNREVIEWED") === label));
    const activate = () => {
      setReviewLabel(card, label);
      renderCards();
      renderReview();
    };
    chip.addEventListener("click", activate);
    chip.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        activate();
      }
    });
    wrap.append(chip);
  }
  return wrap;
}

/* fact_line 形如「营收 12.3 亿 | 净利 1.2 亿」，拆成等宽分格，第一段是标签、其余是取值 */
function renderFactLine(factLine) {
  const wrap = document.createElement("div");
  wrap.className = "card__fact";
  for (const part of String(factLine || "").split("|")) {
    const text = part.trim();
    if (!text) continue;
    const [label, ...rest] = text.split(/\s+/);
    const cell = document.createElement("div");
    const key = document.createElement("span");
    key.textContent = label;
    const value = document.createElement("b");
    value.textContent = rest.join(" ") || "—";
    cell.append(key, value);
    wrap.append(cell);
  }
  return wrap;
}

/* 覆盖池上百家时卡片网格会变成读不完的瀑布，因此改成默认收起、点击展开的行 */
function renderCard(card, options = {}) {
  const key = severityKey(card);
  const meta = SEVERITY_META[key];
  const node = document.createElement("article");
  node.className = `card ${meta.cls}`;
  if (options.standalone) node.classList.add("standalone", "open");
  if (options.open) node.classList.add("open");

  const head = document.createElement("div");
  head.className = "card__head";
  const severityBar = document.createElement("span");
  severityBar.className = "card__sev";
  head.append(severityBar);

  if (options.rank) {
    const rank = document.createElement("span");
    rank.className = "card__code";
    rank.textContent = String(options.rank).padStart(2, "0");
    head.append(rank);
  }

  const name = document.createElement("span");
  name.className = "card__name";
  name.textContent = displayName(card.ts_code) || card.ts_code;
  const code = document.createElement("span");
  code.className = "card__code";
  code.textContent = `${card.ts_code} · ${card.period}`;
  const summary = document.createElement("span");
  summary.className = "card__sum";
  summary.textContent = card.findings[0]?.title || "规则未触发异常";

  const push = document.createElement("span");
  push.className = "card__push";
  push.append(
    makeTag(meta.tag, card.findings.length > 0 ? meta.cls : "mut"),
    makeTag(`${card.findings.length} 条 · ${(card.max_score || 0).toFixed(0)}`, "mut")
  );
  if (!options.standalone) {
    const chevron = document.createElement("span");
    chevron.className = "card__chevron";
    chevron.textContent = "▶";
    push.append(chevron);
    head.addEventListener("click", () => node.classList.toggle("open"));
  }
  head.append(name, code, summary, push);

  const body = document.createElement("div");
  body.className = "card__body";
  body.append(renderFactLine(card.fact_line));

  const findings = document.createElement("div");
  findings.className = "findings";
  if (card.findings.length === 0) {
    findings.append(makeEmpty(meta.note));
  } else {
    for (const finding of card.findings) {
      findings.append(renderFinding(card, finding));
    }
  }
  body.append(findings);

  if (card.attribution) {
    const attribution = document.createElement("p");
    attribution.className = "card__attribution";
    attribution.textContent = card.attribution;
    body.append(attribution);
  }

  const foot = document.createElement("div");
  foot.className = "card__foot";
  const permalink = document.createElement("a");
  permalink.href = `#/company/${card.ts_code}/${card.period}`;
  permalink.textContent = "打开公司详情";
  foot.append(permalink, renderReviewActions(card));
  body.append(foot);

  node.append(head, body);
  return node;
}

function renderDataProblemGroup(events) {
  const table = document.createElement("div");
  table.className = "table-wrap";
  const rows = events
    .map((event) => {
      const name = displayName(event.ts_code);
      return `<tr><td class="mono">${escapeHtml(event.ts_code)}</td><td>${escapeHtml(name)}</td><td class="mono">${escapeHtml(event.period)}</td><td>${escapeHtml(event.industry || "unknown")}</td><td>${escapeHtml(event.status)}</td><td>${escapeHtml(event.message)}</td></tr>`;
    })
    .join("");
  table.innerHTML = `
    <table>
      <thead><tr><th>代码</th><th>名称</th><th>报告期</th><th>行业</th><th>状态</th><th>原因</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  return table;
}

function renderCards() {
  if (!state.bundle) {
    cardGroups.replaceChildren(makeEmpty("尚无数据，请先生成披露日汇总"));
    return;
  }

  const cards = state.bundle.summary.cards;
  const problemEvents = state.bundle.scan.events.filter((event) => event.status !== "OK");
  const byScore = (a, b) => (b.max_score || 0) - (a.max_score || 0);
  const groups = [
    { key: "RED", cards: cards.filter((card) => severityKey(card) === "RED").sort(byScore) },
    { key: "YELLOW", cards: cards.filter((card) => severityKey(card) === "YELLOW").sort(byScore) },
    { key: "OK", cards: cards.filter((card) => severityKey(card) === "OK") },
  ];

  const nodes = [];
  let rank = 0;
  let openedFirst = false;
  for (const group of groups) {
    if (state.filter !== "all" && state.filter !== group.key) continue;
    if (group.cards.length === 0) continue;
    const meta = SEVERITY_META[group.key];
    const section = document.createElement("section");
    section.append(makeChapterHead(meta.label, `${group.cards.length} 家`, meta.note));

    /* 未见异常只报数量与名单，不逐条展开，避免把版面吃掉 */
    if (group.key === "OK") {
      const brief = document.createElement("p");
      brief.className = "brief";
      brief.append(document.createTextNode("规则全部未触发："));
      group.cards.forEach((card, index) => {
        if (index > 0) brief.append(document.createTextNode("、"));
        const name = document.createElement("b");
        name.textContent = displayName(card.ts_code) || card.ts_code;
        brief.append(name);
      });
      brief.append(document.createTextNode("。仅汇总数量，不逐条展开。"));
      section.append(brief);
      nodes.push(section);
      continue;
    }

    const list = document.createElement("div");
    list.className = "cards";
    for (const card of group.cards) {
      rank += 1;
      /* 默认只展开分数最高的那一行，其余保持收起 */
      const open = !openedFirst;
      openedFirst = true;
      list.append(renderCard(card, { rank, open }));
    }
    section.append(list);
    nodes.push(section);
  }

  const showProblems = (state.filter === "all" || state.filter === "DATA") && problemEvents.length > 0;
  if (showProblems) {
    const meta = SEVERITY_META.DATA;
    const section = document.createElement("section");
    section.append(makeChapterHead(meta.label, `${problemEvents.length} 家`, meta.note));
    section.append(renderDataProblemGroup(problemEvents));
    nodes.push(section);
  }

  cardGroups.replaceChildren(...(nodes.length > 0 ? nodes : [makeEmpty("当前筛选下没有公司")]));
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char];
  });
}

function renderDiagnostics(result) {
  const summary = document.createElement("div");
  summary.className = "metric-grid";
  const metrics = [
    { label: "覆盖池", value: result.coverage_count },
    { label: "当日披露", value: result.disclosed_count },
    { label: "出卡 OK", value: result.ok_count },
    { label: "待数据", value: result.data_not_ready_count },
    { label: "不完整", value: result.data_incomplete_count },
    { label: "错误", value: result.error_count },
  ];
  for (const item of metrics) {
    const node = document.createElement("div");
    node.className = "metric";
    const label = document.createElement("span");
    label.textContent = item.label;
    const value = document.createElement("strong");
    value.textContent = String(item.value);
    node.append(label, value);
    summary.append(node);
  }

  const table = document.createElement("div");
  table.className = "table-wrap";
  table.style.marginTop = "16px";
  const rows = result.events
    .map(
      (event) =>
        `<tr><td class="mono">${escapeHtml(event.ts_code)}</td><td>${escapeHtml(displayName(event.ts_code))}</td><td class="mono">${escapeHtml(event.period)}</td><td>${escapeHtml(event.industry || "unknown")}</td><td>${escapeHtml(event.status)}</td><td>${escapeHtml(event.message)}</td></tr>`
    )
    .join("");
  table.innerHTML = `
    <table>
      <thead><tr><th>代码</th><th>名称</th><th>报告期</th><th>行业</th><th>状态</th><th>原因</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;

  diagnosticStatus.replaceChildren(summary, result.events.length > 0 ? table : makeEmpty("当日覆盖池无披露事件"));
}

/* ---------- 复核状态 ---------- */

function reviewKey(tsCode, period) {
  return `${tsCode}|${period}`;
}

function reviewLabelText(label) {
  if (label === "TRUE") return "✓ 有效";
  if (label === "FALSE") return "✗ 误报";
  return "待复核";
}

function loadReviewLabels() {
  try {
    return JSON.parse(window.localStorage.getItem(REVIEW_STORAGE_KEY) || "{}");
  } catch (error) {
    return {};
  }
}

function persistReviewLabels() {
  window.localStorage.setItem(REVIEW_STORAGE_KEY, JSON.stringify(state.reviewLabels));
}

function setReviewLabel(card, label) {
  const key = reviewKey(card.ts_code, card.period);
  if (label === "UNREVIEWED") {
    delete state.reviewLabels[key];
  } else {
    const scanEvent = state.bundle?.scan.events.find((event) => event.ts_code === card.ts_code && event.period === card.period);
    state.reviewLabels[key] = {
      ts_code: card.ts_code,
      period: card.period,
      rule_id: card.findings[0]?.rule_id || "",
      label,
      notes: "",
      severity: card.max_severity || "",
      industry: scanEvent?.industry || "unknown",
    };
  }
  persistReviewLabels();
  notify(`${card.ts_code} 已标注为${reviewLabelText(label)}`);
}

function renderReview() {
  const entries = Object.values(state.reviewLabels);
  const trueCount = entries.filter((entry) => entry.label === "TRUE").length;
  const falseCount = entries.filter((entry) => entry.label === "FALSE").length;
  const precision = entries.length > 0 ? ((trueCount / entries.length) * 100).toFixed(1) : "待复核";

  const metrics = [
    { label: "已复核", value: entries.length },
    { label: "✓ 有效", value: trueCount },
    { label: "✗ 误报", value: falseCount },
    { label: "精确率", value: entries.length > 0 ? `${precision}%` : precision },
  ];
  reviewMetrics.replaceChildren(
    ...metrics.map((item) => {
      const node = document.createElement("div");
      // 文本型取值用较小字号，衬线大数字只留给真正的数字
      node.className = typeof item.value === "number" ? "metric" : "metric wide";
      const label = document.createElement("span");
      label.textContent = item.label;
      const value = document.createElement("strong");
      value.textContent = String(item.value);
      node.append(label, value);
      return node;
    })
  );

  if (entries.length === 0) {
    reviewTable.replaceChildren(makeEmpty("尚无标注，在工作台公司卡上标注有效或误报"));
    return;
  }

  const wrap = document.createElement("div");
  wrap.className = "table-wrap";
  const rows = entries
    .map(
      (entry) =>
        `<tr><td class="mono">${escapeHtml(entry.ts_code)}</td><td>${escapeHtml(displayName(entry.ts_code))}</td><td class="mono">${escapeHtml(entry.period)}</td><td>${escapeHtml(entry.rule_id)}</td><td>${escapeHtml(entry.label)}</td></tr>`
    )
    .join("");
  wrap.innerHTML = `
    <table>
      <thead><tr><th>代码</th><th>名称</th><th>报告期</th><th>rule_id</th><th>label</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  reviewTable.replaceChildren(wrap);
}

/* ---------- 导出 ---------- */

function downloadFile(filename, content, mime) {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
  notify(`已导出 ${filename}`);
}

function csvCell(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function toCsv(header, rows) {
  return [header, ...rows].map((row) => row.map(csvCell).join(",")).join("\n");
}

function exportBundleJson() {
  if (!state.bundle) {
    notify("请先生成披露日汇总", true);
    return;
  }
  downloadFile(`tradeeye-${state.bundle.date}.json`, JSON.stringify(state.bundle, null, 2), "application/json");
}

function exportBundleCsv() {
  if (!state.bundle) {
    notify("请先生成披露日汇总", true);
    return;
  }
  const cardByCode = new Map(state.bundle.summary.cards.map((card) => [card.ts_code, card]));
  const rows = state.bundle.scan.events.map((event) => {
    const card = cardByCode.get(event.ts_code);
    const top = card?.findings[0];
    return [
      event.ts_code,
      displayName(event.ts_code),
      event.period,
      event.industry || "unknown",
      event.status,
      card?.max_severity || "",
      card?.findings.length ?? 0,
      top?.rule_id || "",
      top?.title || "",
      top?.detail || event.message,
    ];
  });
  const header = ["ts_code", "name", "period", "industry", "status", "max_severity", "finding_count", "top_rule_id", "top_title", "detail"];
  downloadFile(`tradeeye-${state.bundle.date}.csv`, toCsv(header, rows), "text/csv");
}

function exportReviewCsv() {
  const entries = Object.values(state.reviewLabels);
  if (entries.length === 0) {
    notify("尚无标注可导出", true);
    return;
  }
  const header = ["ts_code", "period", "rule_id", "label", "notes", "severity", "industry"];
  const rows = entries.map((entry) => [entry.ts_code, entry.period, entry.rule_id, entry.label, entry.notes, entry.severity, entry.industry]);
  downloadFile("manual_review.csv", toCsv(header, rows), "text/csv");
}

/* ---------- 数据加载 ---------- */

async function loadMeta() {
  try {
    state.meta = await api.getMeta();
  } catch (error) {
    setStatus({ error: error.message });
    return;
  }
  metaStatus.replaceChildren(
    makeStatusDot(state.meta.tushare_ready ? "Tushare 就绪" : "Tushare 未配置", state.meta.tushare_ready),
    makeStatusDot(state.meta.feishu_ready ? "飞书就绪" : "飞书未配置", state.meta.feishu_ready),
    makeChip(`覆盖池 ${state.meta.coverage_count} 家`)
  );
}

function renderJobProgress(job) {
  const name = job.current_name || displayName(job.current_ts_code) || job.current_ts_code || "等待公司";
  const count = `${job.processed_count}/${job.total_count || "?"}`;
  const stage = job.current_stage || job.status;
  el("progress-message").textContent = `${count} · ${name} · ${stage}`;
  el("progress-elapsed").textContent = `${Number(job.elapsed_seconds || 0).toFixed(1)}s`;
  setStatus(job);
}

function finishDisclosureJob(job) {
  clearInterval(state.jobPollTimer);
  state.jobPollTimer = null;
  state.activeJobId = null;
  setScanState("idle");
  scanProgress.stop(performance.now() - Number(job.elapsed_seconds || 0) * 1000, job.status === "cancelled" ? `已停止，完成 ${job.processed_count}/${job.total_count}` : `已完成 ${job.processed_count} 家分析`);
  if (job.bundle) {
    state.bundle = job.bundle;
    renderSummary(job.bundle.summary, job.bundle.scan);
    renderCards();
    renderDiagnostics(job.bundle.scan);
  }
  notify(job.status === "cancelled" ? "扫描已停止" : "扫描完成", job.status === "failed");
}

async function pollDisclosureJob(jobId) {
  const job = await api.getDisclosureDayJob(jobId);
  renderJobProgress(job);
  if (["completed", "cancelled", "failed"].includes(job.status)) {
    finishDisclosureJob(job);
  }
}

async function stopDisclosureScan() {
  if (!state.activeJobId) return;
  setScanState("cancelling");
  const job = await api.cancelDisclosureDayJob(state.activeJobId);
  renderJobProgress(job);
}

async function loadDisclosureDay(date) {
  scanProgress.start(`正在启动 ${date} 覆盖池扫描…`);
  setScanState("scanning");
  try {
    const job = await api.startDisclosureDayJob(date);
    state.activeJobId = job.job_id;
    renderJobProgress(job);
    if (["completed", "cancelled", "failed"].includes(job.status)) {
      finishDisclosureJob(job);
      return;
    }
    clearInterval(state.jobPollTimer);
    state.jobPollTimer = setInterval(() => {
      if (state.activeJobId) {
        pollDisclosureJob(state.activeJobId).catch((error) => {
          clearInterval(state.jobPollTimer);
          state.jobPollTimer = null;
          scanProgress.hide();
          setScanState("idle");
          setStatus({ error: error.message });
          notify(error.message, true);
        });
      }
    }, 1000);
  } catch (error) {
    scanProgress.hide();
    setScanState("idle");
    setStatus({ error: error.message });
    notify(error.message, true);
  }
}

async function loadCompany(tsCode, period) {
  const startedAt = companyProgress.start(`正在分析 ${tsCode} ${period}…`);
  try {
    const result = await api.analyzeCompany(tsCode, period);
    const seconds = companyProgress.stop(startedAt, `状态 ${result.status}`);
    setStatus(result);
    companyPermalinkHint.textContent = `固定链接 #/company/${tsCode}/${period}`;
    if (result.card) {
      companyDetail.replaceChildren(renderCard(result.card, { standalone: true }));
    } else {
      companyDetail.replaceChildren(makeEmpty(`${result.status}：${result.message}`));
    }
    notify(`${tsCode} 分析完成，耗时 ${seconds.toFixed(1)}s`);
  } catch (error) {
    companyProgress.hide();
    setStatus({ error: error.message });
    companyDetail.replaceChildren(makeEmpty(error.message));
    notify(error.message, true);
  }
}

async function loadQuarterly() {
  try {
    const review = await api.getQuarterly();
    const metrics = [
      { label: "区间", value: review.period_label },
      { label: "覆盖池", value: review.coverage_count },
      { label: "已披露", value: review.disclosed_count },
      { label: "命中", value: review.finding_count },
      { label: "精确率", value: review.precision_pct === null ? "待复核" : `${review.precision_pct}%` },
      ...review.top_rules.map((item) => ({ label: item.rule_id, value: item.count })),
    ];
    quarterlyReview.replaceChildren(
      ...metrics.map((item) => {
        const node = document.createElement("div");
        // 文本型取值用较小字号，避免长字符串撑破卡片
        node.className = typeof item.value === "number" ? "metric" : "metric wide";
        const label = document.createElement("span");
        label.textContent = item.label;
        const value = document.createElement("strong");
        value.textContent = String(item.value);
        node.append(label, value);
        return node;
      })
    );
  } catch (error) {
    quarterlyReview.replaceChildren(makeEmpty("披露季复盘暂无数据"));
  }
}

async function showEvidence(card, finding) {
  try {
    const evidence = await api.getEvidence(card.ts_code, card.period, finding.rule_id);
    evidenceContent.textContent = JSON.stringify(evidence, null, 2);
    evidenceDialog.showModal();
  } catch (error) {
    notify(error.message, true);
  }
}

/* ---------- 飞书预览与发送确认 ---------- */

async function previewFeishu() {
  const date = selectedDate();
  if (!date) {
    notify("请先选择披露日期", true);
    return;
  }
  const startedAt = scanProgress.start(`正在渲染 ${date} 飞书摘要…`);
  try {
    const preview = await api.previewFeishuDisclosureDay(date);
    scanProgress.stop(startedAt, "摘要已生成");
    setStatus({ date: preview.date, sendable: preview.sendable, reason: preview.reason, chars: preview.text.length });
    state.previewDate = date;
    feishuPreviewText.textContent = preview.text || "（无内容）";
    feishuPreviewMeta.textContent = `${preview.text.length} 字符 · ${preview.text.split("\n").length} 行`;
    sendFeishuButton.disabled = !preview.sendable;
    feishuPreviewHint.textContent = preview.sendable
      ? "确认后将真实推送到已配置的飞书 webhook"
      : `不可发送：${preview.reason}`;
    feishuDialog.showModal();
  } catch (error) {
    scanProgress.hide();
    setStatus({ error: error.message });
    notify(error.message, true);
  }
}

async function confirmSendFeishu() {
  const date = state.previewDate;
  sendFeishuButton.disabled = true;
  try {
    const result = await api.sendFeishuDisclosureDay(date);
    setStatus(result);
    notify(result.sent ? `${date} 飞书摘要已发送` : `未发送：${result.reason}`, !result.sent);
    feishuDialog.close();
  } catch (error) {
    setStatus({ error: error.message });
    notify(error.message, true);
  } finally {
    sendFeishuButton.disabled = false;
  }
}

/* ---------- 事件绑定 ---------- */

for (const name of VIEWS) {
  el(`tab-${name}`).addEventListener("click", () => navigate(`#/${name}`));
}

/* 同一个按钮按当前状态分派：空闲时开扫，扫描中发取消 */
scanButton.addEventListener("click", () => {
  if (scanButton.dataset.state === "idle") {
    const date = selectedDate();
    if (!date) {
      notify("请先选择披露日期", true);
      return;
    }
    navigate(`#/day/${date}`);
    return;
  }
  stopDisclosureScan().catch((error) => {
    setStatus({ error: error.message });
    notify(error.message, true);
  });
});

el("analyze-company").addEventListener("click", () => {
  const tsCode = el("company-ts-code").value.trim();
  const period = el("company-period").value;
  navigate(`#/company/${tsCode}/${period}`);
});

el("preview-feishu").addEventListener("click", previewFeishu);
sendFeishuButton.addEventListener("click", confirmSendFeishu);
el("cancel-feishu").addEventListener("click", () => feishuDialog.close());
el("close-dialog").addEventListener("click", () => evidenceDialog.close());

el("poll-rss").addEventListener("click", async () => {
  try {
    const result = await api.pollRss();
    setStatus(result);
    notify(`RSS 命中 ${result.matched_count} 条，已分析 ${result.analyzed_count} 条`);
  } catch (error) {
    setStatus({ error: error.message });
    notify(error.message, true);
  }
});

/* 导出 JSON / CSV 是同类动作，收进一个下拉；id 沿用原值 */
createMenuButton({
  mount: el("export-menu-mount"),
  label: "导出",
  items: [
    { id: "export-menu-json", label: "导出 JSON", onSelect: exportBundleJson },
    { id: "export-menu-csv", label: "导出 CSV", onSelect: exportBundleCsv },
  ],
});
el("export-review-csv").addEventListener("click", exportReviewCsv);

el("clear-review").addEventListener("click", () => {
  state.reviewLabels = {};
  persistReviewLabels();
  renderReview();
  renderCards();
  notify("已清空本地标注");
});

for (const button of document.querySelectorAll("#severity-filters button")) {
  button.addEventListener("click", () => {
    state.filter = button.dataset.filter;
    for (const other of document.querySelectorAll("#severity-filters button")) {
      other.setAttribute("aria-pressed", String(other === button));
    }
    renderCards();
  });
}

window.addEventListener("hashchange", applyRoute);

/* ---------- 启动 ---------- */

async function boot() {
  // 未来日期不可能有已披露财报，直接由控件挡住
  el("disclosure-date").max = new Date().toISOString().slice(0, 10);
  initPeriodSelect("20250630");
  await loadMeta();
  renderCards();
  renderReview();
  loadQuarterly();
  await applyRoute();
}

boot();
