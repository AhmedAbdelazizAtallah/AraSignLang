/** Lightweight floating-particle background. Pauses when tab is hidden. */
export function initParticles() {
  const canvas = document.getElementById("particles");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  let w, h, particles, raf;
  const COLORS = ["#6d5efc", "#22d3ee", "#34d399"];
  const COUNT = Math.min(90, Math.floor(window.innerWidth / 18));

  function resize() { w = canvas.width = window.innerWidth; h = canvas.height = window.innerHeight; }
  function seed() {
    particles = Array.from({ length: COUNT }, () => ({
      x: Math.random() * w, y: Math.random() * h, r: Math.random() * 2.2 + 0.6,
      vx: (Math.random() - 0.5) * 0.35, vy: (Math.random() - 0.5) * 0.35,
      c: COLORS[(Math.random() * COLORS.length) | 0], a: Math.random() * 0.5 + 0.2,
    }));
  }
  function tick() {
    ctx.clearRect(0, 0, w, h);
    for (const p of particles) {
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0 || p.x > w) p.vx *= -1;
      if (p.y < 0 || p.y > h) p.vy *= -1;
      ctx.globalAlpha = p.a; ctx.fillStyle = p.c;
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1;
    raf = requestAnimationFrame(tick);
  }
  resize(); seed(); tick();
  window.addEventListener("resize", () => { resize(); seed(); });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) cancelAnimationFrame(raf); else tick();
  });
}
