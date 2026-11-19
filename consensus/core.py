from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from hashlib import sha256
from statistics import mean
from zoneinfo import ZoneInfo
import re
import unicodedata

LISBON = ZoneInfo("Europe/Lisbon")
UTC = timezone.utc
ALIASES = {
    "man city": "manchester city", "man utd": "manchester united",
    "psg": "paris saint germain", "inter milan": "internazionale",
    "atletico madrid": "atletico de madrid", "fc fredericia": "fredericia",
    "montevideo city": "montevideo city torque", "rb bragantino": "bragantino",
    "red bull bragantino": "bragantino", "lyon": "olympique lyonnais",
    "bayern munchen": "bayern munich", "fc bayern munchen": "bayern munich",
    "1 fc koln": "cologne", "tottenham hotspur": "tottenham", "ipswich town": "ipswich",
    "newcastle united": "newcastle", "sl benfica w": "benfica w", "as roma w": "roma w",
    "ol lyonnes": "olympique lyonnais w", "lyon w": "olympique lyonnais w",
    "bos celtics": "boston celtics", "den nuggets": "denver nuggets",
    "la lakers": "los angeles lakers", "uta jazz": "utah jazz",
}


def name_key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    value = re.sub(r"\b(women|woman|feminino|ladies)\b", "w", value)
    value = re.sub(r"[^a-z0-9 ]", " ", value)
    value = " ".join(value.split())
    return ALIASES.get(value, value)


def identity_tags(value: str) -> set[str]:
    return set(re.findall(r"\b(?:w|u\d{2}|reserves|ii|iii|b)\b", name_key(value)))


def team_equal(a: str, b: str, sport: str) -> bool:
    a, b = name_key(a), name_key(b)
    if not a or not b:
        return False
    if a == b:
        return True
    if sport == "tennis":
        aa, bb = a.split(), b.split()
        # Full names with the same initial (Karolina/Kristyna) are different people.
        # A one-letter abbreviation is allowed only after daily-roster ambiguity checks in analyse().
        return (len(aa) > 1 and len(bb) > 1 and aa[-1] == bb[-1] and aa[0][0] == bb[0][0]
                and (len(aa[0]) == 1 or len(bb[0]) == 1))
    if identity_tags(a) != identity_tags(b):
        return False
    # Never identify events from resemblance of the whole match string.
    return len(a) > 6 and len(b) > 6 and SequenceMatcher(None, a, b).ratio() >= 0.94


def iso_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Horário sem fuso")
    return dt.astimezone(UTC)


@dataclass(frozen=True)
class Tip:
    source: str
    sport: str
    home: str
    away: str
    event_date: str
    kickoff: str | None
    market: str
    outcome: str
    url: str
    fetched_at: str
    competition: str = ""
    metric: float | None = None
    metric_kind: str = "categorical"
    votes_for: int = 0
    votes_total: int = 0
    odds: float | None = None
    event_id: str = ""
    segment: str = "open"
    status: str = "scheduled"
    country: str = "Desconhecido"

    def rejection_reason(self, settings: dict) -> str | None:
        if self.status != "scheduled":
            return "not_scheduled"
        if self.market not in {
            "FT_1X2", "MATCH_WINNER", "FT_TOTAL_1.5", "FT_TOTAL_2.5", "FT_TOTAL_3.5", "FT_BTTS"
        }:
            return "unsupported_market"
        if self.source == "olbg":
            if not 0 < self.votes_for <= self.votes_total:
                return "invalid_votes"
            if self.votes_total < settings["min_votes"]:
                return "insufficient_votes"
            return None if 100 * self.votes_for / self.votes_total >= settings["min_olbg"] else "below_source_threshold"
        if self.source in {"protipster", "forebet", "api_football", "betclan"}:
            kind = "tip_score" if self.source == "protipster" else "model_pct"
            if self.metric_kind != kind or self.metric is None:
                return "missing_metric"
            minimum, maximum = (settings["min_protipster"], 10) if self.source == "protipster" else (settings["min_model"], 100)
            return None if minimum <= self.metric <= maximum else "below_source_threshold"
        return None if self.source == "predictz" and self.metric_kind == "categorical" else "unsupported_source"

    def eligible(self, settings: dict) -> bool:
        return self.rejection_reason(settings) is None


