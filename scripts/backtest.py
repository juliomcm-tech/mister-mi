"""Chronological experimental benchmark; NOT a backtest of the live consensus.

Frozen before fetching the holdout: train 2023/24, test 2024/25, threshold .65.
Only completed earlier DAYS enter the expanding model, including in training.
No historical odds or archived tipster predictions are inferred from results.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from math import exp, log, sqrt
from pathlib import Path
import re
from urllib.request import Request, urlopen

CONFIG = {
    "training_season": "2023-24", "test_season": "2024-25",
    "test_start": "2024-07-01", "test_end": "2025-06-30",
    "min_league_games": 60, "min_team_games": 5, "team_shrinkage_games": 5,
    "selection_threshold": 0.65, "lambda_min": 0.15, "lambda_max": 5.0,
    "max_goals": 20, "update_frequency": "strictly_earlier_completed_day",
    "tuned_on_holdout": False,
}
LEAGUES = {"en.1": {"name": "English Premier League", "country": "England"},
           "de.1": {"name": "Bundesliga", "country": "Germany"}}
OUTCOMES = ("HOME", "DRAW", "AWAY")
DATA_LICENSE = "https://github.com/openfootball/football.json/blob/master/LICENSE.md"


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def empty_state():
    return {"games": 0, "home_goals": 0, "away_goals": 0,
            "outcomes": [0, 0, 0], "teams": {}, "last_training_day": None}


def learn(state, game):
    home, away = game["home"], game["away"]
    hg, ag = game["home_goals"], game["away_goals"]
    state["games"] += 1
    state["home_goals"] += hg
    state["away_goals"] += ag
    state["outcomes"][actual_outcome(hg, ag)] += 1
    for team, scored, conceded in [(home, hg, ag), (away, ag, hg)]:
        row = state["teams"].setdefault(team, {"games": 0, "scored": 0, "conceded": 0})
        row["games"] += 1
        row["scored"] += scored
        row["conceded"] += conceded
    state["last_training_day"] = game["date"]


def actual_outcome(home_goals, away_goals):
    return 0 if home_goals > away_goals else 2 if home_goals < away_goals else 1


def poisson_probs(home_lambda, away_lambda, max_goals=20):
    def pmf(lam):
        values = [exp(-lam)]
        for goals in range(1, max_goals + 1):
            values.append(values[-1] * lam / goals)
        return values
    result = [0.0, 0.0, 0.0]
    for home, hp in enumerate(pmf(home_lambda)):
        for away, ap in enumerate(pmf(away_lambda)):
            result[actual_outcome(home, away)] += hp * ap
    total = sum(result)
    return [p / total for p in result]


def predict(state, game, config=CONFIG):
    """Only names/date are read from game. Its result is never read here."""
    if state["games"] < config["min_league_games"]:
        return None
    ht, at = state["teams"].get(game["home"]), state["teams"].get(game["away"])
    if not ht or not at or min(ht["games"], at["games"]) < config["min_team_games"]:
        return None
    n = state["games"]
    league_mean = (state["home_goals"] + state["away_goals"]) / (2 * n)
    if league_mean <= 0:
        return None
    prior = config["team_shrinkage_games"]

    def strength(team, field):
        return ((team[field] + prior * league_mean) / (team["games"] + prior)) / league_mean

    lh = state["home_goals"] / n * strength(ht, "scored") * strength(at, "conceded")
    la = state["away_goals"] / n * strength(at, "scored") * strength(ht, "conceded")
    lh, la = [max(config["lambda_min"], min(config["lambda_max"], value)) for value in (lh, la)]
    probs = poisson_probs(lh, la, config["max_goals"])
    baseline = [(count + 1) / (n + 3) for count in state["outcomes"]]
    return {"probabilities": probs, "historical_prior_probabilities": baseline,
            "home_lambda": lh, "away_lambda": la, "training_games": n,
            "home_team_training_games": ht["games"], "away_team_training_games": at["games"],
            "trained_through": state["last_training_day"]}


def brier(probabilities, actual):
    # Multiclass SUM convention: range0..2, lower is better.
    return sum((p - int(index == actual)) ** 2 for index, p in enumerate(probabilities))


def logloss(probabilities, actual):
    return -log(max(1e-15, min(1, probabilities[actual])))


def wilson(correct, total):
    if not total:
        return None
    z, p = 1.959963984540054, correct / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [round(100 * max(0, center - half), 2), round(100 * min(1, center + half), 2)]


def metrics(rows):
    selected = [row for row in rows if row["selected"]]
    correct = sum(row["correct"] for row in selected)
    total = len(rows)
    return {
        "evaluated": total, "selected": len(selected), "selected_correct": correct,
        "selected_incorrect": len(selected) - correct,
        "coverage_pct": round(100 * len(selected) / total, 2) if total else None,
        "selected_hit_rate_pct": round(100 * correct / len(selected), 2) if selected else None,
        "selected_hit_rate_wilson95_pct": wilson(correct, len(selected)),
        "top1_accuracy_pct": round(100 * sum(row["correct"] for row in rows) / total, 2) if total else None,
        "brier_multiclass_sum": round(sum(row["brier"] for row in rows) / total, 6) if total else None,
        "log_loss_natural": round(sum(row["log_loss"] for row in rows) / total, 6) if total else None,
        "always_home_accuracy_pct": round(100 * sum(row["actual"] == "HOME" for row in rows) / total, 2) if total else None,
        "always_home_on_selected_accuracy_pct": round(100 * sum(row["actual"] == "HOME" for row in selected) / len(selected), 2) if selected else None,
        "historical_prior_brier": round(sum(row["prior_brier"] for row in rows) / total, 6) if total else None,
        "historical_prior_log_loss": round(sum(row["prior_log_loss"] for row in rows) / total, 6) if total else None,
    }


def walk_forward(games, config=CONFIG):
    """Predict an entire day before learning ANY outcome from that day."""
    states, by_day = {}, defaultdict(list)
    for game in games:
        if game["date"] <= config["test_end"]:
            by_day[game["date"]].append(game)
    ledger, scored, warmup_excluded, training_count, test_count = [], [], 0, 0, 0
    for day in sorted(by_day):
        batch = sorted(by_day[day], key=lambda g: (g["league"], g["home"], g["away"]))
        if day >= config["test_start"]:
            test_count += len(batch)
            for game in batch:
                state = states.setdefault(game["league"], empty_state())
                prediction = predict(state, game, config)
                if prediction is None:
                    warmup_excluded += 1
                    continue
                top = max(range(3), key=lambda index: prediction["probabilities"][index])
                entry = {"league": game["league"], "date": day, "home": game["home"], "away": game["away"],
                         **prediction, "prediction": OUTCOMES[top],
                         "selected": prediction["probabilities"][top] >= config["selection_threshold"]}
                assert entry["trained_through"] is None or entry["trained_through"] < day
                # Store the ex-ante prediction before reading the held-out result.
                ledger.append(deepcopy(entry))
                actual = actual_outcome(game["home_goals"], game["away_goals"])
                scored.append({**entry, "actual": OUTCOMES[actual], "correct": actual == top,
                               "final_score": [game["home_goals"], game["away_goals"]],
                               "brier": brier(entry["probabilities"], actual),
                               "log_loss": logloss(entry["probabilities"], actual),
                               "prior_brier": brier(entry["historical_prior_probabilities"], actual),
                               "prior_log_loss": logloss(entry["historical_prior_probabilities"], actual)})
        else:
            training_count += len(batch)
        # No same-day leakage, including when file order changes.
        for game in batch:
            learn(states.setdefault(game["league"], empty_state()), game)
    return {"overall": metrics(scored), "by_league": {league: metrics([r for r in scored if r["league"] == league]) for league in sorted(states)},
            "training_completed_matches": training_count, "test_completed_matches": test_count,
            "warmup_excluded": warmup_excluded, "prediction_ledger_sha256": digest(ledger),
            "first_test_date": min((r["date"] for r in scored), default=None),
            "last_test_date": max((r["date"] for r in scored), default=None),
            "sample_predictions": scored[:10] + scored[-10:] if len(scored) > 20 else scored,
            "selected_predictions": [r for r in scored if r["selected"]][:20],
            "_prediction_ledger": ledger, "_evaluation_ledger": scored}


def parse_source(raw, league, season):
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("matches"), list):
        raise ValueError("Unexpected openfootball JSON structure")
    result, skipped, seen = [], 0, set()
    for item in data["matches"]:
        try:
            day = date.fromisoformat(item["date"]).isoformat()
            home, away = item["team1"], item["team2"]
            score = item["score"]["ft"]
            if (not isinstance(home, str) or not isinstance(away, str) or not home.strip() or not away.strip() or home == away
                    or not isinstance(score, list) or len(score) != 2
                    or not all(type(goal) is int and 0 <= goal <= 50 for goal in score)):
                raise ValueError("Invalid fixture or explicit full-time score")
            season_start = date(int(season[:4]), 7, 1).isoformat()
            season_end = date(int(season[:4]) + 1, 6, 30).isoformat()
            if not season_start <= day <= season_end:
                raise ValueError("Date outside declared source season")
            key = (league, day, home, away)
            if key in seen:
                raise ValueError("Duplicate fixture")
            seen.add(key)
            result.append({"league": league, "season": season, "date": day, "home": home, "away": away,
                           "home_goals": score[0], "away_goals": score[1]})
        except (KeyError, ValueError, TypeError):
            skipped += 1
    return result, skipped


def resolve_source_ref():
    url = "https://api.github.com/repos/openfootball/football.json/git/ref/heads/master"
    request = Request(url, headers={"User-Agent": "MisterMiResearch/1.0 (+https://github.com/juliomcm-tech/mister-mi)",
                                   "Accept": "application/vnd.github+json"})
    with urlopen(request, timeout=30) as response:
        ref = json.load(response).get("object", {}).get("sha", "")
    if not re.fullmatch(r"[a-f0-9]{40}", ref):
        raise ValueError("Could not resolve immutable upstream commit")
    return ref


def fetch_source(spec):
    league, season, ref = spec
    url = f"https://raw.githubusercontent.com/openfootball/football.json/{ref}/{season}/{league}.json"
    request = Request(url, headers={"User-Agent": "MisterMiResearch/1.0 (+https://github.com/juliomcm-tech/mister-mi)"})
    with urlopen(request, timeout=30) as response:
        raw = response.read(3_000_001)
        if len(raw) > 3_000_000:
            raise ValueError("Source too large")
        etag = response.headers.get("ETag")
    games, skipped = parse_source(raw, league, season)
    return games, {"url": url, "league": league, "season": season,
                   "sha256": sha256(raw).hexdigest(), "size_bytes": len(raw), "etag": etag,
                   "fetched_at": datetime.now(timezone.utc).isoformat(), "included_fulltime_matches": len(games),
                   "excluded_rows": skipped, "license": "CC0-1.0", "license_url": DATA_LICENSE}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="web/data/backtest.json")
    parser.add_argument("--ledger-output", default="docs/backtest-ledger.json")
    parser.add_argument("--source-ref", help="Exact40character upstream Git commit for deterministic replay")
    args = parser.parse_args()
    # Freeze and fingerprint the declared methodology before fetching holdout outcomes.
    config = deepcopy(CONFIG)
    frozen_at = datetime.now(timezone.utc).isoformat()
    config_hash = digest(config)
    script_hash = sha256(Path(__file__).read_bytes()).hexdigest()
    ref = args.source_ref or resolve_source_ref()
    if not re.fullmatch(r"[a-f0-9]{40}", ref):
        raise ValueError("source-ref must be an exact upstream commit SHA")
    specs = [(league, season, ref) for league in LEAGUES for season in (config["training_season"], config["test_season"])]
    games, sources = [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for batch, provenance in pool.map(fetch_source, specs):
            games.extend(batch)
            sources.append(provenance)
    report = walk_forward(games, config)
    predictions, evaluations = report.pop("_prediction_ledger"), report.pop("_evaluation_ledger")
    ledger = {"schema_version": 1, "kind": "experimental_poisson_baseline", "config": config,
              "config_sha256": config_hash, "upstream_commit": ref, "sources": sources,
              "prediction_ledger_sha256": report["prediction_ledger_sha256"],
              "predictions": predictions, "evaluations": evaluations}
    ledger_bytes = (json.dumps(ledger, ensure_ascii=False, indent=2) + "\n").encode()
    ledger_path = Path(args.ledger_output)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_bytes(ledger_bytes)
    payload = {"schema_version": 1, "name": "Mister Mi · laboratório histórico",
               "kind": "experimental_poisson_baseline", "is_live_consensus_backtest": False,
               "production_history_evaluated": 0, "probabilities_are_calibrated": False,
               "method_frozen_at": frozen_at, "config_sha256": config_hash, "config": config,
               "script_sha256": script_hash, "upstream_commit": ref,
               "leagues": LEAGUES, "sources": sources, **report,
               "ledger_artifact": {"path": ledger_path.as_posix(), "sha256": sha256(ledger_bytes).hexdigest(),
                                   "prediction_rows": len(predictions), "evaluation_rows": len(evaluations)},
               "odds_available": False, "roi": None, "kelly_staking": None,
               "limits": [
                   "Este ensaio avalia um modelo Poisson experimental; não mede o desempenho real do consenso OLBG/Forebet/ProTipster.",
                   "Não existem previsões históricas pré-jogo arquivadas dessas fontes nem recomendações de produção liquidadas neste ensaio.",
                   "Simulação cronológica retrospetiva; não é uma experiência prospetiva cega.",
                   "Só resultados anteriores ao dia de previsão entram no modelo; jogos do mesmo dia são previstos em lote.",
                   "Probabilidades do modelo não calibradas; uma taxa de acerto não demonstra rentabilidade nem segurança.",
                   "Sem odds históricas pré-jogo verificadas não se calcula retorno, valor esperado ou Kelly.",
                   "Só duas ligas de futebol e uma época de teste; os resultados não representam ténis, NBA ou hóquei.",
                   "A disponibilidade original e eventuais correções posteriores dos dados históricos não são reconstruídas.",
               ]}
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(path), "overall": payload["overall"], "by_league": payload["by_league"],
                      "training_completed_matches": payload["training_completed_matches"],
                      "test_completed_matches": payload["test_completed_matches"], "warmup_excluded": payload["warmup_excluded"],
                      "prediction_ledger_sha256": payload["prediction_ledger_sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
