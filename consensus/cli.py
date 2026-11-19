from datetime import datetime
from pathlib import Path
from .core import UTC, analyse, upcoming_previews
from .sources import collect
from .history import load_json, record, apply_results, auto_results, summary
from .free_results import collect_free_results
from .fixture_catalog import collect_fixture_catalog, verify_fixture
from .oddspedia import collect_oddspedia_feed
from scripts.pipeline_health import collect_pipeline_health
import argparse
import json
import os


def main():
    parser = argparse.ArgumentParser(description="Recolher e filtrar prognósticos de hoje")
    parser.add_argument("--output", default="web/data/consenso_hoje.json")
    parser.add_argument("--history", default="web/data/history.json")
    parser.add_argument("--settings", default="config/settings.json")
    parser.add_argument("--results", default="config/results.json")
    args = parser.parse_args()
    now = datetime.now(UTC)
    tips, sources = collect(now)
    now = datetime.now(UTC)
    settings = load_json(args.settings, {})
    payload = analyse(tips, now, settings)
    payload["previews"] = upcoming_previews(tips, now, settings)
    api_candidates = payload.get("data", []) + [pick for snapshot in payload["previews"]
                      for key in ("data", "candidates", "watchlist") for pick in snapshot.get(key, [])]
    payload["oddspedia_feed"] = collect_oddspedia_feed(now, queries=[pick.get("home") for pick in api_candidates])
    prior_history = load_json(args.history, {"schema_version": 1, "records": []})
    catalog = collect_fixture_catalog(prior_history.get("fixture_catalog"), now)
    payload["fixture_catalog"] = catalog
    for snapshot in [payload, *payload["previews"]]:
        for pick in [*snapshot.get("data", []), *snapshot.get("candidates", []), *snapshot.get("watchlist", [])]:
            pick["fixture_verification"] = verify_fixture(pick, catalog)
    history = record(prior_history, payload)
    history["fixture_catalog"] = catalog
    free_results, free_statuses = collect_free_results(history, now)
    history["result_sources"] = free_statuses
    automatic, outcome_note = auto_results(history, now)
    # Conflicting final score evidence remains pending, rather than settling from whichever arrived first.
    candidates = free_results + automatic + load_json(args.results, {"results": []})["results"]
    conflicts = {r["id"] for r in candidates if len({(x.get("status"), x.get("home_score"), x.get("away_score")) for x in candidates if x["id"] == r["id"]}) > 1}
    apply_results(history, [r for r in candidates if r["id"] not in conflicts], now)
    payload["performance"] = summary(history, settings)
    payload["settlement_note"] = outcome_note
    payload["result_sources"] = free_statuses
    payload["analyst"] = "Mister Mi"
    payload["sources"] = sources
    source_counts = {s["id"]: s for s in payload["diagnostics"]["by_source"]}
    for source in sources:
        counts = source_counts.get(source["id"], {})
        source["today"] = counts.get("today", 0)
        source["eligible"] = counts.get("eligible", 0)
    payload["request_id"] = os.environ.get("REQUEST_ID", "")[:100]
    payload["run_url"] = os.environ.get("RUN_URL", "")
    configured = [s for s in sources if s["status"] != "not_configured"]
    payload["status"] = "error" if all(s["status"] == "error" for s in configured) else "partial" if any(s["status"] != "ok" for s in configured) else "ok"
    payload["pipeline_health"] = collect_pipeline_health(now=now)
    payload["run_event"] = os.environ.get("RUN_EVENT", "unknown")
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)
    history_path = Path(args.history)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_temp = history_path.with_suffix(".tmp")
    history_temp.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    history_temp.replace(history_path)
    print(json.dumps({"date": payload["date"], "selected": payload["total_selected"], "collected": len(tips),
                      "sources": [{"id": s["id"], "status": s["status"], "collected": s["collected"]} for s in sources],
                      "oddspedia_feed": payload["oddspedia_feed"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
