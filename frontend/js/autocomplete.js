/**
 * Auto-complete + Arabic Text-to-Speech module.
 *
 * WHAT IT DOES
 *   1) As accepted letters build up the current word, it asks the backend for
 *      Arabic word suggestions and shows them as clickable chips. Clicking a
 *      chip completes the current word instantly.
 *   2) Speaks any Arabic text aloud using the browser's built-in Web Speech API
 *      (free, no key). Auto-speaks a word when it is completed (toggle-able).
 *
 * HOW TO USE (from camera.js / video.js when a letter is accepted):
 *      import { autocomplete } from "./autocomplete.js";
 *      autocomplete.pushLetter(glyph);      // on each accepted letter
 *      autocomplete.commitWord();           // on a "space" / word-break
 *      autocomplete.getText();              // current full text
 *
 * The module renders itself into #autocompleteBar and #ttsBar containers if they
 * exist; otherwise call autocomplete.mount(parentEl) once to inject the UI.
 */

class AutoComplete {
  constructor() {
    this.currentWord = "";      // letters of the word being built
    this.text = "";             // full committed text (words joined by spaces)
    this.autoSpeak = true;      // speak a word once completed
    this.voice = null;          // preferred Arabic voice
    this.rate = 1.0;
    this._debounce = null;
    this._els = {};
    this._initVoices();
  }

  // ------------------------------------------------------------------ UI setup
  mount(parent) {
    if (document.getElementById("acWrap")) return; // already mounted
    const wrap = document.createElement("div");
    wrap.id = "acWrap";
    wrap.className = "ac-wrap glass";
    wrap.innerHTML = `
      <div class="ac-row">
        <span class="ac-label"><i class="fa-solid fa-wand-magic-sparkles"></i> اقتراحات</span>
        <div id="acChips" class="ac-chips"></div>
      </div>
      <div class="ac-row ac-controls">
        <div class="ac-text" id="acText" dir="rtl">—</div>
        <div class="ac-btns">
          <button id="acSpeak" class="ac-btn" title="نطق النص"><i class="fa-solid fa-volume-high"></i></button>
          <button id="acSpace" class="ac-btn" title="مسافة"><i class="fa-solid fa-arrows-left-right-to-line"></i></button>
          <button id="acBack"  class="ac-btn" title="حذف حرف"><i class="fa-solid fa-delete-left"></i></button>
          <button id="acClear" class="ac-btn" title="مسح الكل"><i class="fa-solid fa-trash"></i></button>
          <label class="ac-toggle" title="نطق تلقائي عند اكتمال الكلمة">
            <input type="checkbox" id="acAuto" checked/> تلقائي
          </label>
        </div>
      </div>`;
    (parent || document.body).appendChild(wrap);

    this._els.chips = wrap.querySelector("#acChips");
    this._els.text = wrap.querySelector("#acText");
    wrap.querySelector("#acSpeak").onclick = () => this.speak(this.getText());
    wrap.querySelector("#acSpace").onclick = () => this.commitWord();
    wrap.querySelector("#acBack").onclick = () => this.backspace();
    wrap.querySelector("#acClear").onclick = () => this.clear();
    wrap.querySelector("#acAuto").onchange = (e) => (this.autoSpeak = e.target.checked);

    this._renderText();
    this._refreshSuggestions();
  }

  // ------------------------------------------------------------- letter input
  /** Add one accepted letter (glyph) to the current word. */
  pushLetter(glyph) {
    if (!glyph) return;
    this.currentWord += glyph;
    this._renderText();
    this._refreshSuggestions();
  }

  /** Finish the current word (like pressing space) and optionally speak it. */
  commitWord() {
    const word = this.currentWord.trim();
    if (word) {
      this.text = (this.text ? this.text + " " : "") + word;
      if (this.autoSpeak) this.speak(word);
    }
    this.currentWord = "";
    this._renderText();
    this._refreshSuggestions();
  }

  /** Choose a full suggestion for the current word. */
  chooseSuggestion(word) {
    this.currentWord = word;
    this.commitWord();       // commit + (auto) speak the chosen word
  }

  backspace() {
    if (this.currentWord) this.currentWord = this.currentWord.slice(0, -1);
    else if (this.text) this.text = this.text.replace(/\s?\S+\s*$/, "");
    this._renderText();
    this._refreshSuggestions();
  }

  clear() {
    this.currentWord = "";
    this.text = "";
    this._renderText();
    this._refreshSuggestions();
  }

  getText() {
    return (this.text + (this.currentWord ? " " + this.currentWord : "")).trim();
  }

  // ------------------------------------------------------------- suggestions
  _refreshSuggestions() {
    clearTimeout(this._debounce);
    this._debounce = setTimeout(async () => {
      try {
        const q = encodeURIComponent(this.currentWord);
        const res = await fetch(`/api/suggest?prefix=${q}&limit=6`);
        const data = await res.json();
        this._renderChips(data.suggestions || []);
      } catch (_) {
        this._renderChips([]);
      }
    }, 120);
  }

  _renderChips(list) {
    if (!this._els.chips) return;
    this._els.chips.innerHTML = "";
    list.forEach((w) => {
      const chip = document.createElement("button");
      chip.className = "ac-chip";
      chip.textContent = w;
      chip.onclick = () => this.chooseSuggestion(w);
      this._els.chips.appendChild(chip);
    });
    if (!list.length) {
      const hint = document.createElement("span");
      hint.className = "ac-empty";
      hint.textContent = "أشر بالحروف لتظهر الاقتراحات…";
      this._els.chips.appendChild(hint);
    }
  }

  _renderText() {
    if (!this._els.text) return;
    const t = this.getText();
    this._els.text.textContent = t || "—";
  }

  // --------------------------------------------------------------- speech (TTS)
  _initVoices() {
    if (!("speechSynthesis" in window)) return;
    const pick = () => {
      const voices = speechSynthesis.getVoices();
      // Prefer an Arabic voice; fall back to the first available.
      this.voice =
        voices.find((v) => /ar(-|_)/i.test(v.lang) || /arabic/i.test(v.name)) ||
        voices[0] ||
        null;
    };
    pick();
    speechSynthesis.onvoiceschanged = pick;
  }

  /** Speak Arabic text aloud. */
  speak(text) {
    if (!text || !("speechSynthesis" in window)) return;
    speechSynthesis.cancel(); // stop any current utterance
    const u = new SpeechSynthesisUtterance(text);
    u.lang = (this.voice && this.voice.lang) || "ar-SA";
    if (this.voice) u.voice = this.voice;
    u.rate = this.rate;
    u.pitch = 1.0;
    speechSynthesis.speak(u);
  }

  setRate(r) {
    this.rate = Math.max(0.5, Math.min(2, Number(r) || 1));
  }
}

export const autocomplete = new AutoComplete();
