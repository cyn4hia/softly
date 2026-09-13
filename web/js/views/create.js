import { api } from "../api.js";
import { dropzone } from "../components/dropzone.js";
import { soundRow, videoTile } from "../components/tiles.js";
import { navigate } from "../router.js";
import { el, loading, toast } from "../ui.js";

const AUDIO_RE = /\.(mp3|wav|m4a|aac|ogg|flac)$/i;

const PRESET_TAGS = [
  "aesthetic", "vlog", "tutorial", "meme", "fashion",
  "food", "dance", "gaming", "mograph", "cozy",
];
const MAX_INSPO = 3;

export async function createView(root) {
  root.append(loading("gathering your library…"));
  const [videos, audio] = await Promise.all([
    api.get("/library?kind=video"),
    api.get("/library?kind=audio"),
  ]);
  root.replaceChildren();

  const state = {
    title: "",
    prompt: "",
    tags: new Set(),
    inspo: [],
    sound: null,
    submitting: false,
  };
  const key = (item) => `${item.source}:${item.path}`;

  // --- prompt card ---
  const titleInput = el("input", {
    type: "text",
    placeholder: "give it a name (optional) — e.g. \"strawberry drift\"",
    oninput: (e) => { state.title = e.target.value; },
  });
  const promptInput = el("textarea", {
    placeholder:
      "describe the video you're dreaming of… palette, motion, mood, pacing. " +
      "fable will write the animation and render it for you",
    oninput: (e) => { state.prompt = e.target.value; },
  });

  // --- tags card ---
  const tagRow = el("div", { class: "chip-row" });
  function renderTags() {
    tagRow.replaceChildren(
      ...[...new Set([...PRESET_TAGS, ...state.tags])].map((t) =>
        el("button", {
          class: `chip ${state.tags.has(t) ? "on" : ""}`,
          type: "button",
          onclick: () => {
            state.tags.has(t) ? state.tags.delete(t) : state.tags.add(t);
            renderTags();
          },
        }, t)),
    );
  }
  renderTags();
  const customTag = el("input", { type: "text", placeholder: "+ your own", onkeydown: (e) => {
    if (e.key === "Enter" && e.target.value.trim()) {
      e.preventDefault();
      state.tags.add(e.target.value.trim());
      e.target.value = "";
      renderTags();
    }
  }});

  // --- inspo picker ---
  const inspoGrid = el("div", { class: "picker-grid" });
  function renderInspo() {
    inspoGrid.replaceChildren(
      ...videos.items.map((item) =>
        videoTile(item, {
          selected: state.inspo.some((i) => key(i) === key(item)),
          onToggle: (it) => {
            const idx = state.inspo.findIndex((i) => key(i) === key(it));
            if (idx >= 0) state.inspo.splice(idx, 1);
            else if (state.inspo.length >= MAX_INSPO) {
              toast(`up to ${MAX_INSPO} inspo clips, softly`, "err");
              return;
            } else state.inspo.push(it);
            renderInspo();
          },
        })),
    );
  }
  renderInspo();

  async function refreshLibrary(saved = []) {
    const [freshVideos, freshAudio] = await Promise.all([
      api.get("/library?kind=video"),
      api.get("/library?kind=audio"),
    ]);
    videos.items = freshVideos.items;
    videos.sources = freshVideos.sources;
    audio.items = freshAudio.items;
    // dropped clips are probably the inspo you meant — select them
    for (const it of saved) {
      if (AUDIO_RE.test(it.path)) continue;
      const found = videos.items.find((x) => x.source === it.source && x.path === it.path);
      if (found && !state.inspo.some((i) => key(i) === key(found)) && state.inspo.length < MAX_INSPO) {
        state.inspo.push(found);
      }
    }
    renderInspo();
    renderSounds();
  }

  const inspoDrop = dropzone({
    label: "drag & drop new example clips here",
    sublabel: "saved into data/examples/ (tracked in the repo) and selected as inspo",
    onUploaded: refreshLibrary,
  });

  const mineMissing = !videos.sources.mine.configured;
  const inspoHint = !videos.items.length
    ? el("div", { class: "hint-card" },
        "your library is empty. drop example clips above, or point softly at your own folder by ",
        mineMissing
          ? el("span", {}, "copying ",
              el("code", {}, "config/settings.example.yaml"), " to ",
              el("code", {}, "config/settings.yaml"), " (your videos are only read, never copied or committed).")
          : el("span", {}, "adding files to ", el("code", {}, "data/examples/"), "."))
    : null;

  // --- sound picker ---
  const soundList = el("div", { class: "sound-list" });
  function renderSounds() {
    soundList.replaceChildren(
      ...audio.items.map((item) =>
        soundRow(item, {
          selected: state.sound !== null && key(state.sound) === key(item),
          onToggle: (it) => {
            state.sound = state.sound && key(state.sound) === key(it) ? null : it;
            renderSounds();
          },
        })),
    );
    if (!audio.items.length) {
      soundList.append(el("p", { class: "faint" },
        "no sounds found — add audio files to data/examples/ or set sounds_dir in config/settings.yaml"));
    }
  }
  renderSounds();

  // --- submit ---
  const submitBtn = el("button", { class: "btn", type: "button", onclick: submit }, "generate");
  async function submit() {
    if (!state.prompt.trim()) {
      toast("tell softly what you're dreaming of first", "err");
      promptInput.focus();
      return;
    }
    if (state.submitting) return;
    state.submitting = true;
    submitBtn.disabled = true;
    submitBtn.textContent = "starting the magic…";
    try {
      const session = await api.post("/sessions", {
        title: state.title.trim(),
        prompt: state.prompt.trim(),
        tags: [...state.tags],
        inspo: state.inspo.map((i) => ({ source: i.source, path: i.path, name: i.name })),
        sound: state.sound ? { source: state.sound.source, path: state.sound.path, name: state.sound.name } : null,
      });
      toast("your first take is brewing");
      navigate(`/session/${session.id}`);
    } catch (err) {
      toast(String(err.message || err), "err");
      state.submitting = false;
      submitBtn.disabled = false;
      submitBtn.textContent = "generate";
    }
  }

  root.append(
    el("div", { class: "view-head" },
      el("div", {},
        el("h1", {}, "new creation"),
        el("p", { class: "sub" }, "a prompt, a little inspo, maybe a sound — softly does the rest"))),
    el("div", { class: "create-form" },
      el("div", { class: "card form-card" },
        el("div", {}, el("label", { class: "field-label" }, "what are we making?"), titleInput),
        el("div", {}, el("label", { class: "field-label" }, "the dream"), promptInput)),
      el("div", { class: "card form-card" },
        el("label", { class: "field-label" }, "vibe / genre"),
        tagRow,
        el("div", { class: "inline-add" }, customTag)),
      el("div", { class: "card form-card" },
        el("label", { class: "field-label" }, `inspo clips (up to ${MAX_INSPO}) — fable will look at these`),
        inspoHint,
        inspoGrid,
        inspoDrop),
      el("div", { class: "card form-card" },
        el("label", { class: "field-label" }, "sound (optional) — muxed onto the final video"),
        soundList),
      el("div", { style: "display:flex; justify-content:flex-end;" }, submitBtn)),
  );
}