DEFAULTS = {"min_votes": 15, "min_olbg": 75, "min_protipster": 8, "min_model": 65,
            "min_sources": 2, "min_score": 70, "max_picks": 6, "max_age_minutes": 45,
            "kickoff_tolerance_minutes": 20, "lead_minutes": 5,
            "excluded_sports": [], "excluded_countries": [], "excluded_combinations": [],
            "min_odds": None, "max_odds": None}


def same_event(a: Tip, b: Tip, settings: dict) -> bool:
    if (a.sport, a.event_date, a.segment) != (b.sport, b.event_date, b.segment):
        return False
    if a.country != "Desconhecido" and b.country != "Desconhecido" and a.country != b.country:
        return False
    if not team_equal(a.home, b.home, a.sport) or not team_equal(a.away, b.away, a.sport):
        return False
    if a.kickoff and b.kickoff:
        return abs((iso_time(a.kickoff) - iso_time(b.kickoff)).total_seconds()) <= settings["kickoff_tolerance_minutes"] * 60
    return True


def score_tips(tips: list[Tip]) -> float:
    # A ranking index, never a win probability. Categorical tips add no numerical strength.
    strengths = [t.metric * 10 if t.metric_kind == "tip_score" else t.metric
                 for t in tips if t.metric is not None]
    volume = max((t.votes_total for t in tips if t.source == "olbg"), default=0)
    return round(min(98, 50 + 12 * (len(tips) - 1) + 0.12 * mean(strengths or [0]) + 8 * min(volume / 50, 1)), 1)


def selection_label(tip: Tip) -> str:
    if tip.outcome in {"HOME", "AWAY"}:
        return (tip.home if tip.outcome == "HOME" else tip.away) + " vence"
    if tip.outcome == "DRAW":
        return "Empate"
    if tip.market.startswith("FT_TOTAL_"):
        return ("Mais de " if tip.outcome == "OVER" else "Menos de ") + tip.market.rsplit("_", 1)[1] + " golos"
    return "Ambas marcam: " + ("sim" if tip.outcome == "YES" else "não")


def group_events(tips: list[Tip], settings: dict) -> list[list[Tip]]:
    groups: list[list[Tip]] = []
    # Stable ordering keeps diagnostics and tie-breaking independent of network completion order.
    for tip in sorted(tips, key=lambda t: (t.kickoff is None, t.kickoff or "", t.source,
                                           t.home, t.away, t.market, t.outcome, t.url)):
        try:
            if tip.kickoff:
                iso_time(tip.kickoff)
            group = next((g for g in groups if all(same_event(tip, t, settings) for t in g)), None)
            if group is None:
                groups.append([tip])
            else:
                group.append(tip)
        except (ValueError, TypeError, OverflowError):
            continue
    return groups


def analyse(tips: list[Tip], now: datetime, settings: dict | None = None) -> dict:
    """Production analysis is always restricted to the actual current Lisbon day."""
    return _analyse_day(tips, now, settings, now.astimezone(LISBON).date().isoformat())


def upcoming_previews(tips: list[Tip], now: datetime, settings: dict | None = None) -> list[dict]:
    """Inspect already-published future forecasts, using the real collection clock.

    These are current observations about future fixtures, not a blind backtest,
    a prediction of tomorrow's data, or production recommendations.
    """
    previews = []
    current_day = now.astimezone(LISBON).date()
    for offset in (1, 2):
        day = (current_day + timedelta(days=offset)).isoformat()
        result = _analyse_day(tips, now, settings, day)
        candidates = [{**pick, "status": "preliminary_consensus", "is_recommendation": False}
                      for pick in result.pop("data")]
        result.update(analysis_mode="future_preview", is_preview=True, day_offset=offset,
                      total_consensus_candidates=len(candidates), total_selected=0, data=[], candidates=candidates)
        previews.append(result)
    return previews


