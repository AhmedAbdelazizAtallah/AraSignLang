/** Arabic Text-to-Speech via Web Speech API. */
const synth = window.speechSynthesis;
let currentVoice = null;
let rate = 1;

export const speech = {
  populateVoices(selectEl) {
    if (!synth) return;
    const load = () => {
      const voices = synth.getVoices();
      selectEl.innerHTML = "";
      voices.forEach((v, i) => {
        const opt = document.createElement("option");
        opt.value = i; opt.textContent = `${v.name} (${v.lang})`;
        selectEl.appendChild(opt);
      });
      const arIdx = voices.findIndex((v) => v.lang.startsWith("ar"));
      if (arIdx >= 0) { selectEl.value = arIdx; currentVoice = voices[arIdx]; }
      else if (voices.length) currentVoice = voices[0];
    };
    load();
    synth.onvoiceschanged = load;
    selectEl.addEventListener("change", () => {
      currentVoice = synth.getVoices()[Number(selectEl.value)] || null;
    });
  },
  setRate(r) { rate = Number(r) || 1; },
  play(text) {
    if (!synth || !text.trim()) return;
    synth.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = currentVoice?.lang || "ar-SA";
    u.voice = currentVoice || null;
    u.rate = rate;
    synth.speak(u);
  },
  pause() { if (synth?.speaking) synth.pause(); },
  resume() { if (synth?.paused) synth.resume(); },
  stop() { synth?.cancel(); },
};
