import json
import re
import unittest
from datetime import datetime

from consensus.core import UTC, analyse
from consensus.sources import parse_olbg


NOW = datetime(2026, 11, 19, 12, tzinfo=UTC)
URL = "https://www.olbg.com/betting-tips/Football/1"


def public_row(**changes):
    return {
        "id": "community-selection", "selection": "Porto", "market_alias": "Full Time Result",
        "odds": "1.80", "event_start_unix_timestamp": int(datetime(2026, 11, 19, 20, tzinfo=UTC).timestamp()),
        "eventUrl": "/betting-tips/Football/Portugal/Porto_v_Benfica/1?event_id=123",
        "event_name_alias": "Porto v Benfica", "menu_league": "Portugal Primeira Liga",
        "win_tips": 20, "win_tips_count": 25, "confidence": 99, "expired": 0, **changes,
    }


def hydration(items=None, *, literal=None):
    # Match OLBG's public Svelte literal: bare keys, JSON-escaped values.
    if literal is None:
        literal = json.dumps(items)
        literal = re.sub(r'([,{]\s*)"([A-Za-z_]\w*)"\s*:', r"\1\2:", literal)
    return '<script>__sveltekit_test = {}; kit.start(app, element, {data:[{type:"data",data:{tips:' + literal + '}}]});</script>'


DOM = '''<div class="grd tip"><div class="ev"><a itemprop="url" href="/betting-tips/Football/Portugal/Porto_v_Benfica/1?event_id=123"><h5>Porto v Benfica</h5></a><time datetime="2026-11-19T20:00:00Z"></time><p>Portugal Primeira Liga</p></div><div class="sel"><h4>Porto</h4><p>Full Time Result</p></div><div class="odds"><span data-decimal="1.80"></span></div><div class="tips">20/25 Win Tips</div></div>'''


