"""Replay coverage and rule diagnostics without changing production settings.

Run from the repository root:
  python scripts/audit_coverage.py --snapshot ../research/mi-future-live-audit.json
  python scripts/audit_coverage.py --live-olbg

The optional live route contacts only the already permitted public OLBG pages.
The sensitivity table and synthetic fixtures are explicitly diagnostic, not
production recommendations, predictive validation, or parameter optimisation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup
from consensus.core import DEFAULTS, UTC, Tip, analyse, iso_time, score_tips, upcoming_previews
from consensus.sources import Client, OLBG_URLS, SPORTS, _olbg_event, _olbg_public_tips, market_selection, parse_olbg


def window(tips, now, settings=None):
    return [analyse(tips, now, settings), *upcoming_previews(tips, now, settings)]


def brief(payload):
    d = payload["diagnostics"]
    return {"date": payload["date"], "forecasts_on_date": d["today_forecasts"],
            "events_on_date": d["today_events"], "eligible_forecasts": payload["total_eligible"],
            "consensus_candidates": payload.get("total_consensus_candidates", payload["total_selected"]),
            "awaiting_sources": d["watchlist_total"], "threshold_reasons": d["threshold_reasons"],
            "time_and_quality_exclusions": {k: payload["discarded"][k] for k in ["started_or_soon", "stale", "threshold"]},
            "comparison_rejections": d["comparison_rejections"]}


def diagnose_public_rows(html, url):
    """Count public-row losses before normalization; never infer unseen fixtures."""
    rows = _olbg_public_tips(BeautifulSoup(html, "html.parser"))
    if rows is None:
        return {"available": False, "note": "No supported public hydration; parser may use rendered rows"}
    categories = Counter()
    for row in rows:
        if row.get("expired") or row.get("cancelled") or row.get("postponed"):
            categories["inactive"] += 1
            continue
        try:
            _, sport, home, away = _olbg_event(url, row["eventUrl"], row["event_name_alias"])
            market = market_selection(row["market_alias"], row["selection"], home, away, sport)
            if market is None:
                categories["unsupported_market"] += 1
                continue
            stamp = row["event_start_unix_timestamp"]
            if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or stamp <= 0:
                raise ValueError("invalid timestamp")
            datetime.fromtimestamp(stamp, UTC)
            yes, total = row["win_tips"], row["win_tips_count"]
            if type(yes) is not int or type(total) is not int or not 0 <= yes <= total or total <= 0:
                raise ValueError("invalid votes")
            categories["supported_active"] += 1
        except (KeyError, ValueError, TypeError, OverflowError, OSError):
            categories["invalid_or_unsupported_identity"] += 1
    return {"available": True, "public_rows": len(rows), "categories": dict(sorted(categories.items()))}


def live_olbg():
    client = Client()

    def read(url):
        try:
            html = client.get(url)
            fetched = datetime.now(UTC)
            tips, raw, _ = parse_olbg(html, url, fetched)
            return tips, {"url": url, "status": "ok", "raw": raw, "collected": len(tips),
                          "row_diagnostics": diagnose_public_rows(html, url)}
        except Exception as exc:
            return [], {"url": url, "status": "error", "error": str(exc)}

    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(read, OLBG_URLS))
    return [tip for tips, _ in records for tip in tips], datetime.now(UTC), [log for _, log in records]


def load_snapshot(path):
    saved = json.loads(Path(path).read_text(encoding="utf-8"))
    now = iso_time(saved["observed_at"])
    tips = [Tip(**item) for item in saved["tips"]]
    return tips, now, saved.get("sources", [])


def synthetic_rule_checks():
    """Hypothetical fixtures isolate rule behavior; these are not sporting data."""
    clock = datetime(2026, 11, 19, 12, tzinfo=UTC)
    a = Tip("olbg", "football", "Audit Home", "Audit Away", "2026-11-19", "2026-11-19T20:00:00Z",
            "FT_1X2", "HOME", "https://example.invalid/audit", clock.isoformat(),
            metric=80, metric_kind="vote_pct", votes_for=20, votes_total=25)
    b = replace(a, source="forebet", metric=70, metric_kind="model_pct", votes_for=0, votes_total=0)
    scenarios = {
        "two_agreeing_independent_providers": [a, b],
        "second_provider_unavailable": [a],
        "five_duplicate_pages_of_one_provider": [a] * 5,
        "independent_provider_disagrees": [a, replace(b, outcome="AWAY")],
        "wrong_lisbon_day": [replace(t, event_date="2026-11-20") for t in [a, b]],
        "old_collection": [replace(t, fetched_at=(clock-timedelta(minutes=46)).isoformat()) for t in [a, b]],
    }
    return {"kind": "synthetic_rule_checks", "not_live_forecasts": True,
            "settings_basis": "Core DEFAULTS; synthetic fixtures are not parameter optimisation",
            "scenarios": {key: brief(analyse(records, clock)) for key, records in scenarios.items()}}


def screenshot_score_audit():
    """Recompute the numbers transcribed from the user's screenshot, as claims."""
    clock = datetime(2026, 11, 19, 12, tzinfo=UTC)
    claims = [("Benfica Women vs AS Roma Women", 28, 34, 8.7, 71, 96.1),
              ("Arsenal Women vs OL Lyonnes", 31, 38, 8.4, 68, 95.5),
              ("Ben Shelton vs Rafael Jodar", 25, 29, 8.9, None, 97.5),
              ("Boston Celtics vs LA Lakers", 34, 40, 9.1, None, 97.0)]
    results = []
    for match, yes, total, tip_score, model, claimed in claims:
        a = Tip("olbg", "football", "Screenshot Home", "Screenshot Away", "2026-11-19", "2026-11-19T20:00:00Z",
                "FT_1X2", "HOME", "https://example.invalid/unverified-claim", clock.isoformat(),
                metric=round(100*yes/total, 2), metric_kind="vote_pct", votes_for=yes, votes_total=total)
        evidence = [a, replace(a, source="protipster", metric=tip_score, metric_kind="tip_score", votes_for=0, votes_total=0)]
        if model is not None:
            evidence.append(replace(a, source="forebet", metric=model, metric_kind="model_pct", votes_for=0, votes_total=0))
        results.append({"match_label_from_screenshot": match, "claimed_score": claimed,
                        "score_using_repository_formula": score_tips(evidence), "source_count_claimed": len(evidence)})
    extreme = replace(a, metric=100, votes_for=50, votes_total=50)
    extreme_pro = replace(extreme, source="protipster", metric=10, metric_kind="tip_score", votes_for=0, votes_total=0)
    extreme_model = replace(extreme, source="forebet", metric=100, metric_kind="model_pct", votes_for=0, votes_total=0)
    return {"provenance": "User screenshot; source observations and fixtures not independently established by this calculation",
            "maximum_two_source_score": score_tips([extreme, extreme_pro]),
            "maximum_three_source_score": score_tips([extreme, extreme_pro, extreme_model]),
            "claims": results}


