async function request(path, options = {}) {
  const init = { method: options.method || "GET" };
  if (options.body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(options.body);
  }
  const res = await fetch(`/api${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      if (data.detail) detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch { /* non-json error body */ }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: "POST", body }),
  del: (path) => request(path, { method: "DELETE" }),
};

export async function uploadFiles(files) {
  const form = new FormData();
  for (const f of files) form.append("files", f, f.name);
  const res = await fetch("/api/library/upload", { method: "POST", body: form });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      if (data.detail) detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch { /* non-json error body */ }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export function mediaUrl(ref) {
  const encoded = ref.path.split("/").map(encodeURIComponent).join("/");
  return `/api/media/${ref.source}/${encoded}`;
}
