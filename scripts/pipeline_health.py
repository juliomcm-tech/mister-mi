"""Read-only evidence of actual GitHub schedule events, not just a cron declaration.

No credentials, dispatches, retries, or repository writes. Two public API reads
are bounded by an eight-second timeout and one-megabyte response limit.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.request import Request, build_opener, HTTPRedirectHandler
import argparse
import json
import re

UTC = timezone.utc
WORKFLOW_PATH = ".github/workflows/collect.yml"


def _instant(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(UTC) if result.tzinfo is not None else None
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None


def build_pipeline_health(runs, now, workflow=None, *, schedule="13,43 * * * *", max_age_minutes=45):
    """Summarize a bounded run window; absence is not evidence of a working cron."""
    if now.tzinfo is None:
        raise ValueError("O relógio da auditoria precisa de fuso horário")
    if not isinstance(runs, list) or not all(isinstance(run, dict) for run in runs):
        raise ValueError("Lista de execuções inválida")
    if not isinstance(max_age_minutes, (int, float)) or not 0 < max_age_minutes <= 1440:
        raise ValueError("Limite de frescura inválido")
    now = now.astimezone(UTC)
    workflow = workflow if isinstance(workflow, dict) else {}
    workflow_state = workflow.get("state", "unknown")
    matching = [run for run in runs if run.get("path") == WORKFLOW_PATH
                or workflow.get("id") is not None and run.get("workflow_id") == workflow["id"]]
    dated = [(run, _instant(run.get("created_at"))) for run in matching]
    dated = [(run, stamp) for run, stamp in dated if stamp and (stamp-now).total_seconds() <= 60]
    dated.sort(key=lambda item: item[1], reverse=True)
    scheduled = [(run, stamp) for run, stamp in dated if run.get("event") in {"schedule", "workflow_dispatch"}]
    last_run = dated[0][0] if dated else {}
    last_schedule, last_at = scheduled[0] if scheduled else ({}, None)
    age = round(max(0, (now-last_at).total_seconds()/60), 1) if last_at else None
    successful = next((stamp for run, stamp in scheduled if run.get("conclusion") == "success"), None)
    if workflow_state not in {"active", "unknown"}:
        state = "disabled"
    elif not scheduled:
        state = "not_observed" if workflow_state == "active" else "unknown"
    elif age > max_age_minutes:
        state = "overdue"
    elif last_schedule.get("status") in {"queued", "in_progress", "waiting", "requested", "pending"}:
        state = "running"
    elif last_schedule.get("conclusion") == "success":
        state = "observed"
    else:
        state = "failed"
    return {
        "checked_at": now.isoformat(), "schedule": schedule, "timezone": "UTC",
        "workflow_state": workflow_state, "scheduler_status": state,
        "last_scheduled_at": last_at.isoformat() if last_at else None,
        "last_successful_scheduled_at": successful.isoformat() if successful else None,
        "scheduled_age_minutes": age, "max_age_minutes": max_age_minutes,
        "schedule_runs_observed": len(scheduled), "run_window": len(runs),
        "last_event": last_run.get("event"), "last_run_url": last_run.get("html_url"),
    }


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirecionamento da API recusado")


def _public_json(url):
    request = Request(url, headers={"User-Agent": "MisterMi/1.0", "Accept": "application/vnd.github+json",
                                    "X-GitHub-Api-Version": "2022-11-28"})
    with build_opener(_NoRedirect()).open(request, timeout=8) as response:
        content = response.read(1_000_001)
    if len(content) > 1_000_000:
        raise ValueError("Resposta da API demasiado grande")
    return json.loads(content)


def collect_pipeline_health(repository="juliomcm-tech/mister-mi", now=None, *, schedule="13,43 * * * *", max_age_minutes=45):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Repositório inválido")
    now = now or datetime.now(UTC)
    base = "https://api.github.com/repos/" + repository
    urls = {"workflow": base + "/actions/workflows/collect.yml", "runs": base + "/actions/runs?per_page=100"}
    values, errors = {}, {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = {key: pool.submit(_public_json, url) for key, url in urls.items()}
        for key, future in pending.items():
            try:
                values[key] = future.result()
            except Exception as exc:
                code = getattr(exc, "code", None)
                errors[key] = f"HTTP {code}" if code else type(exc).__name__
    runs = values.get("runs", {}).get("workflow_runs") if isinstance(values.get("runs"), dict) else None
    if runs is None:
        result = build_pipeline_health([], now, values.get("workflow"), schedule=schedule, max_age_minutes=max_age_minutes)
        result["scheduler_status"] = "unavailable"
        result["run_window"] = None
    else:
        try:
            result = build_pipeline_health(runs, now, values.get("workflow"), schedule=schedule, max_age_minutes=max_age_minutes)
        except ValueError:
            errors["runs"] = "InvalidResponse"
            result = build_pipeline_health([], now, schedule=schedule, max_age_minutes=max_age_minutes)
            result.update(scheduler_status="unavailable", run_window=None)
    result["errors"] = errors
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default="juliomcm-tech/mister-mi")
    parser.add_argument("--schedule", default="13,43 * * * *")
    args = parser.parse_args()
    print(json.dumps(collect_pipeline_health(args.repository, schedule=args.schedule), ensure_ascii=False))
