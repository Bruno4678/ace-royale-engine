// Chart.js defaults and small helpers shared by every chart on the page.

const PALETTE = {
  green: "#4cc38a",
  gold: "#d9b26a",
  grey: "#8a9a92",
  blue: "#6ea8fe",
  red: "#d2524a",
  text: "#f4f1ea",
  muted: "#9aa8a0",
  grid: "rgba(255, 255, 255, 0.06)",
};

if (window.Chart) {
  Chart.defaults.font.family = "Inter, system-ui, sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.color = PALETTE.muted;
  Chart.defaults.borderColor = PALETTE.grid;
  Chart.defaults.maintainAspectRatio = false;
  Chart.defaults.animation.duration = 400;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxHeight = 7;
  Chart.defaults.plugins.legend.labels.padding = 16;
  Object.assign(Chart.defaults.plugins.tooltip, {
    backgroundColor: "#0d1310", borderColor: "rgba(217, 178, 106, 0.35)", borderWidth: 1,
    titleColor: PALETTE.text, bodyColor: PALETTE.text, padding: 10, cornerRadius: 10,
  });
}

const pct = (x, digits = 2) => `${(100 * x).toFixed(digits)}%`;
const signedPct = (x, digits = 2) => `${x > 0 ? "+" : ""}${pct(x, digits)}`;
const fmtInt = (x) => Math.round(x).toLocaleString("en-US");

function axis(title, extra = {}) {
  return { title: { display: !!title, text: title, color: PALETTE.muted }, grid: { color: PALETTE.grid },
    border: { display: false }, ...extra };
}

// Replaces whatever chart lives on `canvas` with a new one.
function drawChart(canvas, config) {
  const old = Chart.getChart(canvas);
  if (old) old.destroy();
  return new Chart(canvas, config);
}
