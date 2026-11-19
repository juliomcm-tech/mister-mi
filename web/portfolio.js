/** Deterministic paper allocations. No orders, leverage, probability estimates or Kelly sizing. */
export const DEFAULT_POLICY = Object.freeze({
  bankroll: 1000,
  perPickPct: 0.5,
  maxDayPct: 2,
  maxSportPct: 1,
  maxCountryPct: 1,
  maxCompetitionPct: 1,
  minOdd: 1.01,
  maxOdd: 20,
});

const UNKNOWN = "__unknown__";
const GROUPS = [
  ["sport", "maxSportPct", "desporto"],
  ["country", "maxCountryPct", "país"],
  ["competition", "maxCompetitionPct", "competição"],
];

function plainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function finiteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function key(value) {
  if (typeof value !== "string") return UNKNOWN;
  const normalized = value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  return !normalized || ["desconhecido", "desconhecida", "unknown", "na", "n a"].includes(normalized)
    ? UNKNOWN : normalized;
}

// Exact cent accounting avoids a succession of floating-point additions exceeding a cap.
function floorCents(value) {
  return Math.max(0, Math.floor(value * 100 + 1e-8));
}

function ceilCents(value) {
  return Math.max(0, Math.ceil(value * 100 - 1e-8));
}

function validDate(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T12:00:00Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

function eventDate(pick) {
  let kickoffDate = null;
  if (pick.kickoff !== undefined && pick.kickoff !== null) {
    if (typeof pick.kickoff !== "string"
        || !/^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})$/i.test(pick.kickoff)
        || !validDate(pick.kickoff.slice(0, 10))) return null;
    const parsed = new Date(pick.kickoff);
    if (!Number.isFinite(parsed.getTime())) return null;
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Europe/Lisbon", year: "numeric", month: "2-digit", day: "2-digit",
    }).formatToParts(parsed);
    const part = name => parts.find(x => x.type === name)?.value;
    kickoffDate = `${part("year")}-${part("month")}-${part("day")}`;
  }
  if (pick.date !== undefined && pick.date !== null) {
    if (!validDate(pick.date) || (kickoffDate && kickoffDate !== pick.date)) return null;
    return pick.date;
  }
  return kickoffDate;
}

function parseExposure(value) {
  if (!plainObject(value)) return null;
  const maps = Object.fromEntries(GROUPS.map(([field]) => [field, new Map()]));
  let day = value.day === undefined ? 0 : value.day;
  if (!finiteNumber(day) || day < 0) return null;
  day = ceilCents(day);
  if (!Number.isSafeInteger(day)) return null;
  for (const [field] of GROUPS) {
    const raw = value[field] === undefined ? {} : value[field];
    if (!plainObject(raw)) return null;
    let total = 0;
    for (const [name, amount] of Object.entries(raw)) {
      if (!finiteNumber(amount) || amount < 0) return null;
      const normalized = name === UNKNOWN ? UNKNOWN : key(name);
      const cents = ceilCents(amount);
      if (!Number.isSafeInteger(cents)) return null;
      maps[field].set(normalized, (maps[field].get(normalized) || 0) + cents);
      total += cents;
      if (!Number.isSafeInteger(total)) return null;
    }
    // Missing/inconsistent daily totals must never understate already booked exposure.
    day = Math.max(day, total);
  }
  return { day, maps };
}

/**
 * @param {Array<object>} picks Candidates in their existing rank order; score is deliberately ignored.
 * @param {object} policy Amounts are paper units; percentages refer to the supplied paper bankroll.
 * @param {object} currentExposure Existing paper amounts: {day, sport: {}, country: {}, competition: {}}.
 * @returns {{allocations:Array, skipped:Array, totalStake:number, cap:number, warnings:Array,
 *            paperOnly:boolean, leverage:boolean}}
 */