def _analyse_day(tips: list[Tip], now: datetime, settings: dict | None, target_day: str) -> dict:
    settings = DEFAULTS | (settings or {})
    today = target_day
    tennis_roster = {}
    for tip in tips:
        if tip.sport == "tennis" and tip.event_date == today:
            for player in [tip.home, tip.away]:
                parts = name_key(player).split()
                if len(parts) > 1 and len(parts[0]) > 1:
                    tennis_roster.setdefault((parts[0][0], parts[-1]), set()).add(name_key(player))
    eligible = []
    discarded = {"other_day": 0, "started_or_soon": 0, "stale": 0, "threshold": 0, "conflict": 0, "excluded": 0}
    threshold_reasons: dict[str, int] = {}
    comparison = {"insufficient_sources": 0, "missing_kickoff": 0, "odds_filter": 0, "below_consensus_score": 0}

    def reject_threshold(reason):
        discarded["threshold"] += 1
        threshold_reasons[reason] = threshold_reasons.get(reason, 0) + 1

    for tip in tips:
        try:
            if tip.event_date != today:
                discarded["other_day"] += 1
                continue
            if tip.sport == "tennis":
                ambiguous = False
                for player in [tip.home, tip.away]:
                    parts = name_key(player).split()
                    if len(parts) > 1 and len(parts[0]) == 1 and len(tennis_roster.get((parts[0], parts[-1]), set())) > 1:
                        ambiguous = True
                if ambiguous:
                    reject_threshold("ambiguous_identity")
                    continue
            age = (now - iso_time(tip.fetched_at)).total_seconds()
            if age < -60 or age > settings["max_age_minutes"] * 60:
                discarded["stale"] += 1
                continue
            if tip.kickoff and (iso_time(tip.kickoff).astimezone(LISBON).date().isoformat() != today
                                or (iso_time(tip.kickoff) - now).total_seconds() <= settings["lead_minutes"] * 60):
                discarded["started_or_soon"] += 1
                continue
            reason = tip.rejection_reason(settings)
            if reason:
                reject_threshold(reason)
                continue
            eligible.append(tip)
        except (ValueError, TypeError, OverflowError):
            reject_threshold("invalid_record")

    # Timed records are anchors. Undated/untimed categorical pages only corroborate.
    groups = group_events(eligible, settings)
    selected, watchlist = [], []
    for group in groups:
        by_market: dict[str, list[Tip]] = {}
        for tip in group:
            by_market.setdefault(tip.market, []).append(tip)
        for market, records in by_market.items():
            if len({t.outcome for t in records}) > 1:
                discarded["conflict"] += 1
                continue
            by_source = {}
            for tip in records:
                # Multiple tipsters and multiple pages never count as extra sources.
                previous = by_source.get(tip.source)
                if previous is None or (tip.metric or 0) > (previous.metric or 0):
                    by_source[tip.source] = tip
            evidence = list(by_source.values())
            anchors = [t for t in evidence if t.kickoff and t.source != "predictz"]
            if not anchors:
                comparison["missing_kickoff"] += 1
                continue
            anchor = min(anchors, key=lambda t: iso_time(t.kickoff))
            country = next((t.country for t in evidence if t.country != "Desconhecido"), "Desconhecido")
            if (anchor.sport in settings["excluded_sports"] or country in settings["excluded_countries"]
                    or any(r.get("sport") == anchor.sport and r.get("country") == country for r in settings["excluded_combinations"])):
                discarded["excluded"] += 1
                continue
            # Conservative and invariant to network completion order. Preserve every observed source price.
            observed = min((t for t in evidence if t.odds is not None and t.odds > 1), key=lambda t: (t.odds, t.source), default=None)
            if ((settings["min_odds"] is not None and (observed is None or observed.odds < settings["min_odds"]))
                    or (settings["max_odds"] is not None and (observed is None or observed.odds > settings["max_odds"]))):
                comparison["odds_filter"] += 1
                continue
            if len(evidence) < settings["min_sources"]:
                comparison["insufficient_sources"] += 1
                # Visible research candidates never enter data, history or the simulated portfolio.
                watchlist.append({"sport": anchor.sport, "home": anchor.home, "away": anchor.away,
                                  "match": f"{anchor.home} vs {anchor.away}", "kickoff": anchor.kickoff,
                                  "country": country, "competition": anchor.competition,
                                  "market": market, "outcome": anchor.outcome, "selection": selection_label(anchor),
                                  "odds": observed.odds if observed else None,
                                  "source_count": len(evidence), "sources": [asdict(t) for t in evidence],
                                  "status": "awaiting_independent_source", "is_recommendation": False})
                continue
            score = score_tips(evidence)
            if score < settings["min_score"]:
                comparison["below_consensus_score"] += 1
                continue
            identity = f"{today}|{anchor.kickoff}|{anchor.sport}|{country}|{anchor.segment}|{name_key(anchor.home)}|{name_key(anchor.away)}|{market}|{anchor.outcome}"
            selected.append({
                "id": sha256(identity.encode()).hexdigest()[:16], "sport": anchor.sport,
                "home": anchor.home, "away": anchor.away, "match": f"{anchor.home} vs {anchor.away}",
                "competition": anchor.competition, "kickoff": anchor.kickoff, "market": market,
                "country": country, "odds": observed.odds if observed else None,
                "odds_source": observed.source if observed else None,
                "odds_observed_at": observed.fetched_at if observed else None,
                "outcome": anchor.outcome, "selection": selection_label(anchor), "score": score,
                "tier": "gold" if len(evidence) >= 3 else "silver", "source_count": len(evidence),
                "sources": [asdict(t) for t in evidence],
                "reason": f"{len(evidence)} fontes concordam na mesma seleção e no mesmo mercado.",
            })
    selected.sort(key=lambda x: (-x["source_count"], -x["score"], x["kickoff"]))
    unique_events, final = set(), []
    for tip in selected:
        key = (tip["sport"], tip["kickoff"], tip["country"], name_key(tip["home"]), name_key(tip["away"]))
        if key not in unique_events and len(final) < settings["max_picks"]:
            final.append(tip)
            unique_events.add(key)
    today_tips = [t for t in tips if t.event_date == today]
    source_counts = [{"id": source, "collected": sum(t.source == source for t in tips),
                      "today": sum(t.source == source for t in today_tips),
                      "eligible": sum(t.source == source for t in eligible)} for source in sorted({t.source for t in tips})]
    sport_counts = [{"id": sport, "forecasts": sum(t.sport == sport for t in today_tips),
                     "eligible": sum(t.sport == sport for t in eligible),
                     "events": len(group_events([t for t in today_tips if t.sport == sport], settings)),
                     "confirmed": sum(p["sport"] == sport for p in final),
                     "sources": sorted({t.source for t in today_tips if t.sport == sport})}
                    for sport in ["football", "tennis", "basketball", "hockey", "american_football"]]
    watchlist.sort(key=lambda p: (-p["source_count"], p["kickoff"], p["match"], p["market"]))
    return {"date": today, "timezone": "Europe/Lisbon", "updated_at": now.astimezone(UTC).isoformat(),
            "schema_version": 1, "score_is_probability": False, "settings": settings,
            "total_collected": len(tips), "total_eligible": len(eligible), "total_selected": len(final),
            "discarded": discarded, "data": final, "watchlist": watchlist[:8],
            "diagnostics": {"coverage": "partial", "coverage_note": "Apenas previsões publicadas nas fontes acessíveis; não é um calendário completo de jogos.",
                            "today_forecasts": len(today_tips), "today_events": len(group_events(today_tips, settings)),
                            "eligible_forecasts": len(eligible), "eligible_events": len(groups),
                            "threshold_reasons": threshold_reasons, "comparison_rejections": comparison,
                            "watchlist_total": len(watchlist), "by_source": source_counts, "by_sport": sport_counts}}
