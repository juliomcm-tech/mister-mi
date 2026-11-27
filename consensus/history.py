"""Auditable paper portfolio. Store recommendations before knowing their outcomes."""
from collections import defaultdict
from datetime import datetime, timedelta
from hashlib import sha256
from math import sqrt
from .core import UTC, iso_time, team_equal
import json
import os


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def record(history, payload):
    if payload.get("is_preview") or payload.get("analysis_mode") == "future_preview":
        raise ValueError("Uma pré-visualização futura não pode entrar no histórico de recomendações")
    records = {r["id"]: r for r in history.get("records", [])}

    def same_bet(a, b):
        return (a.get("date") == b.get("date") and a.get("sport") == b.get("sport") and a.get("market") == b.get("market")
                and a.get("outcome") == b.get("outcome") and team_equal(a.get("home", ""), b.get("home", ""), a.get("sport", ""))
                and team_equal(a.get("away", ""), b.get("away", ""), a.get("sport", "")))
    config_hash = sha256(json.dumps(payload["settings"], sort_keys=True).encode()).hexdigest()[:12]
    for pick in payload["data"] + payload.get("zebras", []):
        if pick["id"] not in records and not any(same_bet({**pick, "date": payload["date"]}, r) for r in records.values()):
            # mesma aposta com id diferente (outra fonte passou a dar a hora/país) não é registada outra vez
            # Immutable first-publication price and criteria. Later refreshes never improve an old price.
            records[pick["id"]] = {**pick, "date": payload["date"], "first_seen": payload["updated_at"],
                                   "criteria_revision": config_hash, "result": "pending", "settled_at": None,
                                   "settlement_source": None, "paper_stake_units": 1.0}
    return {"schema_version": 1, "records": sorted(records.values(), key=lambda r: (r["first_seen"], r["id"])),
            "result_sources": history.get("result_sources", [])}


def settlement(pick, result):
    if result.get("status") == "void":
        return "void"
    if result.get("status") != "final":
        return None
    h, a = result.get("home_score"), result.get("away_score")
    if (isinstance(h, bool) or isinstance(a, bool) or not isinstance(h, int) or not isinstance(a, int)
            or not 0 <= h <= 300 or not 0 <= a <= 300):
        return None
    market, outcome = pick["market"], pick["outcome"]
    if market in {"FT_1X2", "MATCH_WINNER"}:
        if market == "MATCH_WINNER" and h == a:
            # empate em «vencedor do jogo»: só existe no futebol americano (devolvida); noutros desportos é dado suspeito
            return "void" if pick.get("sport") == "american_football" else None
        actual = "HOME" if h > a else "AWAY" if a > h else "DRAW"
    elif market.startswith("FT_TOTAL_"):
        line = float(market.rsplit("_", 1)[1])
        actual = "OVER" if h + a > line else "UNDER"
    elif market == "FT_BTTS":
        actual = "YES" if h > 0 and a > 0 else "NO"
    else:
        return None
    return "win" if outcome == actual else "loss"


def apply_results(history, results, now):
    records = {r["id"]: r for r in history["records"]}
    for result in results:
        pick = records.get(result.get("id"))
        if not pick or iso_time(pick["kickoff"]) > now:
            continue
        if pick["result"] != "pending" and not result.get("override"):
            continue  # um resultado manual com "override": true corrige um já liquidado
        answer = settlement(pick, result)
        if answer:
            pick.update(result=answer, settled_at=now.isoformat(), settlement_source=result.get("source", "manual"),
                        final_score=[result.get("home_score"), result.get("away_score")],
                        settlement_evidence={k: result[k] for k in ["source_url", "source_event_id", "verified_at", "attribution", "license"] if k in result})
    return history


