/** Upload Image controller: detect + show annotated result. */
import { api } from "./api.js";
import { toast } from "./toast.js";

export class ImageMode {
  constructor() { this._wire(); }

  _wire() {
    const drop = document.getElementById("imageDrop");
    const input = document.getElementById("imageInput");
    drop.addEventListener("click", () => input.click());
    ["dragover", "dragenter"].forEach((e) => drop.addEventListener(e, (ev) => { ev.preventDefault(); drop.classList.add("drag"); }));
    ["dragleave", "drop"].forEach((e) => drop.addEventListener(e, () => drop.classList.remove("drag")));
    drop.addEventListener("drop", (ev) => { ev.preventDefault(); if (ev.dataTransfer.files[0]) this._handle(ev.dataTransfer.files[0]); });
    input.addEventListener("change", () => { if (input.files[0]) this._handle(input.files[0]); });
  }

  async _handle(file) {
    try {
      toast.info("Analyzing image…");
      const result = await api.detectImage(file);
      this._render(result);
      toast.ok("Image analyzed");
    } catch (err) { toast.err("Image analysis failed"); }
  }

  _render(result) {
    document.getElementById("imageStage").hidden = false;
    document.getElementById("imageControls").hidden = false;
    const url = `/api/download/output/${result.download_name}`;
    document.getElementById("imageResult").src = url + `?t=${Date.now()}`;
    document.getElementById("downloadImage").href = url;
    document.getElementById("imageLetter").textContent = result.letter || "—";
    const pct = (result.confidence * 100).toFixed(1);
    document.getElementById("imageConfFill").style.width = `${pct}%`;
    document.getElementById("imageConfLabel").textContent = `${pct}%`;
    document.getElementById("imageLatency").textContent = `${result.latency_ms} ms`;
    document.getElementById("imageDevice").textContent = result.device.toUpperCase();
  }
}