class OlbgCoverageTests(unittest.TestCase):
    def test_public_rows_beyond_initial_render_are_collected_once(self):
        extra = public_row(id="second", selection="Braga", event_name_alias="Braga v Sporting",
                           eventUrl="/betting-tips/Football/Portugal/Braga_v_Sporting/1?event_id=124")
        rows, raw, _ = parse_olbg(DOM + hydration([public_row(), extra]), URL, NOW)
        self.assertEqual((len(rows), raw), (2, 2))
        self.assertEqual({row.home for row in rows}, {"Porto", "Braga"})
        self.assertEqual(rows[0].votes_total, 25)  # Never add HTML and hydration votes.
        self.assertEqual(analyse(rows, NOW)["total_selected"], 0)  # Still only one independent source.

    def test_public_hydration_alone_is_a_valid_page(self):
        rows, raw, _ = parse_olbg(hydration([public_row()]), URL, NOW)
        self.assertEqual((len(rows), raw), (1, 1))
        self.assertEqual((rows[0].metric, rows[0].votes_for, rows[0].votes_total), (80, 20, 25))
        self.assertEqual(rows[0].fetched_at, NOW.isoformat())

    def test_public_confidence_is_not_used_in_place_of_observed_votes(self):
        rows, _, _ = parse_olbg(hydration([public_row(win_tips=1, win_tips_count=20, confidence=99)]), URL, NOW)
        self.assertEqual(rows[0].metric, 5)
        self.assertEqual(analyse(rows, NOW)["total_eligible"], 0)

    def test_unsupported_javascript_falls_back_to_html_without_running(self):
        for literal in ["[window.secret]", "[(()=>{throw Error('executed')})()]", "[{selection:NaN}]",
                        "[{selection:undefined}]", "[{selection:otherVariable}]", "[{}"]:
            with self.subTest(literal=literal):
                rows, raw, _ = parse_olbg(DOM + hydration(literal=literal), URL, NOW)
                self.assertEqual((len(rows), raw), (1, 1))

    def test_escaped_strings_and_brackets_do_not_end_the_literal_early(self):
        item = public_row(menu_league='Portugal "Liga" [A] {selection:x} \\ Test',
                          event_name_alias="Porto v Benfica", unused="\u300c intelligence \u300d")
        rows, _, _ = parse_olbg(hydration([item]), URL, NOW)
        self.assertEqual(rows[0].competition, item["menu_league"])

    def test_dates_use_explicit_epoch_instant_and_current_lisbon_day(self):
        stamp = int(datetime(2026, 7, 1, 23, 30, tzinfo=UTC).timestamp())
        rows, _, _ = parse_olbg(hydration([public_row(event_start_unix_timestamp=stamp)]), URL, NOW)
        self.assertEqual(rows[0].event_date, "2026-07-02")
        self.assertEqual(rows[0].kickoff, "2026-07-01T23:30:00+00:00")
        self.assertEqual(analyse(rows, NOW)["total_selected"], 0)

    def test_malformed_votes_dates_and_wrong_hosts_are_never_accepted(self):
        invalid = [public_row(event_start_unix_timestamp=None), public_row(event_start_unix_timestamp=True),
                   public_row(event_start_unix_timestamp="2026-11-19"), public_row(win_tips=30),
                   public_row(win_tips_count=0), public_row(win_tips=True), public_row(win_tips_count="25"),
                   public_row(eventUrl="https://evil.example/betting-tips/Football/Porto_v_Benfica/1"),
                   public_row(eventUrl="https://www.olbg.com.evil.example/betting-tips/Football/X/1"),
                   public_row(eventUrl="https://www.olbg.com/search?q=/betting-tips/Football/"),
                   public_row(eventUrl="http://www.olbg.com/betting-tips/Football/X/1")]
        missing = public_row()
        del missing["win_tips_count"]
        rows, raw, _ = parse_olbg(hydration(invalid + [missing]), URL, NOW)
        self.assertEqual(len(rows), 0)
        self.assertEqual(raw, len(invalid) + 1)

    def test_expired_cancelled_postponed_and_unsupported_markets_are_skipped(self):
        items = [public_row(expired=1), public_row(cancelled=True), public_row(postponed=True),
                 public_row(market_alias="Result and BTTS"), public_row(market_alias="Goals in First Half 2.5", selection="Over")]
        self.assertEqual(parse_olbg(hydration(items), URL, NOW)[0], [])

    def test_public_cancelled_or_expired_status_invalidates_rendered_duplicate(self):
        for changes in [{"expired": 1}, {"cancelled": True}, {"postponed": True}]:
            with self.subTest(changes=changes):
                rows, raw, _ = parse_olbg(DOM + hydration([public_row(**changes)]), URL, NOW)
                self.assertEqual((len(rows), raw), (0, 1))

    def test_cancelled_public_status_still_blocks_html_with_missing_public_votes(self):
        item = public_row(cancelled=True)
        del item["win_tips_count"]
        rows, raw, _ = parse_olbg(DOM + hydration([item]), URL, NOW)
        self.assertEqual((len(rows), raw), (0, 1))

    def test_conflicting_public_statuses_fail_closed_in_either_order(self):
        for items in [[public_row(), public_row(expired=1)], [public_row(expired=1), public_row()]]:
            rows, raw, _ = parse_olbg(DOM + hydration(items), URL, NOW)
            self.assertEqual((len(rows), raw), (0, 2))

    def test_gender_and_country_stay_in_unique_identity(self):
        items = [public_row(), public_row(menu_league="Brazil Primeira Liga"), public_row(menu_league="Portugal Women")]
        rows, raw, _ = parse_olbg(hydration(items), URL, NOW)
        self.assertEqual((len(rows), raw), (3, 3))
        self.assertEqual({row.country for row in rows}, {"Portugal", "Brazil"})
        self.assertEqual({row.segment for row in rows}, {"open", "w"})

    def test_raw_rows_include_unsupported_dom_fallback_once(self):
        html = DOM.replace("Full Time Result", "Result and BTTS")
        rows, raw, _ = parse_olbg(html + hydration([public_row(market_alias="Result and BTTS")]), URL, NOW)
        self.assertEqual((len(rows), raw), (0, 1))

    def test_money_line_reverses_visitor_at_host_consistently(self):
        item = public_row(eventUrl="/betting-tips/Basketball/NBA/Visitors_@_Hosts/4", event_name_alias="Visitors @ Hosts",
                          selection="Hosts", market_alias="Money Line")
        row = parse_olbg(hydration([item]), URL, NOW)[0][0]
        self.assertEqual((row.sport, row.home, row.away, row.market, row.outcome),
                         ("basketball", "Hosts", "Visitors", "MATCH_WINNER", "HOME"))

    def test_missing_league_on_tennis_data_does_not_drop_a_valid_match(self):
        item = public_row(eventUrl="/betting-tips/Tennis/All_Tennis/All_Events/Alexander_Zverev_v_Arthur_Fils/3",
                          event_name_alias="Alexander Zverev v Arthur Fils", selection="Alexander Zverev",
                          market_alias="Win Match", menu_league=None)
        rows, raw, _ = parse_olbg(hydration([item]), URL, NOW)
        self.assertEqual((len(rows), raw, rows[0].competition, rows[0].sport), (1, 1, "", "tennis"))

    def test_hydration_is_bounded_and_does_not_turn_unrelated_json_into_tips(self):
        unrelated = '<script>const data = {tips:' + json.dumps([public_row()]) + '};</script>'
        rows, raw, _ = parse_olbg(DOM + unrelated, URL, NOW)
        self.assertEqual((len(rows), raw), (1, 1))
        rows, raw, _ = parse_olbg(DOM + hydration([public_row()] * 1001), URL, NOW)
        self.assertEqual((len(rows), raw), (1, 1))


if __name__ == "__main__":
    unittest.main()