def auto_results(history, now):
    """API-Football settles football regular-time markets only; other sports stay pending."""
    if not os.environ.get("API_FOOTBALL_KEY"):
        return [], "Resultados automáticos de futebol: configurar API_FOOTBALL_KEY. Outros desportos: confirmação manual."
    from .sources import Client, country_for, segment_for
    from urllib.parse import urlencode
    client = Client()
    pending = [r for r in history["records"] if r["result"] == "pending" and r["sport"] == "football"
               and iso_time(r["kickoff"]) < now - timedelta(hours=2)
               and iso_time(r["kickoff"]) > now - timedelta(days=14)]
    results = []
    try:
        for day in sorted({r["date"] for r in pending})[-7:]:
            url = "https://v3.football.api-sports.io/fixtures?" + urlencode({"date": day, "timezone": "Europe/Lisbon"})
            data = json.loads(client.get(url, headers={"x-apisports-key": os.environ["API_FOOTBALL_KEY"]}, check_robots=False))
            if data.get("errors"):
                return results, "Falha na API de resultados; verificar plano ou quota. Registos mantidos pendentes."
            for fixture in data.get("response", []):
                if fixture["fixture"]["status"]["short"] not in {"FT", "AET", "PEN"}:
                    continue
                fulltime = fixture.get("score", {}).get("fulltime", {})
                for pick in [r for r in pending if r["date"] == day]:
                    home, away = fixture["teams"]["home"]["name"], fixture["teams"]["away"]["name"]
                    if not (team_equal(home, pick["home"], "football") and team_equal(away, pick["away"], "football")):
                        continue
                    if abs((iso_time(fixture["fixture"]["date"]) - iso_time(pick["kickoff"])).total_seconds()) > 1200:
                        continue
                    if pick["country"] != "Desconhecido" and country_for(fixture["league"]["country"]) != pick["country"]:
                        continue
                    segment = segment_for(fixture["league"]["name"], home, away)
                    original_segment = pick["sources"][0].get("segment", "open")
                    if segment != original_segment:
                        continue
                    results.append({"id": pick["id"], "status": "final", "home_score": fulltime.get("home"),
                                    "away_score": fulltime.get("away"), "source": "api_football"})
        return results, "Resultados de futebol: apenas placares finais no tempo regulamentar confirmados pela API."
    except Exception:
        return results, "Serviço de resultados indisponível; registos mantidos pendentes."


def wilson(wins, n):
    if not n:
        return [None, None]
    z, p = 1.96, wins / n
    d = 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * max(0, center - half), 1), round(100 * min(1, center + half), 1)]


def metrics(records, min_sample=30):
    resolved = [r for r in records if r["result"] in {"win", "loss"}]
    priced = [r for r in resolved if isinstance(r.get("odds"), (int, float)) and r["odds"] > 1]
    wins = sum(r["result"] == "win" for r in resolved)
    units = [(r["odds"] - 1 if r["result"] == "win" else -1) for r in priced]
    balance = peak = max_drawdown = 0
    for unit in units:
        balance += unit
        peak = max(peak, balance)
        max_drawdown = max(max_drawdown, peak - balance)
    return {"total": len(records), "settled": len(resolved), "wins": wins, "losses": len(resolved) - wins,
            "pending": sum(r["result"] == "pending" for r in records), "void": sum(r["result"] == "void" for r in records),
            "hit_rate": round(100 * wins / len(resolved), 1) if resolved else None, "hit_rate_interval_95": wilson(wins, len(resolved)),
            "priced_settled": len(priced), "odds_coverage": round(100 * len(priced) / len(resolved), 1) if resolved else 0,
            "paper_profit_units": round(sum(units), 3), "paper_roi_pct": round(100 * sum(units) / len(priced), 2) if priced else None,
            "paper_max_drawdown_units": round(max_drawdown, 3), "sufficient_sample": len(resolved) >= min_sample}


def score_band(score):
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "?"
    return "90+" if s >= 90 else "80–89" if s >= 80 else "75–79" if s >= 75 else "70–74"


