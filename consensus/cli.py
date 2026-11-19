from datetime import datetime
from pathlib import Path
from .core import UTC, analyse
from .sources import collect
from .history import load_json, record, apply_results, auto_results, summary
from .free_results import collect_free_results
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
    history = record(load_json(args.history, {"schema_version": 1, "records": []}), payload)
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
    payload["request_id"] = os.environ.get("REQUEST_ID", "")[:100]
    payload["run_url"] = os.environ.get("RUN_URL", "")
    payload["status"] = "error" if all(s["status"] in {"error", "not_configured"} for s in sources) else "ok"
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
                      "sources": [{"id": s["id"], "status": s["status"], "collected": s["collected"]} for s in sources]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
