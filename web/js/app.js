import { api } from "./api.js";
import { route, startRouter } from "./router.js";
import { el } from "./ui.js";
import { createView } from "./views/create.js";
import { homeView } from "./views/home.js";
import { learningView } from "./views/learning.js";
import { libraryView } from "./views/library.js";
import { sessionView } from "./views/session.js";

route("/", homeView);
route("/create", createView);
route("/session/:id", sessionView);
route("/library", libraryView);
route("/learning", learningView);

function setActiveNav(path) {
  const first = path.split("/").filter(Boolean)[0] || "home";
  const key = { home: "home", create: "create", session: "home", library: "library", learning: "learning" }[first] || "home";
  for (const link of document.querySelectorAll("#nav a")) {
    if (link.dataset.route === key) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
}

startRouter(document.getElementById("view"), { onRoute: setActiveNav });

api.get("/config")
  .then((cfg) => {
    const parts = [
      el("div", {}, el("span", { class: "dot" }, "●"), ` ${cfg.provider} · ${cfg.model}`),
      el("div", {}, `effort: ${cfg.effort}`),
    ];
    if (!cfg.sources.mine.configured) {
      parts.push(el("div", {}, "tip: link your video folder in config/settings.yaml"));
    }
    document.getElementById("sidebar-foot").replaceChildren(...parts);
  })
  .catch(() => {
    document.getElementById("sidebar-foot").textContent = "backend unreachable";
  });
