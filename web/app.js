const dateInput = document.querySelector("#date-input");
const title = document.querySelector("#summary-title");
const summaryLine = document.querySelector("#summary-line");
const cards = document.querySelector("#cards");
const dialog = document.querySelector("#evidence-dialog");
const evidenceContent = document.querySelector("#evidence-content");
const closeDialog = document.querySelector("#close-dialog");

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

async function loadDaily(date) {
  const response = await fetch(`/api/daily/${date}`);
  const summary = await response.json();
  title.textContent = `${summary.date} 财报研判 · 覆盖池 ${summary.coverage_count} 只`;
  summaryLine.textContent = `今日披露 ${summary.disclosed_count} 家 | 需优先关注 ${summary.red_count} | 留意 ${summary.yellow_count} | 未见异常 ${summary.ok_count}`;
  cards.innerHTML = "";
  for (const card of summary.cards) {
    cards.appendChild(renderCard(card));
  }
}

closeDialog.addEventListener("click", () => dialog.close());
dateInput.addEventListener("change", () => loadDaily(dateInput.value));
loadDaily(dateInput.value);
