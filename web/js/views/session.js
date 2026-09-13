import { api, mediaUrl } from "../api.js";
import { navigate } from "../router.js";
import { el, heartsStatic, loading, timeAgo, toast } from "../ui.js";

const ASPECTS = ["pacing", "visuals", "vibe", "sound", "story"];
const POLL_MS = 2500;

function stateKey(session) {
  return JSON.stringify([session.rendering, session.versions.map((v) => v.status)]);
}

export async function sessionView(root, { id }) {
  root.append(loading());
  let session = await api.get(`/sessions/${id}`);
  let currentId = session.versions.at(-1)?.id ?? null;

  // drafts survive poll-triggered re-renders (feedback per take + revise box)
  const drafts = {};
  let reviseDraft = "";
  // one timer chain, ever; root is this navigation's own container, so
  // isConnected goes false as soon as the user moves to another view
  let pollTimer = null;
  // the <video> node is reused across re-renders so playback isn't reset
  let playerCache = { versionId: null, node: null };

  function draftFor(v) {
    return (drafts[v.id] ??= { rating: 0, aspects: {}, text: "" });
  }

  function current() {
    return session.versions.find((v) => v.id === currentId) ?? session.versions.at(-1) ?? null;
  }

  function schedulePoll() {
    if (!session.rendering || !root.isConnected) return;
    clearTimeout(pollTimer);
    pollTimer = setTimeout(async () => {
      if (!root.isConnected) return;
      try {
        const prev = stateKey(session);
        const stayOnLatest = currentId === session.versions.at(-1)?.id;
        const fresh = await api.get(`/sessions/${id}`);
        if (!root.isConnected) return;
        session = fresh;
        if (stayOnLatest) currentId = session.versions.at(-1)?.id ?? null;
        if (stateKey(session) !== prev) {
          const latest = session.versions.at(-1);
          if (!session.rendering && latest) {
            toast(
              latest.status === "ready" ? `take ${latest.number} is ready` : "that take stumbled",
              latest.status === "ready" ? "ok" : "err",
            );
          }
          render();
        } else {
          schedulePoll();
        }
      } catch (err) {
        if (err.status === 404) return; // creation was deleted — stop watching
        schedulePoll(); // transient hiccup; keep watching
      }
    }, POLL_MS);
  }

  async function revise(instructions) {
    try {
      session = await api.post(`/sessions/${id}/revise`, { instructions });
      currentId = session.versions.at(-1)?.id ?? null;
      reviseDraft = "";
      toast(`brewing take ${session.versions.length}…`);
      render();
    } catch (err) {
      toast(String(err.message || err), "err");
    }
  }

  function playerArea(v) {
    if (!v) return el("div", { class: "placeholder-screen" }, "no takes yet");
    if (v.status === "rendering") {
      return el("div", { class: "placeholder-screen rendering" },
        `fable is dreaming up take ${v.number}…`,
        el("span", { class: "faint" }, "writing the animation code, then rendering it — this can take a few minutes. wander freely, it keeps going."));
    }
    if (v.status === "failed") {
      return el("div", { class: "placeholder-screen" },
        "this take stumbled",
        el("span", { class: "faint" }, v.note || ""),
        el("button", { class: "btn btn-soft btn-sm", onclick: () => revise("") }, "try another take"));
    }
    if (v.media) {
      if (playerCache.versionId === v.id && playerCache.node) {
        const node = playerCache.node;
        const wasPlaying = !node.paused && !node.ended;
        if (wasPlaying) queueMicrotask(() => node.play().catch(() => {}));
        return node;
      }
      const node = el("video", { controls: true, playsinline: true, src: mediaUrl(v.media) });
      playerCache = { versionId: v.id, node };
      return node;
    }
    return el("div", { class: "placeholder-screen" },
      "no video for this take",
      el("span", { class: "faint" }, v.note || ""));
  }

  function feedbackComposer(v) {
    const fb = draftFor(v);

    const heartsRow = el("div", { class: "hearts" });
    function renderHearts() {
      heartsRow.replaceChildren(
        ...[1, 2, 3, 4, 5].map((n) =>
          el("button", {
            class: n <= fb.rating ? "on" : "",
            title: `${n}/5`,
            onclick: () => { fb.rating = fb.rating === n ? 0 : n; renderHearts(); },
          }, n <= fb.rating ? "♥" : "♡")),
      );
    }
    renderHearts();

    const aspectRow = el("div", { class: "aspect-row" });
    function renderAspects() {
      aspectRow.replaceChildren(
        ...ASPECTS.map((name) => {
          const vote = fb.aspects[name];
          const label = vote === "up" ? `${name} +` : vote === "down" ? `${name} −` : name;
          return el("button", {
            class: `chip ${vote === "up" ? "on" : vote === "down" ? "chip-down" : ""}`,
            title: "tap to cycle: liked → needs work → off",
            onclick: () => {
              fb.aspects[name] = vote === undefined ? "up" : vote === "up" ? "down" : undefined;
              if (fb.aspects[name] === undefined) delete fb.aspects[name];
              renderAspects();
            },
          }, label);
        }),
      );
    }
    renderAspects();

    const textArea = el("textarea", {
      placeholder: "what should change, softly? be as picky as you like — it all becomes training signal",
      value: fb.text,
      oninput: (e) => { fb.text = e.target.value; },
    });

    const sendBtn = el("button", { class: "btn btn-soft", onclick: send }, "send feedback");
    async function send() {
      if (!fb.rating && !fb.text.trim() && !Object.keys(fb.aspects).length) {
        toast("say a little something first", "err");
        return;
      }
      sendBtn.disabled = true;
      try {
        session = await api.post(`/sessions/${id}/versions/${v.id}/feedback`, fb);
        delete drafts[v.id];
        toast("noted, softly");
        render();
      } catch (err) {
        toast(String(err.message || err), "err");
        sendBtn.disabled = false;
      }
    }

    return el("div", { class: "card feedback-card" },
      el("h2", {}, `how's take ${v.number}?`),
      el("div", { style: "display:flex; align-items:center; gap:12px;" }, heartsRow),
      aspectRow,
      textArea,
      el("div", { style: "display:flex; justify-content:flex-end;" }, sendBtn));
  }

  function feedbackHistory(v) {
    if (!v || !v.feedback.length) return null;
    return el("div", { class: "card" },
      el("h2", {}, "notes on this take"),
      v.feedback.map((f) =>
        el("div", { class: "fb-item" },
          el("div", { class: "fb-meta" },
            f.rating ? heartsStatic(f.rating) : null,
            Object.entries(f.aspects || {}).map(([a, vote]) =>
              el("span", { class: `chip chip-tiny ${vote === "up" ? "on" : "chip-down"}` }, `${a} ${vote === "up" ? "+" : "−"}`)),
            el("span", { class: "faint", style: "margin-left:auto;" }, timeAgo(f.created_at))),
          f.text ? el("div", {}, f.text) : null)));
  }

  function reviseCard() {
    const instructions = el("textarea", {
      placeholder: "extra direction for the next take (optional) — your hearts & notes ride along automatically",
      style: "min-height:64px;",
      value: reviseDraft,
      oninput: (e) => { reviseDraft = e.target.value; },
    });
    const btn = el("button", {
      class: "btn",
      disabled: session.rendering,
      onclick: () => revise(reviseDraft.trim()),
    }, session.rendering ? "a take is rendering…" : "revise with this feedback");
    return el("div", { class: "card feedback-card" },
      el("h2", {}, "next take"),
      el("p", { class: "muted" }, "softly feeds your notes back into the animation code — praise stays, critiques change."),
      instructions,
      el("div", { style: "display:flex; justify-content:flex-end;" }, btn));
  }

  function render() {
    const v = current();
    root.replaceChildren();

    const title = session.title || session.prompt.slice(0, 48) || "untitled";
    root.append(
      el("a", { class: "back-link", href: "#/" }, "← creations"),
      el("div", { class: "view-head" },
        el("div", {},
          el("h1", {}, title),
          el("p", { class: "sub" },
            session.tags.map((t) => el("span", { class: "chip chip-tiny", style: "margin-right:5px;" }, t)),
            el("span", { class: "faint" }, ` started ${timeAgo(session.created_at)}`))),
        el("button", {
          class: "btn-ghost btn btn-sm",
          onclick: async () => {
            if (!confirm("delete this creation and its rendered takes?")) return;
            try {
              await api.del(`/sessions/${id}`);
              toast("tucked away");
              navigate("/");
            } catch (err) { toast(String(err.message || err), "err"); }
          },
        }, "delete")),
    );

    const takePills = el("div", { class: "take-pills" },
      session.versions.map((tv) =>
        el("button", {
          class: `take-pill ${tv.id === currentId ? "on" : ""}`,
          onclick: () => { currentId = tv.id; render(); },
        }, `take ${tv.number}${tv.status === "rendering" ? " …" : tv.status === "failed" ? " !" : ""}`)));

    const inspoStrip = (session.inspo.length || session.sound)
      ? el("div", { class: "inspo-strip" },
          el("span", { class: "faint" }, "inspo:"),
          session.inspo.map((ref) => el("video", { class: "mini", src: mediaUrl(ref), preload: "metadata", muted: true, title: ref.name || ref.path })),
          session.sound ? el("span", { class: "chip chip-tiny" }, `sound: ${session.sound.name || session.sound.path}`) : null)
      : null;

    const codeReveal = v?.code
      ? el("details", { class: "reveal" },
          el("summary", {}, "peek at the animation code"),
          el("pre", {}, v.code))
      : null;
    const logReveal = v?.log
      ? el("details", { class: "reveal" },
          el("summary", {}, "render log"),
          el("pre", {}, v.log))
      : null;

    root.append(
      el("div", { class: "session-layout" },
        el("div", { class: "card player-card" },
          playerArea(v),
          takePills,
          v?.note && v.status !== "failed" ? el("p", { class: "provider-note" }, v.note) : null,
          inspoStrip,
          codeReveal,
          logReveal),
        el("div", { class: "side-stack" },
          el("div", { class: "card" },
            el("h2", {}, "the dream"),
            el("p", { class: "muted", style: "margin-top:8px; line-height:1.6;" }, session.prompt)),
          v && v.status === "ready" ? feedbackComposer(v) : null,
          feedbackHistory(v),
          session.versions.length ? reviseCard() : null)),
    );

    schedulePoll();
  }

  render();
}
