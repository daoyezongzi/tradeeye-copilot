const STATUS_META = {
  NORMAL: { label: "正常", cls: "ok", radarRadius: 42, note: "未触发异常规则" },
  WATCH: { label: "关注", cls: "yellow", radarRadius: 30, note: "命中黄色规则" },
  ANOMALY: { label: "异常", cls: "red", radarRadius: 18, note: "命中红色规则" },
  NOT_EVALUATED: { label: "不可计算", cls: "data", radarRadius: 0, note: "缺少必要数据" },
  NOT_APPLICABLE: { label: "不适用", cls: "data", radarRadius: 0, note: "当前行业或口径不适用" },
};

const STATUS_ORDER = ["ANOMALY", "WATCH", "NORMAL", "NOT_EVALUATED", "NOT_APPLICABLE"];

function textNode(text) {
  return document.createTextNode(text == null ? "" : String(text));
}

export function qualityStatusKey(factor) {
  const status = factor?.status;
  return Object.prototype.hasOwnProperty.call(STATUS_META, status) ? status : "NOT_EVALUATED";
}

export function qualityStatusMeta(status) {
  return STATUS_META[Object.prototype.hasOwnProperty.call(STATUS_META, status) ? status : "NOT_EVALUATED"];
}

export function qualitySummaryText(overview) {
  return overview?.summary || "暂无经营质量因子";
}

export function comparabilityWarningText(result) {
  if (!result) return "尚未生成对比";
  if (result.warnings?.length) return result.warnings.join("；");
  if (result.comparability === "STRICT") return "严格可比";
  if (result.comparability === "INCOMPLETE") return "对比数据不完整";
  return "仅供探索";
}

export function createRadarPoints(factors = []) {
  const total = Math.max(factors.length, 1);
  return factors.map((factor, index) => {
    const angle = -Math.PI / 2 + (Math.PI * 2 * index) / total;
    const radius = qualityStatusMeta(qualityStatusKey(factor)).radarRadius;
    return {
      x: 50 + Math.cos(angle) * radius,
      y: 50 + Math.sin(angle) * radius,
      radius,
      status: qualityStatusKey(factor),
    };
  });
}

function makeTag(label, cls) {
  const tag = document.createElement("span");
  tag.className = `tag ${cls}`;
  tag.textContent = label;
  return tag;
}

function observationText(observation = {}) {
  if (observation.value === null || observation.value === undefined || observation.value === "") return "不可计算";
  return `${observation.label} ${observation.value}${observation.unit || ""}`;
}

export function renderQualityOverview(card) {
  const wrap = document.createElement("section");
  wrap.className = "quality";
  const head = document.createElement("div");
  head.className = "quality__head";
  const title = document.createElement("div");
  title.className = "quality__title";
  title.append(textNode("经营质量："));
  const meta = qualityStatusMeta(card?.quality_overview?.status);
  title.append(makeTag(meta.label, meta.cls));
  const summary = document.createElement("p");
  summary.className = "quality__summary";
  summary.textContent = qualitySummaryText(card?.quality_overview);
  head.append(title, summary);
  wrap.append(head);

  const body = document.createElement("div");
  body.className = "quality__body";
  const list = document.createElement("div");
  list.className = "quality__list";
  for (const factor of card?.quality_factors || []) list.append(renderQualityFactor(card, factor));
  body.append(list, renderQualityRadar(card?.quality_factors || []));
  wrap.append(body);
  return wrap;
}

export function renderQualityFactor(card, factor) {
  const row = document.createElement("details");
  row.className = `quality-factor quality-factor--${qualityStatusMeta(qualityStatusKey(factor)).cls}`;
  const summary = document.createElement("summary");
  const meta = qualityStatusMeta(qualityStatusKey(factor));
  const title = document.createElement("strong");
  title.textContent = factor.label;
  const obs = document.createElement("span");
  obs.className = "quality-factor__obs";
  obs.textContent = observationText(factor.observations?.[0]);
  summary.append(makeTag(meta.label, meta.cls), title, obs);

  const detail = document.createElement("div");
  detail.className = "quality-factor__detail";
  const text = document.createElement("p");
  text.textContent = factor.summary;
  detail.append(text);
  const metaLine = document.createElement("div");
  metaLine.className = "quality-factor__meta";
  metaLine.textContent = `规则 ${factor.rule_ids?.join("、") || "—"} · 事实 ${factor.fact_ids?.join("、") || "—"}`;
  detail.append(metaLine);
  if (factor.rule_ids?.[0] && card?.findings?.some((finding) => finding.rule_id === factor.rule_ids[0])) {
    const evidence = document.createElement("button");
    evidence.type = "button";
    evidence.className = "outlined quality-factor__evidence";
    evidence.textContent = "查看依据";
    evidence.dataset.qualityRuleId = factor.rule_ids[0];
    detail.append(evidence);
  }
  row.append(summary, detail);
  return row;
}

export function renderQualityRadar(factors) {
  const wrap = document.createElement("div");
  wrap.className = "quality-radar";
  const points = createRadarPoints(factors);
  const polygon = points.filter((point) => point.radius > 0).map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
  const axes = points.map((point) => `<line x1="50" y1="50" x2="${point.x.toFixed(1)}" y2="${point.y.toFixed(1)}" />`).join("");
  const dots = points.map((point) => `<circle class="quality-radar__dot quality-radar__dot--${point.status.toLowerCase()}" cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="3.2" />`).join("");
  wrap.innerHTML = `
    <svg viewBox="0 0 100 100" role="img" aria-label="经营质量分档雷达图">
      <circle cx="50" cy="50" r="42"></circle>
      <circle cx="50" cy="50" r="30"></circle>
      <circle cx="50" cy="50" r="18"></circle>
      <g class="quality-radar__axis">${axes}</g>
      ${polygon ? `<polygon points="${polygon}"></polygon>` : ""}
      <g>${dots}</g>
    </svg>
    <div class="quality-radar__legend">外圈正常 · 中圈关注 · 内圈异常 · 灰色不可计算</div>
  `;
  return wrap;
}

export function renderQualityCompare(result) {
  const wrap = document.createElement("section");
  wrap.className = "quality-compare";
  const head = document.createElement("div");
  head.className = "quality-compare__head";
  const title = document.createElement("h3");
  title.textContent = "经营质量对比";
  const note = document.createElement("p");
  note.textContent = comparabilityWarningText(result);
  head.append(title, note);
  wrap.append(head);

  const table = document.createElement("div");
  table.className = "table-wrap";
  const factorLabels = result.items?.[0]?.quality_factors?.map((factor) => factor.label) || [];
  const rows = (result.items || []).map((card) => {
    const cells = (card.quality_factors || []).map((factor) => {
      const meta = qualityStatusMeta(qualityStatusKey(factor));
      return `<td><span class="tag ${meta.cls}">${meta.label}</span></td>`;
    }).join("");
    return `<tr><td class="mono">${card.ts_code}</td><td class="mono">${card.period}</td>${cells}</tr>`;
  }).join("");
  table.innerHTML = `
    <table>
      <thead><tr><th>代码</th><th>报告期</th>${factorLabels.map((label) => `<th>${label}</th>`).join("")}</tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  wrap.append(table);
  return wrap;
}

if (typeof window !== "undefined") {
  window.TradeEyeQualityView = {
    comparabilityWarningText,
    createRadarPoints,
    qualityStatusKey,
    qualityStatusMeta,
    qualitySummaryText,
    renderQualityCompare,
    renderQualityOverview,
  };
}
