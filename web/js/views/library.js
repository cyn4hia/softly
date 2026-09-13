import { api, mediaUrl } from "../api.js";
import { dropzone } from "../components/dropzone.js";
import { soundRow, videoTile } from "../components/tiles.js";
import { el, emptyState, fmtBytes, loading, toast } from "../ui.js";

const TABS = [
  ["mine", "my clips"],
  ["examples", "examples"],
  ["generated", "generated"],
  ["sounds", "sounds"],
];

export async function libraryView(root) {
  root.append(loading("opening the library…"));
  let [videos, audio] = await Promise.all([
    api.get("/library?kind=video"),
    api.get("/library?kind=audio"),
  ]);
  root.replaceChildren();

  let tab = "mine";
  const body = el("div", {});
  const tabsRow = el("div", { class: "tabs" });

  async function refresh() {
    [videos, audio] = await Promise.all([
      api.get("/library?kind=video"),
      api.get("/library?kind=audio"),
    ]);
    renderBody();
  }

  function renderTabs() {
    tabsRow.replaceChildren(
      ...TABS.map(([key, label]) =>
        el("button", {
          class: `tab ${tab === key ? "on" : ""}`,
          onclick: () => { tab = key; renderTabs(); renderBody(); },
        }, label)),
    );
  }

  function tagEditor(item) {
    const wrap = el("div", { class: "tag-editor" });
    function draw() {
      wrap.replaceChildren(
        ...item.tags.map((t) =>
          el("button", {
            class: "chip chip-tiny on",
            title: "remove tag",
            onclick: () => save(item.tags.filter((x) => x !== t)),
          }, `${t} ×`)),
        el("input", {
          type: "text",
          placeholder: "+ tag",
          onkeydown: (e) => {
            const value = e.target.value.trim();
            if (e.key === "Enter" && value) {
              e.preventDefault();
              if (!item.tags.includes(value)) save([...item.tags, value]);
              else e.target.value = "";
            }
          },
        }),
      );
    }
    async function save(tags) {
      try {
        await api.post("/library/tags", { source: item.source, path: item.path, tags });
        item.tags = tags;
        draw();
      } catch (err) {
        toast(String(err.message || err), "err");
      }
    }
    draw();
    return wrap;
  }

  function setupCard() {
    return el("div", { class: "hint-card", style: "max-width:640px;" },
      el("b", {}, "point softly at your videos"), el("br", {}),
      "copy ", el("code", {}, "config/settings.example.yaml"), " to ",
      el("code", {}, "config/settings.yaml"), " and set ", el("code", {}, "videos_dir"),
      " to your folder. that file stays out of git, and your clips are only ever read from where they live — never moved, copied, or committed.");
  }

  function renderBody() {
    body.replaceChildren();
    if (tab === "sounds") {
      body.append(
        el("div", { style: "max-width:640px; margin-bottom:16px;" },
          dropzone({
            label: "drag & drop sounds here — or click to browse",
            sublabel: "saved into data/examples/ (tracked in the repo — keep it shareable)",
            accept: "audio/*",
            onUploaded: refresh,
          })),
      );
      if (!audio.items.length) {
        body.append(emptyState("no sounds yet", "drop audio above, or set sounds_dir in config/settings.yaml"));
        return;
      }
      body.append(el("div", { class: "sound-list" }, audio.items.map((item) => soundRow(item))));
      return;
    }

    if (tab === "examples") {
      body.append(
        el("div", { style: "margin-bottom:16px;" },
          dropzone({
            label: "drag & drop example clips here — or click to browse",
            sublabel: "saved into data/examples/ (tracked in the repo — keep it shareable, not your private stuff)",
            onUploaded: refresh,
          })),
      );
    }

    const items = videos.items.filter((i) => i.source === tab);
    if (tab === "mine" && !videos.sources.mine.configured) {
      body.append(setupCard());
      return;
    }
    if (!items.length) {
      const notes = {
        mine: ["your folder is connected but empty-looking", `softly is watching ${videos.sources.mine.path || "your folder"} for video files`],
        examples: ["no example clips yet", "drop reference clips above and they'll live in data/examples/"],
        generated: ["nothing generated yet", "make your first creation and it'll bloom here"],
      };
      const [t, s] = notes[tab];
      body.append(emptyState(t, s));
      return;
    }
    body.append(
      el("div", { class: "library-grid" },
        items.map((item) =>
          el("div", { class: "library-item" },
            videoTile(item),
            el("span", { class: "lib-name", title: item.path }, item.name),
            el("span", { class: "faint" }, fmtBytes(item.size)),
            tagEditor(item)))),
    );
  }

  renderTabs();
  renderBody();

  root.append(
    el("div", { class: "view-head" },
      el("div", {},
        el("h1", {}, "library"),
        el("p", { class: "sub" }, "inspo in, creations out — tag things so softly learns what matches what"))),
    tabsRow,
    body,
  );
}
