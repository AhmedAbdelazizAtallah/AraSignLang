/** Toast notification system. */
const wrap = () => document.getElementById("toasts");

function show(message, type = "info", ms = 3200) {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  const icon = { ok: "circle-check", err: "circle-xmark", info: "circle-info" }[type];
  el.innerHTML = `<i class="fa-solid fa-${icon}"></i><span>${message}</span>`;
  wrap().appendChild(el);
  setTimeout(() => {
    el.style.opacity = "0";
    el.style.transform = "translateX(120%)";
    setTimeout(() => el.remove(), 300);
  }, ms);
}

export const toast = {
  ok: (m) => show(m, "ok"),
  err: (m) => show(m, "err"),
  info: (m) => show(m, "info"),
};