export function planPortfolio(picks, policy = {}, currentExposure = {}) {
  const candidates = Array.isArray(picks) ? picks : [];
  const result = { allocations: [], skipped: [], totalStake: 0, cap: 0, warnings: [], paperOnly: true, leverage: false };
  const refuse = reason => {
    result.skipped = candidates.map(p => ({ id: plainObject(p) ? p.id ?? null : null, reason }));
    result.warnings.push(reason);
    return result;
  };
  if (!Array.isArray(picks)) return refuse("A lista de opções é inválida.");
  if (!plainObject(policy)) return refuse("A política de simulação é inválida.");
  const config = { ...DEFAULT_POLICY, ...policy };
  for (const field of Object.keys(DEFAULT_POLICY)) {
    if (!finiteNumber(config[field]) || config[field] < 0)
      return refuse(`Política inválida: ${field} deve ser um número finito e não negativo.`);
  }
  for (const field of ["perPickPct", "maxDayPct", "maxSportPct", "maxCountryPct", "maxCompetitionPct"]) {
    if (config[field] > 100) return refuse(`Política inválida: ${field} não pode exceder 100%.`);
  }
  if (config.minOdd <= 1 || config.maxOdd < config.minOdd)
    return refuse("O intervalo de odds da simulação é inválido.");
  const exposure = parseExposure(currentExposure);
  if (!exposure) return refuse("A exposição já registada é inválida; a simulação foi suspensa.");
  if (config.bankroll <= 0 || floorCents(config.bankroll) === 0)
    return refuse("Define um saldo de simulação positivo para distribuir posições.");

  const bankrollCents = floorCents(config.bankroll);
  if (!Number.isSafeInteger(bankrollCents)) return refuse("O saldo de simulação excede a precisão numérica suportada.");
  const capFor = percentage => Math.floor(bankrollCents * percentage / 100 + 1e-8);
  const dayCap = Math.min(bankrollCents, capFor(config.maxDayPct));
  const perPick = Math.min(bankrollCents, capFor(config.perPickPct));
  const groupCaps = Object.fromEntries(GROUPS.map(([field, limit]) => [field, capFor(config[limit])]));
  result.cap = dayCap / 100;
  const events = new Set();
  const ids = new Set();
  const allocatedGroups = Object.fromEntries(GROUPS.map(([field]) => [field, new Set()]));
  let newExposure = 0;
  let hasUnknownGroup = false;
  let plannedDate = null;

  for (const pick of candidates) {
    const id = plainObject(pick) ? pick.id ?? null : null;
    const skip = reason => result.skipped.push({ id, reason });
    if (!plainObject(pick) || typeof id !== "string" || !id.trim()) {
      skip("Opção sem identificador válido.");
      continue;
    }
    const sport = key(pick.sport), home = key(pick.home), away = key(pick.away);
    const date = eventDate(pick);
    if ([sport, home, away].includes(UNKNOWN) || home === away || !date) {
      skip("Evento sem desporto, participantes ou data verificáveis.");
      continue;
    }
    if (plannedDate && date !== plannedDate) {
      skip("Uma carteira diária só pode conter jogos do mesmo dia.");
      continue;
    }
    const event = JSON.stringify([sport, ...[home, away].sort(), date]);
    if (ids.has(id) || events.has(event)) {
      skip("O evento já tem uma posição nesta simulação.");
      continue;
    }
    if (!finiteNumber(pick.odds) || pick.odds < config.minOdd || pick.odds > config.maxOdd) {
      skip("Odd observada em falta, inválida ou fora do intervalo definido.");
      continue;
    }
    const buckets = { sport, country: key(pick.country), competition: key(pick.competition) };
    const rooms = [[dayCap - exposure.day, "dia"]];
    for (const [field, , label] of GROUPS)
      rooms.push([groupCaps[field] - (exposure.maps[field].get(buckets[field]) || 0), label]);
    const room = Math.min(perPick, ...rooms.map(([amount]) => amount));
    const cents = Math.max(0, Math.floor(room));
    if (cents < 1) {
      const limit = rooms.find(([amount]) => amount < 1)?.[1];
      skip(limit ? `Limite de exposição por ${limit} atingido.` : "A posição fixa é inferior a uma unidade centesimal.");
      continue;
    }
    const limiting = rooms.filter(([amount]) => amount === cents && amount < perPick).map(([, label]) => label);
    result.allocations.push({
      id, stake: cents / 100, pct: Number((cents / bankrollCents * 100).toFixed(6)),
      reason: limiting.length ? `Simulação limitada pela exposição de ${limiting.join(", ")}.`
        : "Posição fixa de simulação; sem estimativa de rentabilidade.",
    });
    exposure.day += cents;
    newExposure += cents;
    events.add(event);
    ids.add(id);
    plannedDate ??= date;
    for (const [field] of GROUPS) {
      const bucket = buckets[field];
      exposure.maps[field].set(bucket, (exposure.maps[field].get(bucket) || 0) + cents);
      allocatedGroups[field].add(bucket);
      if (bucket === UNKNOWN) hasUnknownGroup = true;
    }
  }
  result.totalStake = newExposure / 100;
  if (exposure.day >= dayCap) result.warnings.push("O limite diário de exposição simulada foi atingido.");
  if (hasUnknownGroup)
    result.warnings.push("Entradas sem país ou competição identificados partilham limites comuns de exposição.");
  if (result.allocations.length > 1) {
    for (const [field, , label] of GROUPS) {
      if (allocatedGroups[field].size === 1)
        result.warnings.push(`As novas posições concentram-se num único ${label}.`);
    }
  }
  return result;
}
