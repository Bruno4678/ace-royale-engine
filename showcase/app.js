// Ace Royale Engine showcase. Loads the engine into Pyodide and wires up the
// four sections. Charts that only read simulation results draw right away;
// anything that needs the engine waits for it.

const $ = (id) => document.getElementById(id);
const tick = () => new Promise((resolve) => setTimeout(resolve, 30));

let RESULTS = null;
let bridge = null;          // the Python module, once Pyodide has loaded it

// ------------------------------------------------------------------ chrome

function setupChrome() {
  const nav = $("nav");
  const onScroll = () => nav.classList.toggle("scrolled", window.scrollY > 8);
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // Fade sections in as they scroll into view.
  const reveal = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (e.isIntersecting) { e.target.classList.add("in"); reveal.unobserve(e.target); }
    }
  }, { rootMargin: "0px 0px -8% 0px" });
  document.querySelectorAll(".reveal").forEach((el) => reveal.observe(el));

  // Highlight the nav link of the section on screen.
  const links = [...document.querySelectorAll(".links a")];
  const spy = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (e.isIntersecting) links.forEach((a) => a.classList.toggle("active", a.hash === "#" + e.target.id));
    }
  }, { rootMargin: "-45% 0px -50% 0px" });
  document.querySelectorAll("section[id]").forEach((el) => spy.observe(el));

  // A royal flush fanned out in the hero.
  const fan = $("hero-fan");
  [110, 111, 112, 113, 101].forEach((c, i) => {
    const el = cardEl(c);
    el.style.transform = `rotate(${(i - 2) * 11}deg)`;
    el.style.animationDelay = `${0.1 + i * 0.08}s`;
    fan.appendChild(el);
  });
}

// --------------------------------------------------------------- engine

function setStatus(kind, text) {
  const el = $("engine-status");
  el.className = "status " + kind;
  el.querySelector(".text").textContent = text;
}

async function loadEngine() {
  try {
    const started = performance.now();
    const pyodide = await loadPyodide();
    const zip = await (await fetch("engine.zip")).arrayBuffer();
    pyodide.unpackArchive(zip, "zip");
    bridge = pyodide.pyimport("bridge");
    const version = pyodide.runPython("import sys; sys.version.split()[0]");
    const seconds = ((performance.now() - started) / 1000).toFixed(1);
    setStatus("ready", `Engine ready: Python ${version} running in your browser (loaded in ${seconds}s)`);
    document.querySelectorAll("#eq-run, #play-start").forEach((b) => (b.disabled = false));
    updateEquityButton();
    drawBaccarat();
  } catch (err) {
    console.error(err);
    setStatus("error", "Could not load the Python engine: " + err.message);
  }
}

// Calls a bridge function and parses its JSON. Python errors come back as a
// message (the last line of the traceback).
function py(name, ...args) {
  try {
    return JSON.parse(bridge[name](...args));
  } catch (err) {
    const lines = String(err.message || err).trim().split("\n");
    throw new Error(lines[lines.length - 1].replace(/^\w+Error: /, ""));
  }
}

// --------------------------------------------------------------- equity

const eq = { hand: [], board: [] };

function renderEquityPicker() {
  const used = new Set([...eq.hand, ...eq.board]);
  const slot = (row, cards, size) => {
    const box = $(row);
    box.innerHTML = "";
    for (let i = 0; i < size; i++) {
      const el = cardEl(cards[i] ?? null);
      if (cards[i] !== undefined) {
        el.title = "Click to remove";
        el.onclick = () => { cards.splice(i, 1); renderEquityPicker(); };
      }
      box.appendChild(el);
    }
  };
  slot("hand-slots", eq.hand, 2);
  slot("board-slots", eq.board, 5);

  const deck = $("deck");
  deck.innerHTML = "";
  for (const c of deckInDisplayOrder()) {
    const el = cardEl(c);
    if (used.has(c)) {
      el.classList.add("used");
    } else {
      el.onclick = () => {
        if (eq.hand.length < 2) eq.hand.push(c);
        else if (eq.board.length < 5) eq.board.push(c);
        renderEquityPicker();
      };
    }
    deck.appendChild(el);
  }
  updateEquityButton();
}

