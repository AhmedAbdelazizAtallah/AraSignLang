/**
 * Arabic Sentence Builder controller.
 * Owns the shared text buffer; provides undo/redo, space/delete/clear/copy,
 * TTS hooks, and debounced word + sentence suggestions.
 */
import { api } from "./api.js";
import { speech } from "./speech.js";
import { toast } from "./toast.js";

export class SentenceBuilder {
  constructor() {
    this.text = "";
    this.undoStack = [];
    this.redoStack = [];
    this.onChange = () => {};
    this.$buffer = document.getElementById("textBuffer");
    this.$wordSuggest = document.getElementById("wordSuggest");
    this.$sentenceSuggest = document.getElementById("sentenceSuggest");
    this._debounce = null;
    this._wire();
    this.refreshSentences();
  }

  _wire() {
    document.querySelectorAll(".builder-actions .chip").forEach((btn) =>
      btn.addEventListener("click", () => this._action(btn.dataset.act)));
    this.$buffer.addEventListener("input", () => this._commit(this.$buffer.value, false));
    document.querySelectorAll("[data-speech]").forEach((b) =>
      b.addEventListener("click", () => {
        const cmd = b.dataset.speech;
        if (cmd === "play") speech.play(this.text); else speech[cmd]?.();
      }));
    const rate = document.getElementById("speechRate");
    rate?.addEventListener("input", () => speech.setRate(rate.value));
  }

  _action(act) {
    switch (act) {
      case "space": this.append(" "); break;
      case "delete": this._commit(this.text.slice(0, -1)); break;
      case "clear": this._commit(""); break;
      case "undo": this.undo(); break;
      case "redo": this.redo(); break;
      case "copy": navigator.clipboard.writeText(this.text).then(() => toast.ok("Copied")); break;
      case "speak": speech.play(this.text); break;
    }
  }

  append(str) { this._commit(this.text + str); }

  acceptToken(name, glyph) {
    // This model outputs letters only; space/delete are handled via UI buttons.
    if (glyph) this.append(glyph);
  }

  _commit(next, pushUndo = true) {
    if (pushUndo) { this.undoStack.push(this.text); this.redoStack = []; }
    this.text = next;
    this.$buffer.value = next;
    this.onChange(next);
    this._scheduleSuggest();
  }

  undo() {
    if (!this.undoStack.length) return;
    this.redoStack.push(this.text);
    this.text = this.undoStack.pop();
    this.$buffer.value = this.text;
    this.onChange(this.text);
    this._scheduleSuggest();
  }

  redo() {
    if (!this.redoStack.length) return;
    this.undoStack.push(this.text);
    this.text = this.redoStack.pop();
    this.$buffer.value = this.text;
    this.onChange(this.text);
    this._scheduleSuggest();
  }

  currentWord() {
    const parts = this.text.split(" ");
    return parts[parts.length - 1] || "";
  }

  _scheduleSuggest() {
    clearTimeout(this._debounce);
    this._debounce = setTimeout(() => { this.refreshWords(); this.refreshSentences(); }, 220);
  }

  async refreshWords() {
    const prefix = this.currentWord();
    if (!prefix) { this.$wordSuggest.innerHTML = ""; return; }
    try {
      const { words } = await api.suggestWords(prefix);
      this._renderWords(words);
    } catch (_) {}
  }

  _renderWords(words) {
    this.$wordSuggest.innerHTML = "";
    words.forEach((w) => {
      const el = document.createElement("span");
      el.className = "sugg"; el.textContent = w;
      el.addEventListener("click", () => {
        const parts = this.text.split(" ");
        parts[parts.length - 1] = w;
        this._commit(parts.join(" ") + " ");
      });
      this.$wordSuggest.appendChild(el);
    });
  }

  async refreshSentences() {
    try {
      const { sentences } = await api.suggestSentences(this.text);
      this.$sentenceSuggest.innerHTML = "";
      sentences.forEach((s) => {
        const el = document.createElement("span");
        el.className = "sugg"; el.textContent = s;
        el.addEventListener("click", () => this._commit(s));
        this.$sentenceSuggest.appendChild(el);
      });
    } catch (_) {}
  }
}
