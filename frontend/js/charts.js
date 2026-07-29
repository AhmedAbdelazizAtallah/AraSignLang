/** Analytics charts built on Chart.js. */
const GRID = "rgba(140,160,255,0.10)";
const TXT = "#9aa6c7";

function baseOptions(extra = {}) {
  return {
    responsive: true, maintainAspectRatio: false, animation: { duration: 250 },
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { color: GRID }, ticks: { color: TXT, maxTicksLimit: 6 } },
      y: { grid: { color: GRID }, ticks: { color: TXT }, beginAtZero: true },
    },
    ...extra,
  };
}
function lineDataset(color) {
  return { data: [], borderColor: color, backgroundColor: color + "33", borderWidth: 2, fill: true, tension: 0.35, pointRadius: 0 };
}

export class Analytics {
  constructor() { this.MAX = 40; this.charts = {}; }
  init() {
    const C = window.Chart;
    if (!C) return;
    this.charts.conf = new C(document.getElementById("chartConf"), {
      type: "line", data: { labels: [], datasets: [lineDataset("#6d5efc")] },
      options: baseOptions({ scales: { y: { max: 1, grid: { color: GRID }, ticks: { color: TXT } }, x: { grid: { color: GRID }, ticks: { color: TXT, maxTicksLimit: 6 } } } }),
    });
    this.charts.fps = new C(document.getElementById("chartFps"), { type: "line", data: { labels: [], datasets: [lineDataset("#22d3ee")] }, options: baseOptions() });
    this.charts.latency = new C(document.getElementById("chartLatency"), { type: "line", data: { labels: [], datasets: [lineDataset("#34d399")] }, options: baseOptions() });
    this.charts.letters = new C(document.getElementById("chartLetters"), { type: "bar", data: { labels: [], datasets: [{ data: [], backgroundColor: "#a855f7" }] }, options: baseOptions() });
  }
  _push(chart, label, value) {
    if (!chart) return;
    const d = chart.data;
    d.labels.push(label); d.datasets[0].data.push(value);
    if (d.labels.length > this.MAX) { d.labels.shift(); d.datasets[0].data.shift(); }
    chart.update("none");
  }
  sample({ confidence, fps, latency, frame }) {
    const lbl = String(frame ?? "");
    if (confidence != null) this._push(this.charts.conf, lbl, confidence);
    if (fps != null) this._push(this.charts.fps, lbl, fps);
    if (latency != null) this._push(this.charts.latency, lbl, latency);
  }
  setLetters(counter) {
    const c = this.charts.letters;
    if (!c) return;
    const entries = Object.entries(counter).sort((a, b) => b[1] - a[1]).slice(0, 12);
    c.data.labels = entries.map((e) => e[0]);
    c.data.datasets[0].data = entries.map((e) => e[1]);
    c.update("none");
  }
  reset() {
    for (const k of Object.keys(this.charts)) {
      const c = this.charts[k];
      c.data.labels = []; c.data.datasets[0].data = []; c.update("none");
    }
  }
}
export const analytics = new Analytics();