def daily_slips(rows, days=60):
    """Boletim do dia: todas as opções publicadas nesse dia juntas. Ganho só se todas ganharem
    (as devolvidas não contam); a odd é o produto das odds observadas quando todas têm preço."""
    by_day = defaultdict(list)
    for row in rows:
        by_day[row.get("date") or "?"].append(row)
    out = []
    for day in sorted(by_day, reverse=True)[:days]:
        slip, late, lock = [], [], None
        for r in sorted(by_day[day], key=lambda r: (r.get("first_seen") or "", r.get("id") or "")):
            try:
                seen, kick = iso_time(r.get("first_seen") or r["kickoff"]), iso_time(r["kickoff"])
            except (KeyError, TypeError, ValueError):
                late.append(r)
                continue
            if lock is None or seen <= lock:
                slip.append(r)
                lock = kick if lock is None else min(lock, kick)
            else:
                late.append(r)
        picks = sorted(slip, key=lambda r: r.get("kickoff") or "")
        live = [p for p in picks if p["result"] != "void"]
        wins = sum(p["result"] == "win" for p in live)
        losses = sum(p["result"] == "loss" for p in live)
        pending = sum(p["result"] == "pending" for p in live)
        status = "lost" if losses else "pending" if pending else "won" if live else "void"
        priced = all(isinstance(p.get("odds"), (int, float)) and p["odds"] > 1 for p in live) and live
        odd = 1.0
        for p in live:
            odd *= p["odds"] if priced else 1
        out.append({"date": day, "picks": len(picks), "wins": wins, "losses": losses, "pending": pending,
                    "void": len(picks) - len(live), "status": status, "late": len(late), "combined_odds": round(odd, 2) if priced else None,
                    "items": [{"match": p.get("match"), "selection": p.get("selection"), "competition": p.get("competition"),
                               "kickoff": p.get("kickoff"), "odds": p.get("odds"), "result": p["result"],
                               "final_score": p.get("final_score"), "sources": p.get("sources", []), "tier": p.get("tier")}
                              for p in picks]})
    settled = [d for d in out if d["status"] in {"won", "lost"}]
    return {"days": out, "settled": len(settled), "won": sum(d["status"] == "won" for d in settled),
            "hit_rate": round(100 * sum(d["status"] == "won" for d in settled) / len(settled), 1) if settled else None}


def zebra_summary(rows, minimum):
    z = [r for r in rows if r.get("kind") == "zebra"]
    priced = [r for r in z if isinstance(r.get("odds"), (int, float))]
    return {**metrics(z, minimum), "average_odds": round(sum(r["odds"] for r in priced) / len(priced), 2) if priced else None,
            "items": [{"date": r.get("date"), "match": r.get("match"), "selection": r.get("selection"), "odds": r.get("odds"),
                       "implied_pct": r.get("implied_pct"), "source_says": r.get("source_says", []), "result": r["result"],
                       "final_score": r.get("final_score"), "competition": r.get("competition")}
                      for r in sorted(z, key=lambda r: r.get("kickoff") or "", reverse=True)[:30]]}


def summary(history, settings):
    all_rows = history["records"]
    rows = [r for r in all_rows if r.get("kind") != "zebra"]  # as zebras têm contas próprias
    minimum = settings.get("history_min_sample", 30)
    result = {"overall": metrics(rows, minimum), "by_sport": [], "by_country": [], "by_market": [], "by_combination": [],
              "min_sample": minimum, "paper_only": True, "commission_included": False,
              "calibrated_probability_available": False}
    for field, output in [("sport", "by_sport"), ("country", "by_country"), ("market", "by_market")]:
        groups = defaultdict(list)
        for row in rows:
            groups[row.get(field, "Desconhecido")].append(row)
        result[output] = [{"key": key, **metrics(group, minimum)} for key, group in sorted(groups.items())]
    # onde acerta e onde falha: por liga/competição, pelas fontes que concordaram e pelo nível (ouro/prata)
    extra = {
        "by_competition": lambda r: (r.get("competition") or "Desconhecida").strip(),
        "by_sources": lambda r: " + ".join(sorted(s if isinstance(s, str) else s.get("source", "?") for s in r.get("sources", []))) or "?",
        "by_tier": lambda r: r.get("tier") or "?",
        "by_score_band": lambda r: score_band(r.get("score")),
    }
    for output, key in extra.items():
        groups = defaultdict(list)
        for row in rows:
            groups[key(row)].append(row)
        result[output] = sorted(({"key": k, **metrics(g, minimum)} for k, g in groups.items()),
                                key=lambda x: (-x["settled"], -x["total"], x["key"]))
    result["daily"] = daily_slips(rows)
    result["zebra"] = zebra_summary(all_rows, minimum)
    combinations = defaultdict(list)
    for row in rows:
        combinations[(row["sport"], row.get("country", "Desconhecido"))].append(row)
    for (sport, country), group in sorted(combinations.items()):
        stat = metrics(group, minimum)
        warning = stat["priced_settled"] >= minimum and stat["odds_coverage"] >= 80 and stat["paper_roi_pct"] < settings.get("history_warning_roi", -10)
        result["by_combination"].append({"sport": sport, "country": country, **stat, "review_suggested": warning})
    return result
