import test from "node:test";
import assert from "node:assert/strict";
import { planPortfolio, DEFAULT_POLICY } from "../web/portfolio.js";

const pick = (id, extra = {}) => ({ id, sport: "football", home: `Home ${id}`, away: `Away ${id}`,
  date: "2026-11-19", country: "Portugal", competition: "Primeira Liga", odds: 2, ...extra });

test("defaults stay paper-only and allocate fixed units in passed rank order", () => {
  assert.equal(Object.isFrozen(DEFAULT_POLICY), true);
  const output = planPortfolio([pick("low", { score: 20 }), pick("high", { score: 99 })]);
  assert.deepEqual(output.allocations.map(p => [p.id, p.stake, p.pct]), [["low", 5, 0.5], ["high", 5, 0.5]]);
  assert.equal(output.cap, 20);
  assert.equal(output.totalStake, 10);
  assert.equal(output.paperOnly, true);
  assert.equal(output.leverage, false);
  assert.ok(output.warnings.some(message => message.includes("concentram-se")));
});

test("a group cap trims the last stake and blocks further same-group exposure", () => {
  const output = planPortfolio([pick("a"), pick("b"), pick("c")], { maxCountryPct: 0.7 });
  assert.deepEqual(output.allocations.map(p => p.stake), [5, 2]);
  assert.equal(output.totalStake, 7);
  assert.match(output.skipped[0].reason, /país/);
});

test("day cap applies across otherwise distinct groups with no leverage", () => {
  const candidates = Array.from({ length: 10 }, (_, i) => pick(`p${i}`, {
    sport: `sport${i}`, country: `country${i}`, competition: `league${i}`,
  }));
  const output = planPortfolio(candidates);
  assert.equal(output.totalStake, 20);
  assert.equal(output.allocations.length, 4);
  assert.equal(output.skipped.length, 6);
  assert.ok(output.warnings.some(x => /limite diário/.test(x)));
});

test("same event with a new id, punctuation or swapped participants creates no second position", () => {
  const a = pick("a", { home: "São Paulo", away: "Benfica" });
  const b = pick("b", { home: "SAO-PAULO", away: "Benfica" });
  const c = pick("c", { home: "Benfica", away: "São Paulo" });
  const output = planPortfolio([a, b, c], { maxCountryPct: 10, maxSportPct: 10, maxCompetitionPct: 10 });
  assert.equal(output.allocations.length, 1);
  assert.equal(output.skipped.length, 2);
  assert.ok(output.skipped.every(p => /já tem uma posição/.test(p.reason)));
});

test("unidentified countries and competitions share buckets", () => {
  const output = planPortfolio([
    pick("a", { country: undefined, competition: undefined }),
    pick("b", { country: "Desconhecido", competition: "" }),
    pick("c", { country: "unknown", competition: null }),
  ], { maxCountryPct: 0.7, maxCompetitionPct: 0.6 });
  assert.deepEqual(output.allocations.map(p => p.stake), [5, 1]);
  assert.equal(output.totalStake, 6);
  assert.ok(output.warnings.some(x => /partilham limites comuns/.test(x)));
});

test("existing exposure reduces both group and daily available room", () => {
  const output = planPortfolio([pick("a"), pick("b", { sport: "tennis", country: "Spain", competition: "ATP" })], {}, {
    day: 18, sport: { FOOTBALL: 9 }, country: { Portugal: 9 }, competition: { "Primeira Liga": 9 },
  });
  assert.deepEqual(output.allocations.map(p => p.stake), [1, 1]);
  assert.equal(output.totalStake, 2);
});

test("omitted daily exposure is conservatively derived from group totals", () => {
  const output = planPortfolio([pick("a", { sport: "tennis", country: "Spain", competition: "ATP" })], {}, {
    sport: { football: 10, hockey: 9 },
  });
  assert.deepEqual(output.allocations.map(p => p.stake), [1]);
});

test("missing and nonnumeric odds never acquire a simulated stake", () => {
  const values = [undefined, null, true, false, NaN, Infinity, -Infinity, "2.00", 0, 1, 21];
  const output = planPortfolio(values.map((odds, i) => pick(String(i), { odds })));
  assert.equal(output.allocations.length, 0);
  assert.equal(output.skipped.length, values.length);
  assert.equal(output.totalStake, 0);
});

test("zero, negative, boolean and nonfinite bankrolls are disabled", () => {
  for (const bankroll of [0, -1, true, NaN, Infinity, 1e308, "1000"]) {
    const output = planPortfolio([pick("a")], { bankroll });
    assert.equal(output.allocations.length, 0, `bankroll=${bankroll}`);
    assert.equal(output.totalStake, 0);
    assert.ok(output.warnings.length);
  }
});

test("invalid risk percentages and exposure fail closed", () => {
  for (const field of ["perPickPct", "maxDayPct", "maxSportPct", "maxCountryPct", "maxCompetitionPct"]) {
    for (const value of [true, NaN, Infinity, -1, 101])
      assert.equal(planPortfolio([pick("a")], { [field]: value }).allocations.length, 0);
  }
  for (const exposure of [{ day: true }, { day: 1e308 }, { sport: { football: NaN } }, { country: { Spain: -1 } }, { competition: [] }])
    assert.equal(planPortfolio([pick("a")], {}, exposure).allocations.length, 0);
});

test("rounding is downward for new stakes and upward for booked exposure", () => {
  const output = planPortfolio([pick("a")], { bankroll: 123.45, perPickPct: 1, maxDayPct: 1.7,
    maxSportPct: 2, maxCountryPct: 2, maxCompetitionPct: 2 }, { day: 1.001 });
  assert.equal(output.cap, 2.09);
  assert.equal(output.totalStake, 1.08);
  assert.ok(output.totalStake + 1.001 <= 123.45 * 0.017);
  assert.equal(planPortfolio([pick("a")], { bankroll: 1, perPickPct: 0.5 }).allocations.length, 0);
});

test("a valid Lisbon date can be derived from a zoned kickoff", () => {
  const output = planPortfolio([pick("a", { date: undefined, kickoff: "2026-07-01T23:30:00Z" }),
    pick("b", { date: "2026-07-02", kickoff: "2026-07-02T20:00:00+01:00" })]);
  assert.equal(output.allocations.length, 2);
});

test("mixed days, invalid dates, unzoned kickoff and missing identity are rejected", () => {
  const output = planPortfolio([pick("valid"), pick("tomorrow", { date: "2026-11-20" }),
    pick("invalid", { date: "2026-02-30" }), pick("untimed", { kickoff: "2026-11-19T20:00:00" }),
    pick("missing", { home: "" }), pick("conflict", { date: "2026-11-19", kickoff: "2026-11-20T20:00:00Z" })]);
  assert.equal(output.allocations.length, 1);
  assert.equal(output.skipped.length, 5);
});
