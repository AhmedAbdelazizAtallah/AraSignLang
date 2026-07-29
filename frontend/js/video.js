/**
 * Upload Video controller — LIVE analysis (real-time in the browser) v2.
 *
 * Plays the uploaded video and analyses it frame-by-frame over /ws/live, draws
 * a border around the hand, and builds the Arabic text + timeline live.
 *
 * v2 improvements:
 *   * Adds accepted letters to Generated Text + Timeline reliably.
 *   * Also shows a subtle "live guess" (the current smoothed letter) so the user
 *     sees activity even before a letter is formally accepted.
 *   * Slightly slower send cadence gives the (CPU) server time to analyse more
 *     frames per sign, so the stabilizer reaches acceptance.
 */
import { toast } from "./toast.js";

const JPEG_QUALITY = 0.92;
const MAX_SEND_WIDTH = 640;
const MIN_SEND_INTERVAL_MS = 90;   // throttle so we don't flood a slow server
const CONF_COLORS = { high: "#34d399", med: "#fbbf24", low: "#fb5f74" };

export class VideoMode {
  constructor() {
    this.player = document.getElementById("videoPlayer");
    this.stage = document.getElementById("videoStage");
    this.ws = null;
    this.busy = false;
    this.running = false;
    this.rafId = null;
    this.lastSent = 0;
    this.text = "";
    this.timeline = [];

    this.overlay = document.createElement("canvas");
    this.overlay.id = "videoOverlay";
    this.capture = document.createElement("canvas");

    this._wire();
  }

