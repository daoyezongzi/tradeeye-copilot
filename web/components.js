"use strict";

/*
 * 可复用 UI 原语。
 *
 * 折叠区用原生 <details> 直接写在 index.html 里，不需要 JS，因此不在这里。
 * 菜单需要 JS：菜单项由数据驱动，且要处理点外部关闭、Esc 关闭、方向键移动
 * 和 aria-expanded 同步。
 */

/* 顶栏「导出 ▾」。只负责壳与交互，具体动作由调用方通过 onSelect 传入。
   mount 是 HTML 里的占位节点，会被整体替换掉。 */
function createMenuButton({ mount, label, items }) {
  const wrap = document.createElement("div");
  wrap.className = "menu";

  const trigger = document.createElement("button");
  trigger.className = "outlined menu__trigger";
  trigger.textContent = `${label} ▾`;
  trigger.setAttribute("aria-haspopup", "menu");
  trigger.setAttribute("aria-expanded", "false");

  const list = document.createElement("div");
  list.className = "menu__list";
  list.setAttribute("role", "menu");
  list.hidden = true;

  const entries = items.map((item) => {
    const node = document.createElement("button");
    node.className = "menu__item";
    node.id = item.id;
    node.textContent = item.label;
    node.setAttribute("role", "menuitem");
    node.addEventListener("click", () => {
      close();
      item.onSelect();
    });
    list.append(node);
    return node;
  });

  function isOpen() {
    return !list.hidden;
  }

  function open() {
    list.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    entries[0].focus();
  }

  function close() {
    list.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
  }

  trigger.addEventListener("click", () => {
    if (isOpen()) close();
    else open();
  });

  /* Esc 关闭并把焦点还给触发按钮；方向键在项间循环 */
  wrap.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && isOpen()) {
      event.preventDefault();
      close();
      trigger.focus();
      return;
    }
    if (!isOpen()) return;
    const index = entries.indexOf(document.activeElement);
    if (index < 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      entries[(index + 1) % entries.length].focus();
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      entries[(index - 1 + entries.length) % entries.length].focus();
    }
  });

  /* 点菜单外部关闭。触发按钮自身的点击也会冒泡到这里，
     但它在 wrap 内，所以不会被这条误关。 */
  document.addEventListener("click", (event) => {
    if (isOpen() && !wrap.contains(event.target)) close();
  });

  wrap.append(trigger, list);
  mount.replaceWith(wrap);
  return { open, close };
}
