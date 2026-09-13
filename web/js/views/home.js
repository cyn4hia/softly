import { api } from "../api.js";
import { el, emptyState, loading, timeAgo } from "../ui.js";

function statusBadge(s) {
  if (s.rendering) return el("span", { class: "badge badge-rendering" }, "rendering…");
  if (s.status === "failed") return el("span", { class: "badge badge-failed" }, "needs a retry");
  if (!s.has_media && s.versions > 0) return el("span", { class: "badge badge-stub" }, "no video yet");
  return null;
}

function sessionCard(s) {
  const meta = [];
  meta.push(`${s.versions} take${s.versions === 1 ? "" : "s"}`);
  if (s.avg_rating) meta.push(`♥ ${s.avg_rating}`);
  meta.push(timeAgo(s.updated_at));

  return el(
    "a",
    { class: "card session-card", href: `#/session/${s.id}` },
    el("div", { style: "display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:6px;" },
      el("h3", {}, s.title || s.prompt.slice(0, 42) || "untitled"),
      statusBadge(s)),
    el("p", { class: "prompt-snippet" }, s.prompt),
    s.tags.length
      ? el("div", { class: "chips" }, s.tags.map((t) => el("span", { class: "chip chip-tiny" }, t)))
      : null,
    el("div", { class: "meta" }, meta.join(" · ")),
  );
}

export async function homeView(root) {
  root.append(loading());
  const data = await api.get("/sessions");
  root.replaceChildren();

  root.append(
    el("div", { class: "view-head" },
      el("div", {},
        el("h1", {}, "your creations"),
        el("p", { class: "sub" }, "every take, every note — softly learns from all of it")),
      el("a", { class: "btn", href: "#/create" }, "new creation")),
  );

  if (!data.sessions.length) {
    root.append(
      emptyState("nothing here yet", "let's make something soft and lovely — start your first creation"),
    );
    return;
  }
  root.append(el("div", { class: "session-grid" }, data.sessions.map(sessionCard)));
}