function updateEquityButton() {
  const boardOk = [0, 3, 4, 5].includes(eq.board.length);
  $("eq-run").disabled = !bridge || eq.hand.length !== 2 || !boardOk;
  if (eq.hand.length === 2 && !boardOk) {
    $("eq-detail").textContent = "The board needs 0, 3, 4 or 5 cards.";
  }
}

function randomHand() {
  const deck = deckInDisplayOrder();
  for (let i = deck.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [deck[i], deck[j]] = [deck[j], deck[i]];
  }
  eq.hand = deck.slice(0, 2);
  eq.board = [];
  renderEquityPicker();
}

async function runEquity() {
  const opponents = Number($("eq-opponents").value);
  const samples = Number($("eq-samples").value);
  $("eq-run").disabled = true;
  $("eq-value").textContent = "…";
  $("eq-detail").textContent = `Dealing ${samples.toLocaleString("en-US")} random boards…`;
  await tick();
  try {
    const started = performance.now();
    const r = py("equity", eq.hand, eq.board, opponents, samples);
    const ms = performance.now() - started;
    $("eq-value").textContent = pct(r.equity, 1);
    const board = eq.board.length ? ` on ${eq.board.map(cardLabel).join(" ")}` : "";
    $("eq-detail").innerHTML =
      `<b>${eq.hand.map(cardLabel).join(" ")}</b>${board} vs ${opponents} random hand${opponents > 1 ? "s" : ""}` +
      `<br><span class="mono">&plusmn;${pct(r.ci95, 2)} (95%) &middot; ${samples.toLocaleString("en-US")} samples &middot; ${(ms / 1000).toFixed(2)}s</span>`;
    setGauge(r.equity, 1 / (opponents + 1));

    await tick();
    drawSpread(py("level_spread", eq.hand, eq.board, opponents, 40), r.equity);
  } catch (err) {
    $("eq-value").textContent = "–";
    $("eq-detail").textContent = err.message;
  }
  updateEquityButton();
}

const RING = 2 * Math.PI * 52;   // circumference of the gauge circles

function setGauge(equity, fair) {
  $("eq-ring").style.strokeDasharray = `${equity * RING} ${RING}`;
  const mark = $("eq-fair");
  mark.style.strokeDasharray = `2.5 ${RING}`;
  mark.style.strokeDashoffset = `${-(fair * RING - 1.25)}`;
}

function drawSpread(spread, reference) {
  const keys = Object.keys(spread);
  const colours = [PALETTE.grey, PALETTE.blue, PALETTE.green, PALETTE.gold];
  const datasets = keys.map((key, i) => ({
    label: `${spread[key].name} (${spread[key].samples} samples)`,
    data: spread[key].estimates.map((y) => ({ x: i + (Math.random() - 0.5) * 0.5, y: 100 * y })),
    backgroundColor: colours[i] + "bb",
    pointRadius: 4,
    pointHoverRadius: 6,
  }));
  datasets.push({
    type: "line",
    label: "precise estimate",
    data: [{ x: -0.5, y: 100 * reference }, { x: keys.length - 0.5, y: 100 * reference }],
    borderColor: PALETTE.text,
    borderDash: [5, 4],
    borderWidth: 1.5,
    pointRadius: 0,
  });
  drawChart($("spread-chart"), {
    type: "scatter",
    data: { datasets },
    options: {
      plugins: { legend: { position: "bottom" } },
      scales: {
        x: axis("", { min: -0.6, max: keys.length - 0.4,
          ticks: { stepSize: 1, callback: (v) => (Number.isInteger(v) ? spread[keys[v]]?.name ?? "" : "") } }),
        y: axis("Estimated equity (%)"),
      },
    },
  });
}

