/**
 * Application entrypoint. Boots modules, wires tabs, theme, device badge,
 * analytics refresh, session history, export buttons and TTS voices.
 */
import { api, downloadBlob } from "./api.js";
import { analytics } from "./charts.js";
import { initParticles } from "./particles.js";
import { speech } from "./speech.js";
import { toast } from "./toast.js";
import { SentenceBuilder } from "./sentence.js";
import { LiveCamera } from "./camera.js";
import { VideoMode } from "./video.js";
import { ImageMode } from "./image.js";
import { LearningMode } from "./learning.js";

class App {
  constructor() { this.currentSession = null; this.boot(); }

  boot() {
    initParticles();
    analytics.init();
    this.builder = new SentenceBuilder();
    this.camera = new LiveCamera(this.builder);
    this.video = new VideoMode();
    this.image = new ImageMode();
    this.learning = new LearningMode();
    speech.populateVoices(document.getElementById("voiceSelect"));
    this._wireTabs();
    this._wireTheme();
    this._wireExport();
    this._wireSessionEvents();
    this._checkHealth();
    this._loadHistory();
    setInterval(() => this._refreshDashboard(), 1500);
  }

  _wireTabs() {
    const tabs = [...document.querySelectorAll(".tab")];
    const indicator = document.getElementById("tabIndicator");
    const move = (tab) => {
      indicator.style.width = `${tab.offsetWidth}px`;
      indicator.style.transform = `translateX(${tab.offsetLeft - 6}px)`;
    };
    const activate = (name) => {
      tabs.forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
      document.querySelectorAll(".tab-panel").forEach((p) =>
        p.classList.toggle("active", p.id === `panel-${name}`));
      move(tabs.find((t) => t.dataset.tab === name));
    };
    tabs.forEach((t) => t.addEventListener("click", () => activate(t.dataset.tab)));
    window.addEventListener("resize", () => move(document.querySelector(".tab.active")));
    setTimeout(() => move(document.querySelector(".tab.active")), 50);
  }

  _wireTheme() {
    const btn = document.getElementById("themeToggle");
    btn.addEventListener("click", () => {
      document.body.classList.toggle("light");
      const light = document.body.classList.contains("light");
      btn.innerHTML = `<i class="fa-solid fa-${light ? "sun" : "moon"}"></i>`;
    });
  }

  _wireExport() {
    document.querySelectorAll("[data-export]").forEach((btn) =>
      btn.addEventListener("click", async () => {
        const fmt = btn.dataset.export;
        const sid = this.currentSession || this.camera.sessionId;
        if (!sid) { toast.err("No active session to export"); return; }
        try {
          const { blob, name } = await api.exportSession(sid, fmt);
          downloadBlob(blob, name);
          toast.ok(`Exported ${fmt.toUpperCase()}`);
        } catch (e) { toast.err("Export failed"); }
      }));
  }

  _wireSessionEvents() {
    window.addEventListener("session", (e) => {
      this.currentSession = e.detail.session_id;
      this._setDevice(e.detail.device);
    });
    window.addEventListener("session-ended", () => {
      this._loadHistory(); this.currentSession = null;
    });
  }

  _setDevice(device) {
    const badge = document.getElementById("deviceBadge");
    const gpu = device === "cuda";
    badge.className = `badge ${gpu ? "badge-gpu" : "badge-cpu"}`;
    badge.innerHTML = `<i class="fa-solid fa-microchip"></i> <b>${gpu ? "GPU" : "CPU"}</b>`;
    document.getElementById("aDevice").textContent = gpu ? "GPU" : "CPU";
  }

  async _checkHealth() {
    try {
      const h = await api.health();
      this._setDevice(h.model.device);
      if (h.model.loaded === false) toast.err("Model not loaded — real weights are required.");
    } catch (_) { toast.err("Backend unreachable"); }
  }

  async _refreshDashboard() {
    const sid = this.currentSession || this.camera.sessionId;
    if (!sid) return;
    try {
      const s = await api.getSession(sid);
      document.getElementById("aFrames").textContent = s.frames_processed;
      document.getElementById("aFps").textContent = s.avg_fps;
      document.getElementById("aConf").textContent = `${(s.avg_confidence * 100).toFixed(0)}%`;
      document.getElementById("aLatency").textContent = s.avg_latency_ms;
      document.getElementById("aLetters").textContent = s.accepted_letters.length;
      document.getElementById("aWords").textContent = (s.generated_text.trim().split(/\s+/).filter(Boolean)).length;
      document.getElementById("aDuration").textContent = `${Math.round(s.duration_s)}s`;
    } catch (_) {}
  }

  async _loadHistory() {
    try {
      const { sessions } = await api.sessionHistory();
      const wrap = document.getElementById("sessionHistory");
      if (!sessions.length) { wrap.innerHTML = '<p class="muted">No sessions yet.</p>'; return; }
      wrap.innerHTML = "";
      sessions.forEach((s) => {
        const div = document.createElement("div");
        div.className = "history-item";
        const date = new Date((s.started_at || 0) * 1000).toLocaleString();
        div.innerHTML = `
          <div>
            <div class="txt" dir="rtl">${s.generated_text || "—"}</div>
            <div class="meta">${date} · ${Math.round(s.duration_s)}s · ${(s.avg_confidence * 100).toFixed(0)}% · ${s.device.toUpperCase()}</div>
          </div>
          <div class="acts">
            <button class="mini-btn" data-exp="${s.session_id}" title="Export PDF"><i class="fa-solid fa-file-pdf"></i></button>
            <button class="mini-btn" data-del="${s.session_id}" title="Delete"><i class="fa-solid fa-trash"></i></button>
          </div>`;
        wrap.appendChild(div);
      });
      wrap.querySelectorAll("[data-exp]").forEach((b) =>
        b.addEventListener("click", async () => {
          try { const { blob, name } = await api.exportSession(b.dataset.exp, "pdf"); downloadBlob(blob, name); toast.ok("Report exported"); }
          catch (_) { toast.err("Export failed"); }
        }));
      wrap.querySelectorAll("[data-del]").forEach((b) =>
        b.addEventListener("click", async () => { await api.deleteSession(b.dataset.del).catch(() => {}); this._loadHistory(); }));
    } catch (_) {}
  }
}

document.addEventListener("DOMContentLoaded", () => new App());
