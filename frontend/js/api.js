/** Thin REST client for the backend API. */
async function jsonFetch(url, options = {}) {
  const res = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

export const api = {
  health: () => jsonFetch("/health"),
  suggestWords: (prefix, limit = 6) =>
    jsonFetch("/api/language/suggest", { method: "POST", body: JSON.stringify({ prefix, limit }) }),
  suggestSentences: (text, limit = 5) =>
    jsonFetch("/api/language/sentences", { method: "POST", body: JSON.stringify({ text, limit }) }),

  async detectImage(file) {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/detect/image", { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async detectVideo(file) {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/detect/video", { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  videoProgress: (jobId) => jsonFetch(`/api/video/progress/${jobId}`),
  sessionHistory: () => jsonFetch("/api/sessions/history"),
  getSession: (id) => jsonFetch(`/api/sessions/${id}`),
  deleteSession: (id) => jsonFetch(`/api/sessions/${id}`, { method: "DELETE" }),

  async exportSession(sessionId, format) {
    const res = await fetch("/api/sessions/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, format }),
    });
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const cd = res.headers.get("Content-Disposition") || "";
    const name = /filename="?([^"]+)"?/.exec(cd)?.[1] || `report.${format}`;
    return { blob, name };
  },
};

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
