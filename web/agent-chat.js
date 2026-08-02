export function createChatState() {
  return { sessionId: null, currentKey: null, currentCard: null, groups: [] };
}

function cardKey(card) {
  return card ? `${card.ts_code}:${card.period}` : null;
}

export function reduceBindCard(state, card) {
  const key = cardKey(card);
  if (!key) {
    return { ...state, sessionId: null, currentKey: null, currentCard: null };
  }
  if (state.currentKey === key) {
    return { ...state, currentCard: card };
  }
  const groups = state.groups.map((group) => ({ ...group, status: "past" }));
  groups.push({ key, card, status: "current" });
  return { sessionId: null, currentKey: key, currentCard: card, groups };
}

export function reduceChatResult(state, result) {
  return { ...state, sessionId: result.session_id || state.sessionId };
}

export function actionLabel(action) {
  if (action.action === "refetch_company") return "重新抓取单票研判卡";
  if (action.action === "rescan_disclosure_day") return "重扫披露日";
  return "执行动作";
}

export async function routeAction(action, executors) {
  if (action.action === "refetch_company") {
    await executors.refetchCompany(action.params.ts_code, action.params.period);
    return;
  }
  if (action.action === "rescan_disclosure_day") {
    await executors.rescanDisclosureDay(action.params.date);
    return;
  }
  throw new Error(`未知动作: ${action.action}`);
}

export function createAgentChat({ panel, api, executors }) {
  let state = createChatState();

  function bindCard(card) {
    const before = state.currentKey;
    state = reduceBindCard(state, card);
    if (!card) {
      panel.setContext(null);
      return;
    }
    if (before !== state.currentKey) {
      panel.startGroup(card);
    }
    panel.setContext(card);
  }

  async function send(question, retrying = false) {
    if (!state.currentCard) {
      panel.appendSystem("请先选择一张研判卡。");
      return;
    }
    const pending = panel.setPending(true);
    try {
      const result = await api.agentChat(
        state.currentCard.ts_code,
        state.currentCard.period,
        question,
        state.sessionId,
      );
      state = reduceChatResult(state, result);
      panel.replacePending(pending, result.answer, result.references || []);
      for (const action of result.actions || []) {
        panel.appendAction(action);
      }
    } catch (error) {
      if (!retrying && String(error.message || "").includes("session 与公司/报告期不匹配")) {
        state = { ...state, sessionId: null };
        panel.replacePending(pending, "会话已重置，正在重试…", []);
        await send(question, true);
        return;
      }
      panel.replacePending(pending, error.message || "Agent 调用失败", [], { retryQuestion: question });
    } finally {
      panel.setPending(false);
    }
  }

  async function executeAction(action, actionNode) {
    panel.setActionRunning(actionNode, true);
    try {
      await routeAction(action, executors);
      panel.setActionDone(actionNode);
      panel.appendSystem(`已执行：${actionLabel(action)}`);
    } catch (error) {
      panel.setActionRunning(actionNode, false);
      panel.appendSystem(error.message || "动作执行失败", true);
    }
  }

  panel.onSend(send);
  panel.onAction(executeAction);

  return { bindCard, clearCard: () => bindCard(null), send };
}

if (typeof window !== "undefined") {
  window.TradeEyeAgentChat = { createAgentChat };
}
