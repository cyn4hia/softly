export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key === "value") node.value = value;
    else if (value === true) node.setAttribute(key, "");
    else node.setAttribute(key, value);
  }
  append(node, children);
  return node;
}

function append(node, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
}

export function toast(message, kind = "ok") {
  const box = document.getElementById("toasts");
  const item = el("div", { class: `toast ${kind === "err" ? "err" : ""}` }, message);
  box.append(item);
  setTimeout(() => item.remove(), 3200);
}

export function timeAgo(iso) {
  if (!iso) return "";
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000;
  if (seconds < 50) return "just now";
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`;
  if (seconds < 86400 * 7) return `${Math.round(seconds / 86400)}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function fmtBytes(n) {
  if (!n && n !== 0) return "";
  if (n < 1024 * 1024) return `${Math.max(1, Math.round(n / 1024))} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function heartsStatic(rating) {
  return el(
    "span",
    { class: "hearts-static", title: `${rating}/5` },
    "♥".repeat(rating) + "♡".repeat(5 - rating),
  );
}

export function loading(label = "loading…") {
  return el("div", { class: "loading" }, el("div", { class: "spin-ring" }), label);
}

export function emptyState(title, sub) {
  return el(
    "div",
    { class: "empty" },
    el("h2", {}, title),
    sub ? el("p", { class: "muted" }, sub) : null,
  );
}