def build_report(tips, now, source_logs, settings=None):
    settings = DEFAULTS | (settings or {})
    sports = sorted(set(SPORTS.values()))
    base = window(tips, now, settings)
    per_sport = {sport: window([tip for tip in tips if tip.sport == sport], now, settings) for sport in sports}
    sensitivity = []
    for votes in (5, 10, 15, 20):
        for support in (65, 75, 85):
            trial = window(tips, now, settings | {"min_votes": votes, "min_olbg": support})
            sensitivity.append({"min_votes": votes, "min_olbg": support,
                                "days": [{"date": p["date"], "eligible": p["total_eligible"],
                                          "consensus": p.get("total_consensus_candidates", p["total_selected"])} for p in trial]})
    return {"kind": "coverage_diagnostic_not_predictive_backtest", "evaluated_as_of": now.isoformat(),
            "scope": "Only forecasts present in the supplied snapshot or allowed public OLBG responses",
            "configured_sports": sports, "covers_all_sports_or_daily_fixtures": False,
            "production_settings_unchanged": True, "default_qualification_rules": {
                k: settings[k] for k in ["min_votes", "min_olbg", "min_protipster", "min_model", "min_sources", "min_score"]},
            "source_logs": source_logs, "forecasts_normalized": len(tips),
            "normalized_markets_by_sport": {sport: dict(sorted(Counter(t.market for t in tips if t.sport == sport).items()))
                                            for sport in sports},
            "days": [{**brief(p), "by_sport": [{"sport": sport, **brief(per_sport[sport][i])} for sport in sports]}
                     for i, p in enumerate(base)],
            "threshold_sensitivity": {"diagnostic_only": True, "live_settings_updated": False, "scenarios": sensitivity},
            "synthetic_rule_checks": synthetic_rule_checks(), "screenshot_score_audit": screenshot_score_audit(),
            "limitations": ["No historical outcomes are evaluated; this is not a success-rate or ROI estimate.",
                            "Relaxing a community threshold cannot supply an unavailable independent provider.",
                            "A source-specific vote ratio is not a calibrated probability of winning."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    route = parser.add_mutually_exclusive_group(required=True)
    route.add_argument("--snapshot", type=Path)
    route.add_argument("--live-olbg", action="store_true")
    parser.add_argument("--settings", type=Path, default=ROOT / "config" / "settings.json")
    args = parser.parse_args()
    tips, now, logs = live_olbg() if args.live_olbg else load_snapshot(args.snapshot)
    settings = json.loads(args.settings.read_text(encoding="utf-8"))
    print(json.dumps(build_report(tips, now, logs, settings), ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
