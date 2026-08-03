const STORAGE_KEY = "tradeeye.agentPanel";
const MIN_WIDTH = 320;
const MAX_WIDTH = 560;
const MIN_HEIGHT = 360;
const MAX_HEIGHT = 720;
const DOCK_THRESHOLD = 24;
const VISIBLE_MIN_WIDTH = 120;
const VISIBLE_MIN_HEIGHT = 80;

export const defaultPanelState = {
  mode: "docked",
  open: false,
  left: 0,
  top: 72,
  width: 400,
  height: 520,
};

export const agentLauncherLabel = "打开 Agent 问答";
export const agentRobotIconParts = ["antenna", "head", "eye-left", "eye-right", "mouth"];

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

export function isNearRightDock({ left, width, viewportWidth, threshold = DOCK_THRESHOLD }) {
  return viewportWidth - (left + width) <= threshold;
}

export function clampPanelState(state, viewport) {
  const merged = { ...defaultPanelState, ...state };
  const width = clamp(Number(merged.width) || defaultPanelState.width, MIN_WIDTH, MAX_WIDTH);
  if (merged.mode === "docked") {
    return { ...defaultPanelState, ...merged, mode: "docked", width, height: defaultPanelState.height };
  }

  const height = clamp(Number(merged.height) || defaultPanelState.height, MIN_HEIGHT, Math.min(MAX_HEIGHT, viewport.height));
  const maxLeft = Math.max(0, viewport.width - VISIBLE_MIN_WIDTH);
  const maxTop = Math.max(0, viewport.height - VISIBLE_MIN_HEIGHT);
  return {
    ...defaultPanelState,
    ...merged,
    mode: "floating",
    width,
    height,
    left: clamp(Number(merged.left) || 0, 0, maxLeft),
    top: clamp(Number(merged.top) || 0, 0, maxTop),
  };
}

export function readPanelState(storage = window.localStorage) {
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (!raw) return { ...defaultPanelState };
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return { ...defaultPanelState };
    return { ...defaultPanelState, ...parsed };
  } catch {
    return { ...defaultPanelState };
  }
}

export function writePanelState(storage = window.localStorage, state) {
  storage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      mode: state.mode,
      open: Boolean(state.open),
      left: Number(state.left),
      top: Number(state.top),
      width: Number(state.width),
      height: Number(state.height),
    }),
  );
}

export function shouldAutoScroll({ scrollHeight, scrollTop, clientHeight }, threshold = 40) {
  return scrollHeight - scrollTop - clientHeight < threshold;
}

function textNode(text) {
  return document.createTextNode(text == null ? "" : String(text));
}

export function formatAgentCard(card) {
  return {
    title: card.title || card.ts_code || "未知公司",
    subtitle: card.subtitle || card.period || "",
  };
}

export const agentDisabledGuidance = "Agent 问答需要配置外部 LLM API 后启用；当前仍可查看公司卡、依据弹窗和确定性 finding。";

function valueOrMissing(value) {
  if (value === null || value === undefined || value === "") return "未提供";
  return String(value);
}

export function formatAgentReference(reference = {}) {
  return {
    rows: [
      { label: "类型或规则", value: valueOrMissing(reference.rule_id || reference.kind || reference.title) },
      { label: "来源", value: valueOrMissing(reference.source) },
      { label: "字段", value: valueOrMissing(reference.field) },
      { label: "期间", value: valueOrMissing(reference.period) },
      { label: "数值", value: valueOrMissing(reference.value) },
    ],
    raw: JSON.stringify(reference, null, 2),
  };
}

export function agentActionTitle(action = {}) {
  if (action.action === "refetch_company") return "重新抓取单票研判卡";
  if (action.action === "rescan_disclosure_day") return "重扫披露日";
  return "执行建议动作";
}