// ----------------------------------------------------------------- play

const VERB = { fold: "folds", check: "checks", call: "calls", bet: "bets", raise: "raises to" };
const MY_VERB = { fold: "fold", check: "check", call: "call", bet: "bet", raise: "raise to" };

let shownCards = new Set();   // cards already on the table, so only new ones animate
let shownHand = null;

function renderTable(s) {
  $("table").classList.remove("hidden");
  $("table-empty").classList.add("hidden");
  $("play-start").textContent = "New match";
  const bot = s.bot_name;
  $("bot-name").textContent = bot;
  $("bot-avatar").textContent = bot[0];
  $("bot-chips").textContent = s.chips[bot];
  $("my-chips").textContent = s.chips.You;
  $("bot-button").style.visibility = s.button === bot ? "visible" : "hidden";
  $("my-button").style.visibility = s.button === "You" ? "visible" : "hidden";
  $("bot-bet").textContent = s.bets[bot] || "";
  $("my-bet").textContent = s.bets.You || "";
  // Once the hand is over the pot has been paid out: show what was won.
  $("pot").textContent = s.finished ? s.result.pots.reduce((t, p) => t + p.amount, 0) : s.pot;

  if (s.hand_number !== shownHand) { shownCards = new Set(); shownHand = s.hand_number; }
  const seen = new Set();
  const make = (c) => {
    const key = typeof c === "number" ? c : null;
    const el = cardEl(c, key !== null && !shownCards.has(key) ? "deal" : "");
    if (key !== null) seen.add(key);
    return el;
  };
  const fill = (id, cards) => {
    const box = $(id);
    box.innerHTML = "";
    cards.forEach((c) => box.appendChild(make(c)));
  };
  fill("bot-cards", s.bot_cards || ["back", "back"]);
  fill("my-cards", s.my_cards);
  const board = $("play-board");
  board.innerHTML = "";
  for (let i = 0; i < 5; i++) board.appendChild(make(s.board[i] ?? null));
  shownCards = new Set([...shownCards, ...seen]);

  $("outcome").textContent = s.finished ? outcomeText(s) : "";
  renderActions(s);
  renderLog(s);
}

function outcomeText(s) {
  const r = s.result;
  if (!r.showdown) {
    const loser = r.winners[0] === "You" ? s.bot_name : "You";
    return `${r.winners[0] === "You" ? "You win" : r.winners[0] + " wins"} ${r.pots[0].amount} (${loser === "You" ? "you" : loser} folded)`;
  }
  return r.pots.map((p) => {
    const who = p.winners.length > 1 ? "Split pot" : (p.winners[0] === "You" ? "You win" : `${p.winners[0]} wins`);
    return `${who} ${p.amount} with ${p.hand}`;
  }).join(" · ");
}