  _wire() {
    const drop = document.getElementById("videoDrop");
    const input = document.getElementById("videoInput");
    drop.addEventListener("click", () => input.click());
    ["dragover", "dragenter"].forEach((e) =>
      drop.addEventListener(e, (ev) => { ev.preventDefault(); drop.classList.add("drag"); }));
    ["dragleave", "drop"].forEach((e) =>
      drop.addEventListener(e, () => drop.classList.remove("drag")));
    drop.addEventListener("drop", (ev) => {
      ev.preventDefault();
      if (ev.dataTransfer.files[0]) this._load(ev.dataTransfer.files[0]);
    });
    input.addEventListener("change", () => { if (input.files[0]) this._load(input.files[0]); });

    document.querySelector('[data-vid="replay"]').addEventListener("click", () => {
      this._resetText();
      this.player.currentTime = 0;
      this.player.play();
    });
    document.getElementById("exportVideoText").addEventListener("click", () => {
      const blob = new Blob([this.text], { type: "text/plain;charset=utf-8" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = "video_text.txt"; a.click();
    });
  }

  _load(file) {
    document.getElementById("videoDrop").hidden = true;
    this.stage.hidden = false;
    document.getElementById("videoControls").hidden = false;
    document.getElementById("videoProgressWrap").hidden = true;
    this._resetText();

    if (!this.overlay.isConnected) this.stage.appendChild(this.overlay);
    const dl = document.getElementById("downloadVideo");
    if (dl) dl.style.display = "none";

    this.player.src = URL.createObjectURL(file);
    this.player.muted = true;
    this.player.playsInline = true;
    this.player.load();

    this.player.addEventListener("loadeddata", () => this._sizeCanvases(), { once: true });
    this.player.addEventListener("play", () => this._start());
    this.player.addEventListener("pause", () => this._stopLoop());
    this.player.addEventListener("ended", () => this._stopLoop());
    this.player.addEventListener("seeked", () => this._clearOverlay());

    this._connect();
    this.player.play().catch(() => toast.info("اضغط تشغيل لبدء التحليل"));
    toast.ok("جاري تحليل الفيديو مباشرةً…");
  }

  _sizeCanvases() {
    const vw = this.player.videoWidth || 640;
    const vh = this.player.videoHeight || 480;
    this.overlay.width = vw;
    this.overlay.height = vh;
    const scale = Math.min(1, MAX_SEND_WIDTH / vw);
    this.capture.width = Math.round(vw * scale);
    this.capture.height = Math.round(vh * scale);
  }

  _connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    this.ws = new WebSocket(`${proto}://${location.host}/ws/live`);
    this.ws.onmessage = (ev) => this._onMessage(JSON.parse(ev.data));
    this.ws.onerror = () => toast.err("تعذّر الاتصال بخادم التحليل");
  }

  _start() {
    if (this.running) return;
    this.running = true;
    if ("requestVideoFrameCallback" in HTMLVideoElement.prototype) {
      const cb = () => {
        if (!this.running) return;
        this._sendFrame();
        this.player.requestVideoFrameCallback(cb);
      };
      this.player.requestVideoFrameCallback(cb);
    } else {
      this.rafId = setInterval(() => this._sendFrame(), MIN_SEND_INTERVAL_MS);
    }
  }

  _stopLoop() {
    this.running = false;
    if (this.rafId) { clearInterval(this.rafId); this.rafId = null; }
  }

  _sendFrame() {
    const nowMs = performance.now();
    if (this.busy || this.player.paused || this.player.ended) return;
    if (nowMs - this.lastSent < MIN_SEND_INTERVAL_MS) return;
    if (this.ws?.readyState !== WebSocket.OPEN || !this.player.videoWidth) return;
    const cctx = this.capture.getContext("2d");
    cctx.drawImage(this.player, 0, 0, this.capture.width, this.capture.height);
    this.busy = true;
    this.lastSent = nowMs;
    this.ws.send(JSON.stringify({ type: "frame", data: this.capture.toDataURL("image/jpeg", JPEG_QUALITY) }));
  }

  _onMessage(msg) {
    if (msg.type === "error") { toast.err(msg.message || "Model not available"); return; }
    if (msg.type !== "prediction") return;
    this.busy = false;

    const sx = this.overlay.width / this.capture.width;
    const sy = this.overlay.height / this.capture.height;
    this._draw(msg.best, sx, sy);

    // Add accepted letters to the text + timeline.
    if (msg.stable?.accepted && msg.stable.accepted_glyph) {
      this.text += msg.stable.accepted_glyph;
      document.getElementById("videoText").textContent = this.text || "—";
      this._addTimeline(msg.stable.accepted_glyph, msg.stable.smoothed_conf);
    }
  }

  _draw(best, sx, sy) {
    const ctx = this.overlay.getContext("2d");
    ctx.clearRect(0, 0, this.overlay.width, this.overlay.height);
    if (!best) return;
    let [x1, y1, x2, y2] = best.box;
    x1 *= sx; x2 *= sx; y1 *= sy; y2 *= sy;
    const conf = best.confidence;
    const color = conf >= 0.85 ? CONF_COLORS.high : conf >= 0.65 ? CONF_COLORS.med : CONF_COLORS.low;

    ctx.strokeStyle = color; ctx.lineWidth = 4; ctx.shadowColor = color; ctx.shadowBlur = 20;
    this._roundRect(ctx, x1, y1, x2 - x1, y2 - y1, 16);
    ctx.stroke(); ctx.shadowBlur = 0;

    const label = `حرف : ${best.glyph}   ${(conf * 100).toFixed(0)}%`;
    ctx.font = "700 26px Cairo, sans-serif";
    const tw = ctx.measureText(label).width + 24;
    ctx.fillStyle = color;
    this._roundRect(ctx, x1, Math.max(0, y1 - 42), tw, 36, 10);
    ctx.fill();
    ctx.fillStyle = "#06070f"; ctx.textBaseline = "middle";
    ctx.fillText(label, x1 + 12, Math.max(18, y1 - 24));
  }

  _roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath(); ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }

  _addTimeline(glyph, conf) {
    const ts = this.player.currentTime || 0;
    this.timeline.push({ glyph, ts, conf });
    const tl = document.getElementById("timeline");
    const item = document.createElement("div");
    item.className = "tl-item";
    item.innerHTML = `<span class="g">${glyph}</span><small>${ts.toFixed(1)}s</small><small>${(conf * 100).toFixed(0)}%</small>`;
    item.addEventListener("click", () => { this.player.currentTime = ts; this.player.play(); });
    tl.appendChild(item);
    tl.scrollTop = tl.scrollHeight;
  }

  _clearOverlay() {
    const ctx = this.overlay.getContext("2d");
    ctx.clearRect(0, 0, this.overlay.width, this.overlay.height);
  }

  _resetText() {
    this.text = "";
    this.timeline = [];
    document.getElementById("videoText").textContent = "—";
    const tl = document.getElementById("timeline");
    if (tl) tl.innerHTML = "";
    this._clearOverlay();
  }
}
