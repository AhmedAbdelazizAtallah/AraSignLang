/**
 * Learning Mode controller — HIGH-QUALITY capture (same fix as camera.js).
 *
 * Shows a target Arabic letter, streams the webcam to the live WebSocket at
 * (near) native resolution + high JPEG quality so the model sees a clean image,
 * evaluates the user's sign, and tracks attempts / score / completion.
 */
import { toast } from "./toast.js";

// The model's class_name IS the Arabic glyph, so targets are glyphs directly.
const LETTERS = ["ب", "ا", "ت", "ج", "د", "ر", "س", "ع", "ل", "م", "ن", "ه", "و", "ي"];

const SEND_INTERVAL_MS = 140;
const JPEG_QUALITY = 0.92;
const MAX_SEND_WIDTH = 640;

export class LearningMode {
  constructor() {
    this.idx = 0; this.attempts = 0; this.score = 0; this.completed = new Set();
    this.ws = null; this.stream = null; this.sendTimer = null; this.busy = false;
    this.video = document.getElementById("learnWebcam");
    this.overlay = document.getElementById("learnOverlay");
    this.ctx = this.overlay.getContext("2d");
    this.capture = document.createElement("canvas");
    this._wire();
    this._renderTarget();
  }

  _wire() {
    document.getElementById("startLearn").addEventListener("click", () => this.start());
    document.getElementById("nextLetter").addEventListener("click", () => this.next());
  }

  _renderTarget() { document.getElementById("targetLetter").textContent = LETTERS[this.idx]; }

  async start() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 } }, audio: false });
      this.video.srcObject = this.stream;
      await this.video.play();
      if (!this.video.videoWidth) {
        await new Promise((r) => this.video.addEventListener("loadeddata", r, { once: true }));
      }
      const vw = this.video.videoWidth || 640, vh = this.video.videoHeight || 480;
      this.overlay.width = vw; this.overlay.height = vh;
      const scale = Math.min(1, MAX_SEND_WIDTH / vw);
      this.capture.width = Math.round(vw * scale);
      this.capture.height = Math.round(vh * scale);
      this._connect();
    } catch (_) { toast.err("Camera access denied"); }
  }

  _connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    this.ws = new WebSocket(`${proto}://${location.host}/ws/live`);
    this.ws.onopen = () => { this.sendTimer = setInterval(() => this._send(), SEND_INTERVAL_MS); };
    this.ws.onmessage = (ev) => this._onMsg(JSON.parse(ev.data));
    this.ws.onclose = () => clearInterval(this.sendTimer);
  }

  _send() {
    if (this.busy || this.ws?.readyState !== WebSocket.OPEN || !this.video.videoWidth) return;
    const cctx = this.capture.getContext("2d");
    cctx.drawImage(this.video, 0, 0, this.capture.width, this.capture.height);
    this.busy = true;
    this.ws.send(JSON.stringify({ type: "frame", data: this.capture.toDataURL("image/jpeg", JPEG_QUALITY) }));
  }

  _onMsg(msg) {
    if (msg.type === "error") { toast.err(msg.message || "Model not available"); return; }
    if (msg.type !== "prediction") { return; }
    this.busy = false;
    if (!msg.best) return;
    this._drawBox(msg.best);
    const target = LETTERS[this.idx];
    document.getElementById("learnConf").textContent = `${(msg.best.confidence * 100).toFixed(0)}%`;
    if (msg.stable?.accepted) {
      this.attempts += 1;
      document.getElementById("learnAttempts").textContent = this.attempts;
      const verdict = document.getElementById("learnVerdict");
      if (msg.stable.accepted_glyph === target) {
        this.score += 10; this.completed.add(target);
        verdict.textContent = "✅ Correct!"; verdict.className = "learn-verdict ok";
        toast.ok("Correct!");
        setTimeout(() => this.next(), 900);
      } else {
        verdict.textContent = "❌ Try again"; verdict.className = "learn-verdict no";
      }
      document.getElementById("learnScore").textContent = this.score;
      this._progress();
    }
  }

  _progress() {
    const pct = Math.round((this.completed.size / LETTERS.length) * 100);
    document.getElementById("learnProgress").style.width = `${pct}%`;
    document.getElementById("learnPct").textContent = `${pct}%`;
  }

  next() {
    this.idx = (this.idx + 1) % LETTERS.length;
    this._renderTarget();
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify({ type: "reset" }));
  }

  _drawBox(best) {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.overlay.width, this.overlay.height);
    const [x1, y1, x2, y2] = best.box;
    ctx.strokeStyle = "#22d3ee"; ctx.lineWidth = 3; ctx.shadowColor = "#22d3ee"; ctx.shadowBlur = 16;
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1); ctx.shadowBlur = 0;
  }
}