function renderActions(s) {
  const box = $("actions");
  box.innerHTML = "";
  const button = (label, cls, onclick) => {
    const b = document.createElement("button");
    b.className = cls;
    b.textContent = label;
    b.onclick = onclick;
    box.appendChild(b);
    return b;
  };
  if (s.finished) {
    button("Next hand", "btn btn-gold", () => playStep("match_next_hand"));
    return;
  }
  if (!s.my_turn) return;
  const a = s.actions;
  if (a.fold && !a.check) button("Fold", "btn btn-ghost btn-sm", () => playStep("match_act", "fold", 0));
  if (a.check) button("Check", "btn btn-ghost btn-sm", () => playStep("match_act", "check", 0));
  if (a.call) button(`Call ${a.call.amount}`, "btn btn-ghost btn-sm", () => playStep("match_act", "call", 0));

  const kind = a.raise ? "raise" : (a.bet ? "bet" : null);
  if (!kind) return;
  const { min, max } = a[kind];
  const toCall = a.call ? a.call.amount : 0;
  const potAfterCall = s.pot + toCall;
  const clamp = (x) => Math.max(min, Math.min(max, Math.round(x)));

  const wrap = document.createElement("div");
  wrap.className = "raise";
  const input = document.createElement("input");
  input.type = "number";
  input.min = min; input.max = max;
  input.value = clamp(s.bets.You + toCall + 0.5 * potAfterCall);
  const presets = [["½ pot", 0.5], ["Pot", 1]];
  presets.forEach(([label, f]) => {
    const b = document.createElement("button");
    b.className = "btn btn-ghost btn-sm";
    b.textContent = label;
    b.onclick = () => (input.value = clamp(s.bets.You + toCall + f * potAfterCall));
    wrap.appendChild(b);
  });
  const allIn = document.createElement("button");
  allIn.className = "btn btn-ghost btn-sm";
  allIn.textContent = "All-in";
  allIn.onclick = () => (input.value = max);
  wrap.appendChild(allIn);
  wrap.appendChild(input);
  const go = document.createElement("button");
  go.className = "btn btn-gold btn-sm";
  go.textContent = kind === "raise" ? "Raise to" : "Bet";
  go.onclick = () => playStep("match_act", kind, clamp(Number(input.value)));
  wrap.appendChild(go);
  box.appendChild(wrap);
}

function renderLog(s) {
  const ol = $("log");
  ol.innerHTML = "";
  for (const e of s.log) {
    const li = document.createElement("li");
    if (e.event === "deal") {
      li.className = "head";
      li.innerHTML = `Hand #${e.hand} <span class="street">${e.button === "You" ? "you deal" : e.button + " deals"}</span>` +
        (e.reset ? `<br><span class="street">someone went broke: stacks back to 1,000</span>` : "");
    } else {
      const amount = ["bet", "raise"].includes(e.action) ? ` ${e.amount}` : "";
      // The bot's equity would give its hand away, so it shows once the hand is over.
      const thinks = s.finished && e.equity != null ? `<span class="eq" title="equity the bot estimated">${pct(e.equity, 0)}</span>` : "";
      const verb = (e.who === "You" ? MY_VERB : VERB)[e.action] || e.action;
      li.innerHTML = `${thinks}<b>${e.who}</b> ${verb}${amount}<span class="street">${e.street}</span>`;
    }
    ol.appendChild(li);
  }
  if (s.finished) {
    const li = document.createElement("li");
    li.className = "end";
    const hands = Object.entries(s.result.hands).map(([who, text]) => `${who}: ${text}`).join("<br>");
    li.innerHTML = `${outcomeText(s)}${hands ? `<br><span class="street">${hands}</span>` : ""}`;
    ol.appendChild(li);
  }
  ol.scrollTop = ol.scrollHeight;
}

async function playStep(name, ...args) {
  $("actions").querySelectorAll("button").forEach((b) => (b.disabled = true));
  await tick();
  try {
    renderTable(py(name, ...args));
  } catch (err) {
    $("outcome").textContent = err.message;
    $("actions").querySelectorAll("button").forEach((b) => (b.disabled = false));
  }
}

// ----------------------------------------------------------- house edge

