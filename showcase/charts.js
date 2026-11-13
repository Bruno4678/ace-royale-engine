// Chart.js defaults and small helpers shared by every chart on the page.

const PALETTE = {
  green: "#1f6f4a",
  greenLight: "#4cc38a",
  gold: "#b8860b",
  grey: "#8a8a8a",
  blue: "#3b6fb6",
  ink: "#1b1b1b",
  grid: "rgba(0,0,0,0.08)",
};

if (window.Chart) {
  Chart.defaults.font.family = "Inter, system-ui, sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.color = "#333";
  Chart.defaults.maintainAspectRatio = false;
  Chart.defaults.animation.duration = 300;
}

const pct = (x, digits = 2) => `${(100 * x).toFixed(digits)}%`;
const signedPct = (x, digits = 2) => `${x > 0 ? "+" : ""}${pct(x, digits)}`;
const fmtInt = (x) => Math.round(x).toLocaleString("en-US");

function axis(title, extra = {}) {
  return { title: { display: true, text: title }, grid: { color: PALETTE.grid }, ...extra };
}

// Replaces whatever chart lives on `canvas` with a new one.
function drawChart(canvas, config) {
  const old = Chart.getChart(canvas);
  if (old) old.destroy();
  return new Chart(canvas, config);
}
