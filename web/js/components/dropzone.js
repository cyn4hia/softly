import { uploadFiles } from "../api.js";
import { el, toast } from "../ui.js";

/** drag-and-drop (or click-to-browse) upload target.
 *  files land in data/examples/ via /api/library/upload. */
export function dropzone({ label, sublabel, accept = "video/*,audio/*", onUploaded } = {}) {
  const input = el("input", {
    type: "file",
    multiple: true,
    accept,
    style: "display:none;",
    onchange: () => {
      if (input.files.length) handle([...input.files]);
      input.value = "";
    },
  });
  const title = el("span", { class: "dz-title" }, label || "drag & drop clips here — or click to browse");
  const zone = el(
    "div",
    { class: "dropzone", role: "button", tabindex: "0" },
    title,
    sublabel ? el("span", { class: "dz-sub" }, sublabel) : null,
    input,
  );

  zone.addEventListener("click", () => input.click());
  zone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); }
  });
  for (const type of ["dragenter", "dragover"]) {
    zone.addEventListener(type, (e) => {
      e.preventDefault();
      zone.classList.add("drag");
    });
  }
  zone.addEventListener("dragleave", (e) => {
    if (zone.contains(e.relatedTarget)) return;
    zone.classList.remove("drag");
  });
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("drag");
    const files = [...(e.dataTransfer?.files || [])];
    if (files.length) handle(files);
  });

  let busy = false;
  async function handle(files) {
    if (busy) return;
    busy = true;
    zone.classList.add("busy");
    const restore = title.textContent;
    title.textContent = `adding ${files.length} file${files.length === 1 ? "" : "s"}…`;
    try {
      const result = await uploadFiles(files);
      for (const err of result.errors) toast(`${err.name}: ${err.error}`, "err");
      if (result.saved.length) {
        toast(`added ${result.saved.length} file${result.saved.length === 1 ? "" : "s"} to examples`);
        onUploaded?.(result.saved);
      }
    } catch (err) {
      toast(String(err.message || err), "err");
    } finally {
      busy = false;
      zone.classList.remove("busy");
      title.textContent = restore;
    }
  }

  return zone;
}
