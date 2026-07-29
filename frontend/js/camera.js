/**
 * Live Camera controller — HIGH-QUALITY capture.
 *
 * ROOT-CAUSE FIX for "no hand detected" in live mode:
 *   Previously the browser shrank each frame to 416x312 and compressed it hard
 *   (JPEG q=0.6) BEFORE sending. The model — trained on clear 416x416 images —
 *   then received a tiny, double-compressed frame and saw no hand, even though
 *   the SAME model detects perfectly on uploaded photos.
 *
 * The fix: send the frame at (near) the camera's native resolution and high
 * JPEG quality, and let the SERVER do a single clean resize to 416x416. This
 * makes a live frame just as clean as an uploaded photo → detection works.
 *
 * Renders: animated confidence-coloured box, current letter, confidence bar,
 * prediction history, live stats, smart-guide colour + hints and quality LED.
 * Accepted letters feed the SentenceBuilder and analytics charts.
 */
import { analytics } from "./charts.js";
import { toast } from "./toast.js";

const CONF_COLORS = { high: "#34d399", med: "#fbbf24", low: "#fb5f74" };
const QUALITY_MAP = {
  ok: { led: "ok", text: "🟢 Hand detected" },
  partial: { led: "partial", text: "🟡 Partial hand" },
  low_light: { led: "low", text: "🟠 Low lighting" },
  none: { led: "none", text: "🔴 No hand" },
  loading: { led: "", text: "⚪ Camera loading" },
};

// How often we send a frame (ms). ~8 fps is smooth and keeps the server light.
const SEND_INTERVAL_MS = 120;
// JPEG quality for the sent frame (high, so the model sees a clean image).
const JPEG_QUALITY = 0.92;
// Max width we send (keeps bandwidth sane while staying well above 416).
const MAX_SEND_WIDTH = 640;

export class LiveCamera {
  constructor(builder) {
    this.builder = builder;
    this.ws = null;
    this.stream = null;
    this.running = false;
    this.sessionId = null;
    this.sendTimer = null;
    this.history = [];
    this.letterCounts = {};
    this.frameNo = 0;
    this.busy = false; // avoid piling up frames if the server is slow

    this.video = document.getElementById("webcam");
    this.overlay = document.getElementById("overlay");
    this.ctx = this.overlay.getContext("2d");
    this.capture = document.createElement("canvas");
    this._wire();
  }

  _wire() {
    document.getElementById("startCam").addEventListener("click", () => this.start());
    document.getElementById("stopCam").addEventListener("click", () => this.stop());
  }

