/**
 * Upload Video controller.
 *
 * Uploads the file (returns a job_id immediately), then polls the job for
 * progress until it's done, and finally renders the processed video, timeline
 * and generated text. This avoids the request "hanging" while a long video is
 * analysed on CPU.
 */
import { api } from "./api.js";
import { toast } from "./toast.js";

export class VideoMode {
  constructor() {
    this.player = document.getElementById("videoPlayer");
    this.jobId = null;
    this.fps = 25;
    this._poll = null;
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
      if (ev.dataTransfer.files[0]) this._handle(ev.dataTransfer.files[0]);
    });
    input.addEventListener("change", () => { if (input.files[0]) this._handle(input.files[0]); });

    document.querySelector('[data-vid="replay"]').addEventListener("click", () => {
      this.player.currentTime = 0; this.player.play();
    });
    document.getElementById("exportVideoText").addEventListener("click", () => {
      const text = document.getElementById("videoText").textContent;
      const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = "video_text.txt"; a.click();
    });
  }

  async _handle(file) {
    document.getElementById("videoDrop").hidden = true;
    const wrap = document.getElementById("videoProgressWrap");
    wrap.hidden = false;
    this._setProgress(0, "Uploading…");

    try {
      // 1) Upload → get a job id immediately.
      const { job_id } = await api.detectVideo(file);
      this.jobId = job_id;
      this._setProgress(0.02, "Analyzing… 0%");

      // 2) Poll the job until it finishes (or errors).
      this._poll = setInterval(async () => {
        try {
          const job = await api.videoProgress(this.jobId);
          if (job.status === "processing" || job.status === "queued") {
            this._setProgress(Math.max(0.02, job.progress), `Analyzing… ${(job.progress * 100) | 0}%`);
          } else if (job.status === "done") {
            clearInterval(this._poll);
            this._setProgress(1, "Done");
            setTimeout(() => (wrap.hidden = true), 700);
            this._render(job.result);
            toast.ok("Video analyzed");
          } else if (job.status === "error") {
            clearInterval(this._poll);
            wrap.hidden = true;
            document.getElementById("videoDrop").hidden = false;
            toast.err("Video analysis failed");
          }
        } catch (_) {
          clearInterval(this._poll);
          wrap.hidden = true;
          document.getElementById("videoDrop").hidden = false;
          toast.err("Lost connection to job");
        }
      }, 800);
    } catch (err) {
      wrap.hidden = true;
      document.getElementById("videoDrop").hidden = false;
      toast.err("Upload failed (is the model loaded?)");
    }
  }

  _setProgress(p, text) {
    document.getElementById("videoProgress").style.width = `${p * 100}%`;
    document.getElementById("videoProgressText").textContent = text;
  }

  _render(result) {
    this.fps = result.fps || 25;
    document.getElementById("videoStage").hidden = false;
    document.getElementById("videoControls").hidden = false;
    this.player.src = result.output_url;
    this.player.load();
    document.getElementById("downloadVideo").href = result.output_url;
    document.getElementById("videoText").textContent = result.generated_text || "—";

    const tl = document.getElementById("timeline");
    tl.innerHTML = "";
    (result.timeline || []).forEach((t) => {
      const item = document.createElement("div");
      item.className = "tl-item";
      item.innerHTML = `<span class="g">${t.glyph}</span><small>${t.timestamp_s.toFixed(1)}s</small><small>${(t.confidence * 100).toFixed(0)}%</small>`;
      item.addEventListener("click", () => { this.player.currentTime = t.timestamp_s; this.player.play(); });
      tl.appendChild(item);
    });
    if (!result.timeline?.length) tl.innerHTML = '<p class="muted">No letters detected.</p>';
  }
}
