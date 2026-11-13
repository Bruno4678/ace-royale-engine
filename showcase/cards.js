// Cards use the engine's encoding: an int XYY, X = suit (1 spades, 2 clubs,
// 3 hearts, 4 diamonds), YY = rank (1 = ace ... 13 = king). 101 is the ace of spades.

const SUIT_SYMBOL = { 1: "♠", 2: "♣", 3: "♥", 4: "♦" };
const RANK_LABEL = { 1: "A", 10: "10", 11: "J", 12: "Q", 13: "K" };

function cardSuit(card) { return Math.floor(card / 100); }
function cardRank(card) { return card % 100; }
function rankLabel(card) { return RANK_LABEL[cardRank(card)] || String(cardRank(card)); }

function cardLabel(card) {
  return rankLabel(card) + SUIT_SYMBOL[cardSuit(card)];
}

// A card element. `card` null draws an empty slot, "back" a face-down card.
function cardEl(card, extra = "") {
  const el = document.createElement("div");
  el.className = ("pcard " + extra).trim();
  if (card === null || card === undefined) {
    el.classList.add("empty");
  } else if (card === "back") {
    el.classList.add("back");
  } else {
    const s = cardSuit(card);
    if (s === 3 || s === 4) el.classList.add("red");
    el.innerHTML = `<span class="corner">${rankLabel(card)}<small>${SUIT_SYMBOL[s]}</small></span>` +
                   `<span class="pip">${SUIT_SYMBOL[s]}</span>`;
    el.dataset.card = card;
    el.title = cardLabel(card);
  }
  return el;
}

// Display order: ace high, suits in the usual spades-hearts-diamonds-clubs order.
function deckInDisplayOrder() {
  const ranks = [1, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2];
  const cards = [];
  for (const s of [1, 3, 4, 2]) for (const r of ranks) cards.push(s * 100 + r);
  return cards;
}
