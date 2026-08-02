import test from "node:test";
import assert from "node:assert/strict";

import {
  actionLabel,
  createChatState,
  reduceBindCard,
  reduceChatResult,
  routeAction,
} from "./agent-chat.js";

test("bindCard starts a current group and clears session on card change", () => {
  let state = createChatState();
  state = reduceBindCard(state, { ts_code: "000001.SZ", period: "20250630", severity: "YELLOW" });
  state = reduceChatResult(state, { session_id: "session-1" });
  state = reduceBindCard(state, { ts_code: "603026.SH", period: "20250630", severity: "RED" });

  assert.equal(state.sessionId, null);
  assert.equal(state.currentKey, "603026.SH:20250630");
  assert.equal(state.groups[0].status, "past");
  assert.equal(state.groups[1].status, "current");
});

test("bindCard reuses group and session when card is unchanged", () => {
  let state = createChatState();
  state = reduceBindCard(state, { ts_code: "000001.SZ", period: "20250630", severity: "YELLOW" });
  state = reduceChatResult(state, { session_id: "session-1" });
  state = reduceBindCard(state, { ts_code: "000001.SZ", period: "20250630", severity: "YELLOW" });

  assert.equal(state.sessionId, "session-1");
  assert.equal(state.groups.length, 1);
});

test("reduceChatResult stores latest session id", () => {
  const state = reduceChatResult(createChatState(), { session_id: "session-2" });

  assert.equal(state.sessionId, "session-2");
});

test("routeAction dispatches refetch_company", async () => {
  const calls = [];
  await routeAction(
    { action: "refetch_company", params: { ts_code: "000001.SZ", period: "20250630" } },
    { refetchCompany: async (...args) => calls.push(args), rescanDisclosureDay: async () => calls.push(["bad"]) },
  );

  assert.deepEqual(calls, [["000001.SZ", "20250630"]]);
});

test("routeAction dispatches rescan_disclosure_day", async () => {
  const calls = [];
  await routeAction(
    { action: "rescan_disclosure_day", params: { date: "20250821" } },
    { refetchCompany: async () => calls.push(["bad"]), rescanDisclosureDay: async (...args) => calls.push(args) },
  );

  assert.deepEqual(calls, [["20250821"]]);
});

test("actionLabel returns readable Chinese labels", () => {
  assert.equal(actionLabel({ action: "refetch_company" }), "重新抓取单票研判卡");
  assert.equal(actionLabel({ action: "rescan_disclosure_day" }), "重扫披露日");
});