function createMessage(role, text, references = [], options = {}) {
  const node = document.createElement("div");
  node.className = `agent-message agent-message--${role}`;
  const body = document.createElement("div");
  body.className = "agent-message__body";
  for (const [index, part] of String(text || "").split("\n").entries()) {
    if (index > 0) body.append(document.createElement("br"));
    body.append(textNode(part));
  }
  node.append(body);

  if (references.length > 0) {
    const refs = document.createElement("div");
    refs.className = "agent-message__refs";
    for (const reference of references) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "agent-ref";
      chip.textContent = reference.fact_id || reference.evidence_id;
      chip.dataset.factId = reference.fact_id || "";
      chip.dataset.evidenceId = reference.evidence_id || "";
      chip.setAttribute("aria-label", `查看 ${chip.textContent} 的证据`);
      refs.append(chip);
    }
    node.append(refs);
  }

  if (options.retryQuestion) {
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "outlined agent-message__retry";
    retry.textContent = "重试";
    retry.dataset.retryQuestion = options.retryQuestion;
    node.append(retry);
  }
  return node;
}

function createPendingMessage() {
  const node = createMessage("assistant", "");
  node.classList.add("agent-message--pending");
  const body = node.querySelector(".agent-message__body");
  body.replaceChildren();
  const label = document.createElement("span");
  label.className = "agent-thinking__label";
  label.textContent = "正在思考";
  const dots = document.createElement("span");
  dots.className = "agent-thinking__dots";
  dots.setAttribute("aria-hidden", "true");
  for (let index = 0; index < 3; index += 1) {
    const dot = document.createElement("span");
    dots.append(dot);
  }
  body.append(label, dots);
  return node;
}

function createRobotIcon() {
  const icon = document.createElement("span");
  icon.className = "agent-robot";
  icon.setAttribute("aria-hidden", "true");
  for (const part of agentRobotIconParts) {
    const node = document.createElement("span");
    node.className = `agent-robot__${part}`;
    icon.append(node);
  }
  return icon;
}

function viewportSize() {
  return { width: window.innerWidth, height: window.innerHeight };
}

