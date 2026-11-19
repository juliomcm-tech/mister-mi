import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from consensus.core import Tip, UTC, LISBON, analyse, team_equal
from consensus.sources import parse_forebet, parse_protipster, SameHostRedirect, FetchError, market_selection
from consensus.history import record, apply_results, metrics, settlement
from urllib.request import Request

NOW = datetime(2026, 11, 19, 12, tzinfo=UTC)


def tip(source="olbg", **changes):
    base = Tip(source, "football", "Porto", "Benfica", "2026-11-19", "2026-11-19T20:00:00Z", "FT_1X2", "HOME",
               "https://example.org/match", NOW.isoformat(), "Portugal Primeira Liga", 80, "vote_pct", 20, 25, 1.8,
               country="Portugal")
    if source == "forebet":
        base = replace(base, metric=72, metric_kind="model_pct", votes_for=0, votes_total=0, odds=1.7)
    if source == "predictz":
        base = replace(base, metric=None, metric_kind="categorical", kickoff=None, votes_for=0, votes_total=0, odds=None)
    return replace(base, **changes)


class ConsensusTests(unittest.TestCase):
    def test_two_sources_same_market_selected(self):
        p = analyse([tip(), tip("forebet")], NOW)
        self.assertEqual(p["total_selected"], 1)
        self.assertFalse(p["score_is_probability"])

    def test_duplicate_pages_are_one_source(self):
        self.assertEqual(analyse([tip(), tip(), tip()], NOW)["total_selected"], 0)

    def test_different_markets_never_confirm_each_other(self):
        self.assertEqual(analyse([tip(), tip("forebet", market="MATCH_WINNER")], NOW)["total_selected"], 0)

    def test_opposing_predictions_refuse_event(self):
        self.assertEqual(analyse([tip(), tip("forebet", outcome="AWAY"), tip("predictz")], NOW)["total_selected"], 0)

    def test_past_stale_and_other_day_are_hidden(self):
        for changed in [dict(kickoff="2026-11-19T11:59:00Z"), dict(fetched_at=(NOW-timedelta(hours=1)).isoformat()),
                        dict(event_date="2026-11-20"), dict(kickoff="2026-11-19T12:04:00Z")]:
            self.assertEqual(analyse([tip(**changed), tip("forebet", **changed)], NOW)["total_selected"], 0)

    def test_lisbon_summer_midnight_uses_local_day(self):
        now = datetime(2026, 7, 1, 23, 5, tzinfo=UTC)
        data = [replace(tip(s), fetched_at=now.isoformat(), event_date="2026-07-02", kickoff="2026-07-01T23:50:00Z") for s in ["olbg", "forebet"]]
        p = analyse(data, now)
        self.assertEqual(p["date"], "2026-07-02")
        self.assertEqual(p["total_selected"], 1)

    def test_lisbon_dst_clock_change_is_timezone_aware(self):
        first = datetime(2026, 10, 25, 0, 30, tzinfo=UTC).astimezone(LISBON)
        second = datetime(2026, 10, 25, 1, 30, tzinfo=UTC).astimezone(LISBON)
        self.assertEqual(first.hour, second.hour)
        self.assertNotEqual(first.utcoffset(), second.utcoffset())

    def test_known_countries_never_cross(self):
        self.assertEqual(analyse([tip(), tip("forebet", country="Brazil")], NOW)["total_selected"], 0)

    def test_gender_and_age_groups_remain_distinct(self):
        self.assertFalse(team_equal("Arsenal W", "Arsenal", "football"))
        self.assertFalse(team_equal("Porto U19", "Porto U21", "football"))

    def test_tennis_initials_do_not_merge_full_names(self):
        self.assertFalse(team_equal("Karolina Pliskova", "Kristyna Pliskova", "tennis"))
        self.assertTrue(team_equal("Ben Shelton", "B. Shelton", "tennis"))

    def test_ambiguous_initial_is_excluded_from_daily_roster(self):
        a = tip(sport="tennis", home="Karolina Pliskova", away="Iga Swiatek", market="MATCH_WINNER")
        b = replace(tip("forebet"), sport="tennis", home="K. Pliskova", away="I. Swiatek", market="MATCH_WINNER")
        c = replace(a, home="Kristyna Pliskova", away="Emma Raducanu")
        self.assertEqual(analyse([a, b, c], NOW)["total_selected"], 0)

    def test_observed_price_is_deterministic_and_conservative(self):
        a = analyse([tip(), tip("forebet")], NOW)["data"][0]
        b = analyse([tip("forebet"), tip()], NOW)["data"][0]
        self.assertEqual(a["odds"], 1.7)
        self.assertEqual((a["id"], a["odds_source"]), (b["id"], b["odds_source"]))

    def test_manual_country_sport_exclusion(self):
        settings = {"excluded_combinations": [{"sport": "football", "country": "Portugal"}]}
        self.assertEqual(analyse([tip(), tip("forebet")], NOW, settings)["total_selected"], 0)

    def test_forebet_uses_selected_probability_and_raw_utc_plus_two(self):
        html = '''<div class="rcnt"><a class="tnmscn" href="/match"><span class="homeTeam">Porto</span><span class="awayTeam">Benfica</span><span class="date_bah">19/11/2026 22:00</span></a><div class="fprc"><span>20</span><span>10</span><span>70</span></div><div class="predict"><span class="forepr">1</span></div></div>'''
        rows, _, _ = parse_forebet(html, "https://www.forebet.com", NOW)
        self.assertEqual(rows[0].metric, 20)
        self.assertEqual(rows[0].kickoff, "2026-11-19T20:00:00+00:00")
        self.assertFalse(rows[0].eligible(analyse([], NOW)["settings"]))

    def test_half_time_and_corners_are_not_full_time_goals(self):
        for label in ["Goals in First Half 2.5", "Total corners 2.5", "Asian Handicap 2.5"]:
            self.assertIsNone(market_selection(label, "Over", "Porto", "Benfica", "football"))

    def test_protipster_odd_is_never_a_tip_score(self):
        html = '''<script>mutation:'TIPS_SECTIONS',args:[{"today":{"picks":[{"hostName":"Porto","opponentName":"Benfica","sportSlug":"football","marketPhrase":"Team to Win","outcome":"1","fixtureDate":"2026-11-19T20:00:00Z","fixtureId":12,"currentRawOdd":8.7}]}}]</script>'''
        rows, _, missing = parse_protipster(html, "https://www.protipster.com", NOW)
        self.assertEqual(missing, 1)
        self.assertIsNone(rows[0].metric)
        self.assertFalse(rows[0].eligible(analyse([], NOW)["settings"]))

    def test_cross_host_redirect_blocked_before_forwarding(self):
        handler = SameHostRedirect()
        with self.assertRaises(FetchError):
            handler.redirect_request(Request("https://api.example.org/", headers={"x-api-key": "secret"}), None, 302, "Found", {}, "https://other.example.org/")

    def test_history_freezes_first_price_and_never_removes_losses(self):
        payload = analyse([tip(), tip("forebet")], NOW)
        h = record({"records": []}, payload)
        payload["data"][0]["odds"] = 2.2
        h = record(h, payload)
        self.assertEqual(h["records"][0]["odds"], 1.7)
        identifier = h["records"][0]["id"]
        apply_results(h, [{"id": identifier, "status": "final", "home_score": 0, "away_score": 2}], NOW + timedelta(days=1))
        h = record(h, {**payload, "data": []})
        self.assertEqual(h["records"][0]["result"], "loss")

    def test_return_only_on_known_odds_voids_and_pending_excluded(self):
        rows = [{"result": "win", "odds": 2}, {"result": "loss", "odds": 2}, {"result": "win", "odds": None}, {"result": "void", "odds": 2}, {"result": "pending", "odds": 2}]
        m = metrics(rows)
        self.assertEqual(m["settled"], 3)
        self.assertEqual(m["priced_settled"], 2)
        self.assertEqual(m["paper_roi_pct"], 0)
        self.assertAlmostEqual(m["hit_rate"], 66.7)

    def test_match_winner_tie_and_boolean_scores_cannot_settle(self):
        pick = {"market": "MATCH_WINNER", "outcome": "HOME"}
        self.assertIsNone(settlement(pick, {"status": "final", "home_score": 1, "away_score": 1}))
        self.assertIsNone(settlement(pick, {"status": "final", "home_score": True, "away_score": 0}))


if __name__ == "__main__":
    unittest.main()
