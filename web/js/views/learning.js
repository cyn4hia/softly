import { api } from "../api.js";
import { el, emptyState, loading, timeAgo } from "../ui.js";

function describe(ev) {
  const p = ev.payload || {};
  switch (ev.type) {
    case "creation": return `new creation — "${(p.prompt || "").slice(0, 60)}"`;
    case "generation": return `take ${p.version} ${p.ok ? "rendered" : "failed"} (${p.provider})`;
    case "feedback": return `feedback on take ${p.version}${p.rating ? ` — ${p.rating}/5 ♥` : ""}`;
    case "library_tag": return `tagged ${p.path}: ${(p.tags || []).join(", ") || "(cleared)"}`;
    case "library_upload": return `added example: ${p.path}`;
    case "deleted": return "a creation was deleted";
    default: return ev.type;
  }
}

export async function learningView(root) {
  root.append(loading("counting the petals…"));
  const [stats, eventsData] = await Promise.all([
    api.get("/learning/stats"),
    api.get("/learning/events?limit=40"),
  ]);
  root.replaceChildren();

  root.append(
    el("div", { class: "view-head" },
      el("div", {},
        el("h1", {}, "learning"),
        el("p", { class: "sub" }, "everything softly is picking up from your taste — the seed of the future reward model"))),
  );

  root.append(
    el("div", { class: "stat-row" },
      statTile(stats.sessions, "creations"),
      statTile(stats.versions, "takes rendered"),
      statTile(stats.feedback, "feedback notes"),
      statTile(stats.avg_rating === null ? "—" : `♥ ${stats.avg_rating}`, "avg hearts")),
  );

  if (!stats.sessions) {
    root.append(emptyState("nothing to learn from yet", "make a creation, leave feedback — softly remembers all of it"));
    return;
  }

  const maxTag = Math.max(1, ...stats.tags.map(([, n]) => n));
  const tagCard = el("div", { class: "card" },
    el("h2", {}, "vibes you make"),
    stats.tags.length
      ? el("div", { class: "bar-rows" },
          stats.tags.slice(0, 8).map(([tag, n]) =>
            el("div", { class: "bar-row" },
              el("span", { class: "bar-label", title: tag }, tag),
              el("div", { class: "bar-track" },
                el("div", { class: "bar-fill", style: `width:${Math.round((n / maxTag) * 100)}%` })),
              el("span", { class: "bar-value" },
                `${n}${stats.tag_ratings[tag] ? ` · ♥${stats.tag_ratings[tag]}` : ""}`))))
      : el("p", { class: "faint" }, "tag your creations and this fills in"));

  const aspectEntries = Object.entries(stats.aspects);
  const aspectCard = el("div", { class: "card" },
    el("h2", {}, "what lands, what doesn't"),
    aspectEntries.length
      ? el("table", { class: "aspect-table" },
          el("tbody", {},
            aspectEntries.map(([name, votes]) =>
              el("tr", {},
                el("td", {}, name),
                el("td", { class: "vote" }, `liked ${votes.up}`),
                el("td", { class: "vote" }, `needs work ${votes.down}`)))))
      : el("p", { class: "faint" }, "use the aspect chips when leaving feedback"));

  const keywordCard = el("div", { class: "card" },
    el("h2", {}, "words in your feedback"),
    stats.keywords.length
      ? el("div", { class: "keyword-cloud" },
          stats.keywords.map(([word, n]) => el("span", { class: "chip" }, `${word} · ${n}`)))
      : el("p", { class: "faint" }, "write a few notes and the patterns show up here"));

  const feedCard = el("div", { class: "card" },
    el("h2", {}, "recent moments"),
    eventsData.events.length
      ? el("div", { class: "event-feed" },
          eventsData.events.map((ev) =>
            el("div", { class: "event-item" },
              el("span", { class: "event-dot" }, "•"),
              el("span", {}, describe(ev)),
              el("span", { class: "when" }, timeAgo(ev.ts)))))
      : el("p", { class: "faint" }, "quiet so far"));

  root.append(
    el("div", { class: "learning-grid" }, tagCard, aspectCard, keywordCard, feedCard),
    el("div", { class: "hint-card", style: "margin-top:16px;" },
      "every prompt, take, and note lands in ", el("i", {}, "data/learning/"),
      " (tracked in the repo — video files stay out). later, your view & interaction statistics will join it to sharpen the reward signal."),
  );
}

function statTile(num, label) {
  return el("div", { class: "card stat-tile" },
    el("div", { class: "stat-num" }, String(num)),
    el("div", { class: "stat-label" }, label));
}
