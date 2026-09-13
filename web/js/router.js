import { el } from "./ui.js";

const routes = [];
let epoch = 0;

export function route(pattern, render) {
  routes.push({ pattern, render });
}

export function navigate(path) {
  location.hash = `#${path}`;
}

function safeDecode(segment) {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment; // malformed %-encoding shouldn't kill routing
  }
}

function match(pattern, path) {
  const p = pattern.split("/").filter(Boolean);
  const a = path.split("/").filter(Boolean);
  if (p.length !== a.length) return null;
  const params = {};
  for (let i = 0; i < p.length; i++) {
    if (p[i].startsWith(":")) params[p[i].slice(1)] = safeDecode(a[i]);
    else if (p[i] !== a[i]) return null;
  }
  return params;
}

export function startRouter(root, { onRoute } = {}) {
  async function render() {
    const my = ++epoch;
    const path = location.hash.replace(/^#/, "") || "/";
    for (const r of routes) {
      const params = match(r.pattern, path);
      if (params) {
        onRoute?.(path);
        // each navigation gets a fresh container: leftover async work from an
        // old view writes into a detached node, and its isConnected guards
        // (e.g. the session poll) go false the moment the user moves on.
        const container = el("div", { class: "route-root" });
        root.replaceChildren(container);
        window.scrollTo(0, 0);
        try {
          await r.render(container, params);
        } catch (err) {
          if (my !== epoch) return; // a newer navigation already took over
          container.replaceChildren(
            el("div", { class: "empty" },
              el("h2", {}, "something drifted off"),
              el("p", { class: "muted" }, String(err.message || err))),
          );
        }
        return;
      }
    }
    root.replaceChildren(
      el("div", { class: "empty" },
        el("h2", {}, "404 — lost in the clouds")),
    );
  }
  window.addEventListener("hashchange", render);
  render();
}