function renderEdgeTable() {
  const bj = RESULTS.blackjack_shoe, bac = RESULTS.baccarat, tc = RESULTS.three_card;
  const rows = [
    ["Blackjack", "Basic strategy", bj.return, `&plusmn;${pct(bj.ci95)}`, "6 decks, S17, DAS, 3:2 \u00b7 10M rounds"],
    ["Baccarat", "Banker", bac.return_per_chip.banker, "", "Exact, 8-deck shoe, multiples of 20"],
    ["Baccarat", "Player", bac.return_per_chip.player, "", "Exact enumeration"],
    ["Baccarat", "Tie (8:1)", bac.return_per_chip.tie, "", "Exact enumeration"],
    ["Three Card Poker", "Ante / Play", tc.ante_play_ev_per_ante, "", "Optimal play: Q-6-4 or better \u00b7 exact"],
    ["Three Card Poker", "Pair Plus", tc.pair_plus_ev, "", "1-4-6-30-40 paytable \u00b7 exact"],
  ];
  // Meter on a square-root scale, so -0.4% and -14% both stay readable.
  const worst = Math.sqrt(Math.max(...rows.map((r) => -r[2])));
  $("edge-table").innerHTML = rows.map(([game, bet, edge, extra, how]) =>
    `<div class="edge-card"><span class="game">${game}</span><span class="bet">${bet}</span>` +
    `<span class="val">${pct(edge)} <small>${extra}</small></span>` +
    `<span class="meter"><i style="width:${(100 * Math.sqrt(-edge) / worst).toFixed(1)}%"></i></span>` +
    `<span class="src">${how}</span></div>`
  ).join("");
}

let baccaratRows = null;

function drawBaccarat() {
  const p = RESULTS.baccarat.probabilities;
  baccaratRows = py("banker_returns", p.banker, p.player, 200);
  drawChart($("baccarat-chart"), {
    type: "line",
    data: {
      labels: baccaratRows.map((r) => r.bet),
      datasets: [
        { label: "rounded down (old rule)", data: baccaratRows.map((r) => 100 * r.down), borderColor: PALETTE.gold, pointRadius: 0, borderWidth: 2 },
        { label: "rounded up (engine)", data: baccaratRows.map((r) => 100 * r.up), borderColor: PALETTE.green, pointRadius: 0, borderWidth: 2 },
        { label: "your bet", data: [], showLine: false, pointRadius: 7, pointBackgroundColor: PALETTE.text, borderColor: PALETTE.green, borderWidth: 3 },
      ],
    },
    options: {
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "bottom" },
        tooltip: { callbacks: { title: (items) => `Banker bet of ${items[0].label} chips`,
          label: (item) => `${item.dataset.label}: ${item.parsed.y.toFixed(2)}%` } },
      },
      scales: {
        x: axis("Banker bet (chips)", { ticks: { maxTicksLimit: 12 } }),
        y: axis("Player return per chip (%)", { suggestedMin: -8, suggestedMax: 2 }),
      },
    },
  });
  updateBaccaratSlider();
}

function updateBaccaratSlider() {
  const bet = Number($("bac-bet").value);
  $("bac-bet-value").textContent = bet;
  if (!baccaratRows) return;
  const r = baccaratRows[bet - 5];
  const show = (id, x) => {
    $(id).textContent = signedPct(x);
    $(id).className = x > 0 ? "pos" : "neg";
  };
  show("bac-old", r.down);
  show("bac-new", r.up);
  const chart = Chart.getChart($("baccarat-chart"));
  if (chart) {
    const i = bet - 5;
    chart.data.datasets[2].data = baccaratRows.map((row, j) => (j === i ? 100 * row.up : null));
    chart.update("none");
  }
}

const STRATEGY_COLUMNS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "A"];
const ACTION_NAMES = { H: "Hit", S: "Stand", D: "Double (else hit)", Ds: "Double (else stand)", P: "Split" };

function renderStrategy(kind) {
  const s = RESULTS.blackjack_strategy;
  const table = s[kind];
  const keys = Object.keys(table).sort((a, b) => Number(a) - Number(b));
  const label = (k) => {
    if (kind === "hard") return k;
    if (kind === "soft") return `A,${k}`;
    const c = k === "1" ? "A" : k === "10" ? "T" : k;
    return `${c},${c}`;
  };
  let html = "<table><tr><th></th>" + STRATEGY_COLUMNS.map((c) => `<th>${c}</th>`).join("") + "</tr>";
  for (const k of keys) {
    html += `<tr><th>${label(k)}</th>` + STRATEGY_COLUMNS.map((c) => {
      const a = table[k][c];
      return `<td class="a-${a}" title="${label(k)} vs ${c}: ${ACTION_NAMES[a] || a}">${a}</td>`;
    }).join("") + "</tr>";
  }
  $("strategy").innerHTML = html + "</table>";
  document.querySelectorAll("#strategy-tabs button").forEach((b) => b.classList.toggle("active", b.dataset.kind === kind));
}