export function createAgentPanel({ mount = document.body, onSend = null, onAction = null, onReference = null } = {}) {
  let sendHandler = onSend;
  let actionHandler = onAction;
  let referenceHandler = onReference;
  let state = clampPanelState(readPanelState(), viewportSize());
  let currentGroup = null;
  let pendingCount = 0;

  const root = document.createElement("section");
  root.className = "agent-panel";
  root.setAttribute("role", "complementary");
  root.setAttribute("aria-label", "Agent 问答");

  const snap = document.createElement("div");
  snap.className = "agent-panel__snap";
  snap.hidden = true;

  const head = document.createElement("div");
  head.className = "agent-panel__head";
  head.tabIndex = 0;
  const mark = document.createElement("span");
  mark.className = "brand-mark";
  mark.setAttribute("aria-hidden", "true");
  const title = document.createElement("strong");
  title.textContent = "Agent 问答";
  const spacer = document.createElement("span");
  spacer.className = "agent-panel__spacer";
  head.append(mark, title, spacer);

  const dockButton = document.createElement("button");
  dockButton.type = "button";
  dockButton.className = "text agent-panel__dock";
  dockButton.textContent = "停靠";
  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "text agent-panel__close";
  closeButton.textContent = "关闭";
  head.append(dockButton, closeButton);

  const context = document.createElement("div");
  context.className = "agent-context";
  context.textContent = "未选择研判卡";

  const log = document.createElement("div");
  log.className = "agent-log";
  log.setAttribute("aria-live", "polite");

  const form = document.createElement("form");
  form.className = "agent-input";
  const input = document.createElement("textarea");
  input.rows = 2;
  input.placeholder = "请先选择一张研判卡";
  input.disabled = true;
  const send = document.createElement("button");
  send.type = "submit";
  send.textContent = "发送";
  send.disabled = true;
  form.append(input, send);

  const resize = document.createElement("div");
  resize.className = "agent-panel__resize";
  resize.tabIndex = 0;
  resize.setAttribute("role", "separator");
  resize.setAttribute("aria-orientation", "vertical");
  resize.setAttribute("aria-label", "调整 Agent 面板宽度");

  const fab = document.createElement("button");
  fab.type = "button";
  fab.className = "agent-fab";
  fab.setAttribute("aria-label", agentLauncherLabel);
  fab.append(createRobotIcon());
  fab.setAttribute("aria-expanded", String(state.open));

  root.append(resize, head, context, log, form);
  mount.append(root, snap, fab);

  function persist() {
    writePanelState(window.localStorage, state);
  }

  function applyState() {
    root.classList.toggle("agent-panel--floating", state.mode === "floating");
    root.classList.toggle("agent-panel--docked", state.mode === "docked");
    root.hidden = !state.open;
    fab.hidden = state.open;
    fab.setAttribute("aria-expanded", String(state.open));
    if (state.mode === "docked") {
      root.style.top = "calc(52px + var(--space-4))";
      root.style.right = "var(--space-4)";
      root.style.bottom = "var(--space-4)";
      root.style.left = "auto";
      root.style.width = `${state.width}px`;
      root.style.height = "auto";
    } else {
      root.style.top = `${state.top}px`;
      root.style.left = `${state.left}px`;
      root.style.right = "auto";
      root.style.bottom = "auto";
      root.style.width = `${state.width}px`;
      root.style.height = `${state.height}px`;
    }
    persist();
  }

  function appendToCurrent(node) {
    const atBottom = shouldAutoScroll(log);
    const target = currentGroup?.body || log;
    target.append(node);
    if (atBottom) log.scrollTop = log.scrollHeight;
    return node;
  }

  function updateInputHeight() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (!question || !sendHandler) return;
    appendToCurrent(createMessage("user", question));
    input.value = "";
    updateInputHeight();
    sendHandler(question);
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  input.addEventListener("input", updateInputHeight);

  log.addEventListener("click", (event) => {
    const retry = event.target.closest("[data-retry-question]");
    if (retry && sendHandler) {
      sendHandler(retry.dataset.retryQuestion);
      return;
    }
    const ref = event.target.closest(".agent-ref");
    if (ref && referenceHandler) {
      referenceHandler({ fact_id: ref.dataset.factId || null, evidence_id: ref.dataset.evidenceId || null });
    }
  });

  fab.addEventListener("click", () => {
    state = { ...state, open: true };
    applyState();
  });
  closeButton.addEventListener("click", () => {
    state = { ...state, open: false };
    applyState();
  });
  dockButton.addEventListener("click", () => {
    state = { ...state, mode: "docked" };
    applyState();
  });

  function startDrag(event) {
    if (event.button !== 0) return;
    const startX = event.clientX;
    const startY = event.clientY;
    const rect = root.getBoundingClientRect();
    const base = { left: rect.left, top: rect.top, width: rect.width, height: rect.height };
    state = { ...state, mode: "floating", left: base.left, top: base.top, height: base.height };
    applyState();

    function move(moveEvent) {
      const next = { ...state, left: base.left + moveEvent.clientX - startX, top: base.top + moveEvent.clientY - startY };
      snap.hidden = !isNearRightDock({ left: next.left, width: next.width, viewportWidth: window.innerWidth });
      state = clampPanelState(next, viewportSize());
      applyState();
    }
    function up() {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
      snap.hidden = true;
      if (isNearRightDock({ left: state.left, width: state.width, viewportWidth: window.innerWidth })) {
        state = { ...state, mode: "docked" };
        applyState();
      }
    }
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  }
  head.addEventListener("mousedown", startDrag);

  function startResize(event) {
    if (event.button !== 0) return;
    event.preventDefault();
    const startX = event.clientX;
    const baseWidth = root.getBoundingClientRect().width;
    function move(moveEvent) {
      const delta = state.mode === "docked" ? startX - moveEvent.clientX : moveEvent.clientX - startX;
      state = clampPanelState({ ...state, width: baseWidth + delta }, viewportSize());
      applyState();
    }
    function up() {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    }
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  }
  resize.addEventListener("mousedown", startResize);

  window.addEventListener("resize", () => {
    state = clampPanelState(state, viewportSize());
    applyState();
  });

  applyState();

  return {
    open() {
      state = { ...state, open: true };
      applyState();
    },
    close() {
      state = { ...state, open: false };
      applyState();
    },
    onSend(handler) {
      sendHandler = handler;
    },
    onAction(handler) {
      actionHandler = handler;
    },
    onReference(handler) {
      referenceHandler = handler;
    },
    startGroup(card) {
      for (const group of log.querySelectorAll(".agent-group")) {
        group.classList.remove("agent-group--current");
        group.classList.add("agent-group--past");
        const badge = group.querySelector(".agent-group__badge");
        if (badge) badge.textContent = "已切走";
      }
      const group = document.createElement("section");
      group.className = "agent-group agent-group--current";
      const headNode = document.createElement("div");
      headNode.className = "agent-group__head";
      const formatted = formatAgentCard(card);
      const groupTitle = document.createElement("span");
      groupTitle.className = "agent-group__title";
      groupTitle.textContent = formatted.title;
      headNode.append(groupTitle);
      if (formatted.subtitle) {
        const groupSubtitle = document.createElement("span");
        groupSubtitle.className = "agent-group__subtitle";
        groupSubtitle.textContent = formatted.subtitle;
        headNode.append(groupSubtitle);
      }
      const badge = document.createElement("span");
      badge.className = "agent-group__badge";
      badge.textContent = "当前";
      headNode.append(badge);
      const body = document.createElement("div");
      body.className = "agent-group__body";
      group.append(headNode, body);
      log.append(group);
      currentGroup = { node: group, body };
      log.scrollTop = log.scrollHeight;
    },
    setContext(card) {
      if (!card) {
        context.textContent = "未选择研判卡";
        input.placeholder = "请先选择一张研判卡";
        input.disabled = true;
        send.disabled = true;
        return;
      }
      const formatted = formatAgentCard(card);
      context.textContent = formatted.subtitle ? `当前：${formatted.title} / ${formatted.subtitle}` : `当前：${formatted.title}`;
      input.placeholder = "向 Agent 提问…";
      input.disabled = false;
      send.disabled = false;
    },
    appendMessage(role, text, references = [], options = {}) {
      return appendToCurrent(createMessage(role, text, references, options));
    },
    appendSystem(text, isError = false) {
      return appendToCurrent(createMessage(isError ? "error" : "system", text));
    },
    appendAction(action) {
      const node = document.createElement("div");
      node.className = "agent-action";
      const eyebrow = document.createElement("div");
      eyebrow.className = "agent-action__eyebrow";
      eyebrow.textContent = "建议动作";
      const strong = document.createElement("strong");
      strong.textContent = agentActionTitle(action);
      const reason = document.createElement("p");
      reason.textContent = action.reason || "Agent 建议执行此动作。";
      node.append(eyebrow, strong, reason);
      const row = document.createElement("div");
      row.className = "agent-action__buttons";
      const confirm = document.createElement("button");
      confirm.type = "button";
      confirm.textContent = "确认执行";
      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "outlined";
      cancel.textContent = "取消";
      row.append(confirm, cancel);
      node.append(row);
      confirm.addEventListener("click", () => actionHandler?.(action, node));
      cancel.addEventListener("click", () => node.remove());
      return appendToCurrent(node);
    },
    setPending(active) {
      pendingCount = Math.max(0, pendingCount + (active ? 1 : -1));
      const disabled = pendingCount > 0;
      send.disabled = disabled || input.disabled;
      if (active) {
        return appendToCurrent(createPendingMessage());
      }
      return null;
    },
    replacePending(node, text, references = [], options = {}) {
      if (!node) return this.appendMessage("assistant", text, references, options);
      node.replaceWith(createMessage(options.retryQuestion ? "error" : "assistant", text, references, options));
      return node;
    },
    setDisabled(disabled, message = "Agent 未配置") {
      input.disabled = disabled;
      send.disabled = disabled;
      input.placeholder = disabled ? message : "向 Agent 提问…";
    },
    setActionRunning(node, running) {
      for (const button of node.querySelectorAll("button")) button.disabled = running;
      node.classList.toggle("agent-action--running", running);
    },
    setActionDone(node) {
      for (const button of node.querySelectorAll("button")) button.disabled = true;
      node.classList.remove("agent-action--running");
      node.classList.add("agent-action--done");
      const first = node.querySelector("button");
      if (first) first.textContent = "已执行";
    },
  };
}

if (typeof window !== "undefined") {
  window.TradeEyeAgentPanel = { createAgentPanel, agentDisabledGuidance, formatAgentReference };
}