  async start() {
    try {
      // Ask for a decent resolution; the browser gives the closest it can.
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
        audio: false,
      });
      this.video.srcObject = this.stream;
      await this.video.play();
      // Wait until real dimensions are known before sizing canvases.
      if (!this.video.videoWidth) {
        await new Promise((r) => this.video.addEventListener("loadeddata", r, { once: true }));
      }
      document.getElementById("camPlaceholder").style.display = "none";
      document.getElementById("recDot").classList.add("on");
      document.getElementById("startCam").disabled = true;
      document.getElementById("stopCam").disabled = false;
      this._sizeCanvas();
      this._connect();
      this.running = true;
    } catch (err) {
      toast.err("Camera access denied or unavailable");
    }
  }

  stop() {
    this.running = false;
    clearInterval(this.sendTimer);
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify({ type: "end" }));
    this.ws?.close();
    this.stream?.getTracks().forEach((t) => t.stop());
    this.ctx.clearRect(0, 0, this.overlay.width, this.overlay.height);
    document.getElementById("camPlaceholder").style.display = "grid";
    document.getElementById("recDot").classList.remove("on");
    document.getElementById("startCam").disabled = false;
    document.getElementById("stopCam").disabled = true;
    this._setQuality("loading");
  }

  _sizeCanvas() {
    const vw = this.video.videoWidth || 640;
    const vh = this.video.videoHeight || 480;
    // Overlay matches the true video size so boxes line up exactly.
    this.overlay.width = vw;
    this.overlay.height = vh;
    // Capture at native resolution (capped at MAX_SEND_WIDTH) — NO tiny 416
    // pre-shrink. The server does the single clean resize to 416.
    const scale = Math.min(1, MAX_SEND_WIDTH / vw);
    this.capture.width = Math.round(vw * scale);
    this.capture.height = Math.round(vh * scale);
  }

  _connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    this.ws = new WebSocket(`${proto}://${location.host}/ws/live`);
    this.ws.onopen = () => {
      this.sendTimer = setInterval(() => this._sendFrame(), SEND_INTERVAL_MS);
    };
    this.ws.onmessage = (ev) => this._onMessage(JSON.parse(ev.data));
    this.ws.onclose = () => clearInterval(this.sendTimer);
    this.ws.onerror = () => toast.err("Live connection error");
  }

  _sendFrame() {
    if (!this.running || this.busy || this.ws?.readyState !== WebSocket.OPEN) return;
    if (!this.video.videoWidth) return; // not ready yet
    const cctx = this.capture.getContext("2d");
    cctx.drawImage(this.video, 0, 0, this.capture.width, this.capture.height);
    const data = this.capture.toDataURL("image/jpeg", JPEG_QUALITY);
    this.busy = true; // released when the next prediction arrives
    this.ws.send(JSON.stringify({ type: "frame", data }));
    this.ws.send(JSON.stringify({ type: "text", value: this.builder.text }));
  }

  _onMessage(msg) {
    if (msg.type === "error") { toast.err(msg.message || "Model not available"); this.stop(); return; }
    if (msg.type === "session") {
      this.sessionId = msg.session_id;
      window.dispatchEvent(new CustomEvent("session", { detail: msg }));
      return;
    }
    if (msg.type === "ended") {
      window.dispatchEvent(new CustomEvent("session-ended", { detail: msg.stats }));
      return;
    }
    if (msg.type !== "prediction") return;

    this.busy = false; // ready to send the next frame
    this.frameNo += 1;
    this._drawBox(msg.best);
    this._updatePrediction(msg);
    this._setQuality(msg.quality);
    this._setGuide(msg.guide, msg.hint);
    this._updateStats(msg.stats, msg.best);
    if (msg.stable?.accepted) this._onAccepted(msg.stable);
  }

  _drawBox(best) {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.overlay.width, this.overlay.height);
    if (!best) return;
    const [x1, y1, x2, y2] = best.box;
    const conf = best.confidence;
    const color = conf >= 0.85 ? CONF_COLORS.high : conf >= 0.65 ? CONF_COLORS.med : CONF_COLORS.low;
    ctx.strokeStyle = color; ctx.lineWidth = 3; ctx.shadowColor = color; ctx.shadowBlur = 18;
    this._roundRect(ctx, x1, y1, x2 - x1, y2 - y1, 14);
    ctx.stroke(); ctx.shadowBlur = 0;
    const label = `حرف : ${best.glyph}   ${(conf * 100).toFixed(1)}%`;
    ctx.font = "600 20px Cairo, sans-serif";
    const tw = ctx.measureText(label).width + 20;
    ctx.fillStyle = color;
    this._roundRect(ctx, x1, Math.max(0, y1 - 34), tw, 30, 8);
    ctx.fill();
    ctx.fillStyle = "#06070f"; ctx.textBaseline = "middle";
    ctx.fillText(label, x1 + 10, Math.max(15, y1 - 19));
  }

  _roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath(); ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }

  _updatePrediction(msg) {
    const glyph = msg.stable?.smoothed_glyph || (msg.best ? msg.best.glyph : "—");
    const conf = msg.stable?.smoothed_conf || (msg.best ? msg.best.confidence : 0);
    const $letter = document.getElementById("currentLetter");
    if ($letter.textContent !== glyph && glyph) $letter.textContent = glyph || "—";
    document.getElementById("confFill").style.width = `${(conf * 100).toFixed(1)}%`;
    document.getElementById("confLabel").textContent = `${(conf * 100).toFixed(1)}%`;
    analytics.sample({ confidence: conf || null, fps: msg.stats.fps, latency: msg.stats.latency_ms, frame: this.frameNo });
  }

  _onAccepted(stable) {
    const $letter = document.getElementById("currentLetter");
    $letter.classList.remove("accept-flash");
    void $letter.offsetWidth;
    $letter.classList.add("accept-flash");
    this.builder.acceptToken(stable.accepted_name, stable.accepted_glyph);
    if (stable.accepted_glyph) {
      this.history.unshift(stable.accepted_glyph);
      this.history = this.history.slice(0, 14);
      document.getElementById("historyStrip").innerHTML =
        this.history.map((g) => `<span class="h-letter">${g}</span>`).join("");
      this.letterCounts[stable.accepted_glyph] = (this.letterCounts[stable.accepted_glyph] || 0) + 1;
      analytics.setLetters(this.letterCounts);
    }
  }

  _setQuality(q) {
    const info = QUALITY_MAP[q] || QUALITY_MAP.none;
    document.querySelector("#qualityPill .q-led").className = `q-led ${info.led}`;
    document.getElementById("qualityText").textContent = info.text;
  }

  _setGuide(status, hint) {
    document.getElementById("guideBox").dataset.status = status || "adjust";
    document.getElementById("guideHint").textContent = hint || "";
  }

  _updateStats(stats, best) {
    document.getElementById("statFps").textContent = stats.fps;
    document.getElementById("statLatency").textContent = stats.latency_ms;
    document.getElementById("statFrames").textContent = stats.frames;
    document.getElementById("statConf").textContent = best ? `${(best.confidence * 100).toFixed(0)}%` : "0%";
  }
}
