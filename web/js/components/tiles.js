import { mediaUrl } from "../api.js";
import { el } from "../ui.js";

/** vertical video tile with hover-to-play preview */
export function videoTile(item, { selected = false, onToggle = null } = {}) {
  const video = el("video", {
    src: mediaUrl(item),
    preload: "metadata",
    muted: true,
    loop: true,
    playsinline: true,
  });
  video.muted = true; // attribute alone doesn't set the live property everywhere

  const tile = el(
    "div",
    {
      class: `tile ${selected ? "selected" : ""}`,
      onmouseenter: () => video.play().catch(() => {}),
      onmouseleave: () => {
        video.pause();
        try { video.currentTime = 0; } catch { /* not seekable yet */ }
      },
    },
    video,
    el("span", { class: "tile-name" }, item.name),
    onToggle ? el("span", { class: "tile-pick" }, selected ? "✓" : "+") : null,
  );
  if (onToggle) tile.addEventListener("click", () => onToggle(item));
  return tile;
}

export function soundRow(item, { selected = false, onToggle = null } = {}) {
  const row = el(
    "div",
    { class: `sound-row ${selected ? "selected" : ""}` },
    el("span", { class: "sound-name" }, item.name),
    el("audio", { controls: true, preload: "none", src: mediaUrl(item), onclick: (e) => e.stopPropagation() }),
  );
  if (onToggle) row.addEventListener("click", () => onToggle(item));
  return row;
}