function setupStrategy() {
  const tabs = $("strategy-tabs");
  for (const [kind, name] of [["hard", "Hard totals"], ["soft", "Soft totals"], ["pairs", "Pairs"]]) {
    const b = document.createElement("button");
    b.textContent = name;
    b.dataset.kind = kind;
    b.setAttribute("role", "tab");
    b.onclick = () => renderStrategy(kind);
    tabs.appendChild(b);
  }
  $("strategy-legend").innerHTML = Object.entries(ACTION_NAMES)
    .map(([a, name]) => `<span><i class="a-${a}"></i>${a} ${name}</span>`).join("");
  renderStrategy("hard");
}

// Draws the vertical 95% interval of each point of the "edge" dataset.
const errorBars = {
  id: "errorBars",
  afterDatasetsDraw(chart) {
    const { ctx, scales: { y } } = chart;
    const meta = chart.getDatasetMeta(0);
    ctx.save();
    ctx.strokeStyle = PALETTE.green;
    ctx.lineWidth = 1.5;
    meta.data.forEach((point, i) => {
      const d = chart.data.datasets[0].data[i];
      const top = y.getPixelForValue(d.hi), bottom = y.getPixelForValue(d.lo);
      ctx.beginPath();
      ctx.moveTo(point.x, top); ctx.lineTo(point.x, bottom);
      ctx.moveTo(point.x - 4, top); ctx.lineTo(point.x + 4, top);
      ctx.moveTo(point.x - 4, bottom); ctx.lineTo(point.x + 4, bottom);
      ctx.stroke();
    });
    ctx.restore();
  },
};

function drawHiLo() {
  const by = RESULTS.blackjack_shoe.by_true_count;
  const k = RESULTS.kelly;
  const points = Object.keys(by).map(Number).sort((a, b) => a - b).map((tc) => {
    const e = by[tc];
    return { x: tc, y: 100 * e.edge, lo: 100 * (e.edge - e.ci95), hi: 100 * (e.edge + e.ci95), rounds: e.rounds };
  });
  const xs = [points[0].x, points[points.length - 1].x];
  drawChart($("hilo-chart"), {
    type: "scatter",
    data: {
      datasets: [
        { label: "simulated edge (95% CI)", data: points, backgroundColor: PALETTE.green, pointRadius: 5 },
        { type: "line", label: `fit: ${(100 * k.edge_slope).toFixed(2)}% per point, break-even at ${k.breakeven_true_count.toFixed(1)}`,
          data: xs.map((x) => ({ x, y: 100 * (k.edge_intercept + k.edge_slope * x) })),
          borderColor: PALETTE.gold, borderWidth: 1.5, pointRadius: 0 },
      ],
    },
    options: {
      plugins: {
        legend: { position: "bottom" },
        tooltip: { callbacks: { label: (item) => {
          const d = item.raw;
          return d.rounds ? `true count ${d.x}: ${d.y.toFixed(2)}% (${fmtInt(d.rounds)} rounds)` : "";
        } } },
      },
      scales: { x: axis("Hi-Lo true count before the deal", { ticks: { stepSize: 1 } }), y: axis("Player edge (%)") },
    },
    plugins: [errorBars],
  });
}

// ---------------------------------------------------------------- kelly

// The simulation runs in a worker so the page stays responsive. It mirrors
// sim/kelly.py: rounds are drawn from the recorded (true count, result)
// pairs, every strategy sees the same rounds, bets are whole table minimums
// between 1 and 100, and a path is ruined below one minimum bet.
const KELLY_WORKER = `
self.onmessage = (e) => {
  const { tc, net, count, a, b, variance, strategies, rounds, paths, start } = e.data;
  const cum = new Float64Array(count.length);
  let total = 0;
  for (let i = 0; i < count.length; i++) { total += count[i]; cum[i] = total; }
  const pick = (u) => {
    let lo = 0, hi = cum.length - 1;
    const target = u * total;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (cum[mid] > target) hi = mid; else lo = mid + 1; }
    return lo;
  };
  const rng = (seed) => () => {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const CHECKS = 100;
  const every = rounds / CHECKS;
  const quantile = (sorted, q) => sorted[Math.min(sorted.length - 1, Math.floor(q * (sorted.length - 1) + 0.5))];
  const out = [];
  strategies.forEach((fraction, si) => {
    const marks = Array.from({ length: CHECKS + 1 }, () => new Float64Array(paths));
    const finals = new Float64Array(paths), ruined = new Uint8Array(paths);
    const halved = new Uint8Array(paths), avgBet = new Float64Array(paths);
    for (let p = 0; p < paths; p++) {
      const rand = rng(1000 + p * 7919);
      let bank = start, peak = start, wagered = 0, dead = false, half = false;
      marks[0][p] = bank;
      for (let r = 1; r <= rounds; r++) {
        const i = pick(rand());
        if (!dead) {
          let bet = 1;
          if (fraction > 0) {
            const edge = a + b * tc[i];
            if (edge > 0) bet = Math.min(100, Math.max(1, Math.floor(fraction * edge / variance * bank)));
          }
          bet = Math.min(bet, bank);
          bank += bet * net[i];
          wagered += bet;
          if (bank < 1) dead = true;
          if (bank > peak) peak = bank;
          if (bank <= peak / 2) half = true;
        }
        if (r % every === 0) marks[r / every][p] = bank;
      }
      finals[p] = bank; ruined[p] = dead; halved[p] = half; avgBet[p] = wagered / rounds;
    }
    const bands = marks.map((m) => { const s = Float64Array.from(m).sort(); return [quantile(s, 0.05), quantile(s, 0.5), quantile(s, 0.95)]; });
    const sf = Float64Array.from(finals).sort(), sb = Float64Array.from(avgBet).sort();
    const mean = (xs) => xs.reduce((x, y) => x + y, 0) / xs.length;
    out.push({ fraction, bands, median: quantile(sf, 0.5), p05: quantile(sf, 0.05), p95: quantile(sf, 0.95),
      ruin: mean(ruined), halved: mean(halved), bet: quantile(sb, 0.5) });
    self.postMessage({ progress: (si + 1) / strategies.length });
  });
  self.postMessage({ done: out });
};`;

let kellyWorker = null;

function runKelly() {
  const custom = Number($("kelly-fraction").value);
  const rounds = Number($("kelly-rounds").value);
  const paths = Number($("kelly-paths").value);
  const k = RESULTS.kelly, table = RESULTS.kelly_rounds;
  const strategies = [0, 0.5, 1, custom];
  const names = ["Flat (minimum bet)", "Half Kelly", "Full Kelly", `Your choice (${custom}x Kelly)`];
  const colours = [PALETTE.grey, PALETTE.green, PALETTE.gold, PALETTE.blue];

  if (kellyWorker) kellyWorker.terminate();
  kellyWorker = new Worker(URL.createObjectURL(new Blob([KELLY_WORKER], { type: "text/javascript" })));
  const button = $("kelly-run");
  button.disabled = true;
  button.textContent = "Simulating… 0%";
  kellyWorker.onmessage = (e) => {
    if (e.data.progress !== undefined) {
      button.textContent = `Simulating… ${Math.round(100 * e.data.progress)}%`;
      return;
    }
    button.disabled = false;
    button.textContent = "Simulate";
    drawKelly(e.data.done, names, colours, rounds, paths);
  };
  kellyWorker.postMessage({ tc: table.tc, net: table.net, count: table.count, a: k.edge_intercept,
    b: k.edge_slope, variance: k.variance, strategies, rounds, paths, start: k.start_bankroll });
}

function drawKelly(results, names, colours, rounds, paths) {
  const xs = results[0].bands.map((_, i) => Math.round((i * rounds) / (results[0].bands.length - 1)));
  const floor = (v) => Math.max(1, v);
  const datasets = [];
  results.forEach((r, i) => {
    datasets.push({ label: `${names[i]} 5%`, data: r.bands.map((b) => floor(b[0])), borderWidth: 0, pointRadius: 0, fill: false });
    datasets.push({ label: `${names[i]} 95%`, data: r.bands.map((b) => floor(b[2])), borderWidth: 0, pointRadius: 0,
      fill: "-1", backgroundColor: colours[i] + "16" });
    datasets.push({ label: names[i], data: r.bands.map((b) => floor(b[1])), borderColor: colours[i], borderWidth: 2.5, pointRadius: 0 });
  });
  drawChart($("kelly-chart"), {
    type: "line",
    data: { labels: xs, datasets },
    options: {
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "bottom", labels: { filter: (item) => !/ (5|95)%$/.test(item.text) } },
        tooltip: { filter: (item) => !/ (5|95)%$/.test(item.dataset.label),
          callbacks: { title: (items) => `Round ${fmtInt(items[0].label)}`,
            label: (item) => `${item.dataset.label}: median ${fmtInt(item.parsed.y)}` } },
      },
      scales: {
        x: axis("Rounds", { ticks: { maxTicksLimit: 8, callback: function (v) { return fmtInt(this.getLabelForValue(v)); } } }),
        y: axis("Bankroll (table minimums, log scale)", { type: "logarithmic", min: 1 }),
      },
    },
  });
  $("kelly-table").innerHTML = `<table><tr><th>Strategy</th><th>Median final</th><th>5% / 95%</th><th>Risk of ruin</th><th>Ever halved</th><th>Median avg bet</th></tr>` +
    results.map((r, i) => `<tr><td><span class="sw" style="background:${colours[i]}"></span>${names[i]}</td>` +
      `<td>${fmtInt(r.median)}</td><td>${fmtInt(r.p05)} / ${fmtInt(r.p95)}</td><td>${pct(r.ruin, 1)}</td>` +
      `<td>${pct(r.halved, 0)}</td><td>${r.bet.toFixed(2)}</td></tr>`).join("") +
    `</table><p class="note">${fmtInt(paths)} paths of ${fmtInt(rounds)} rounds, starting from 1,000 table minimums. Shaded: 5-95% of paths.</p>`;
}

// ---------------------------------------------------------------- start

async function main() {
  setupChrome();
  renderEquityPicker();
  $("eq-random").onclick = randomHand;
  $("eq-clear").onclick = () => { eq.hand = []; eq.board = []; renderEquityPicker(); };
  $("eq-run").onclick = runEquity;
  let level = "expert";
  document.querySelectorAll("#levels button").forEach((b) => {
    b.setAttribute("aria-checked", String(b.dataset.level === level));
    b.onclick = () => {
      level = b.dataset.level;
      document.querySelectorAll("#levels button").forEach((x) => {
        x.classList.toggle("active", x === b);
        x.setAttribute("aria-checked", String(x === b));
      });
    };
  });
  $("play-start").onclick = () => { shownHand = null; playStep("start_match", level); };
  $("bac-bet").oninput = updateBaccaratSlider;
  $("kelly-fraction").oninput = () => ($("kelly-fraction-value").textContent = `${Number($("kelly-fraction").value).toFixed(2)}\u00d7`);
  $("kelly-run").onclick = runKelly;

  RESULTS = await (await fetch("results.json")).json();
  const engine = loadEngine();
  renderEdgeTable();
  setupStrategy();
  drawHiLo();
  updateBaccaratSlider();
  runKelly();
  await engine;
}

main();
