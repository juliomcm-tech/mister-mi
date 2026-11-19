import json
import unittest
from dataclasses import replace
from consensus.extra_predictions import Fixture, parse_index, parse_detail, safe_url
from consensus.core import analyse, UTC
from test_consensus import NOW, tip


URL = 'https://www.betclan.com/tennis/predictionsdetails/12/Zverev-vs-Fils/'
F = Fixture('tennis', 'Alexander Zverev', 'Arthur Fils', '2026-11-19T19:30:00+00:00', '2026-11-19', URL, 'ATP Finals')


def detail(f=F, selected='Alexander Zverev', scores=(('Alexander Zverev', 75), ('Arthur Fils', 25)), **changes):
    event = {'@type':'SportsEvent','url':f.url,'homeTeam':{'name':f.home},'awayTeam':{'name':f.away},
             'startDate':f.kickoff,'eventStatus':'https://schema.org/EventScheduled',**changes}
    stats=''.join(f'<div class="cell__section"><div class="vote__count">{name}</div><span class="vote__pct">{p}%</span></div>' for name,p in scores)
    return f'<script type="application/ld+json">{json.dumps(event)}</script><div class="partone"><h4>Winner</h4><h5>{selected}</h5><div class="vote__stats">{stats}</div></div><div class="useraverage">99%</div>'


class BetClanTests(unittest.TestCase):
    def test_only_selected_model_probability_is_used_and_users_average_is_ignored(self):
        rows=parse_detail(detail(selected='Arthur Fils'), F, NOW)
        self.assertEqual((rows[0].outcome,rows[0].metric),('AWAY',25))
        self.assertFalse(rows[0].eligible(analyse([],NOW)['settings']))

    def test_real_second_source_can_confirm_without_relaxing_the_rules(self):
        a=replace(tip(),sport='tennis',home=F.home,away=F.away,kickoff=F.kickoff,market='MATCH_WINNER',competition=F.competition,country='Desconhecido')
        result=analyse([a,*parse_detail(detail(),F,NOW)],NOW)
        self.assertEqual(result['total_selected'],1)
        self.assertEqual(result['data'][0]['source_count'],2)
        self.assertEqual(result['settings']['min_votes'],15)

    def test_index_time_conflict_cannot_become_a_timed_anchor(self):
        rows=parse_detail(detail(startDate='2026-11-19T19:30:00+01:00'),F,NOW)
        self.assertEqual(len(rows),1)
        self.assertIsNone(rows[0].kickoff)
        self.assertEqual(analyse(rows,NOW)['data'],[])

    def test_other_day_inactive_identity_or_percentage_conflicts_fail_closed(self):
        for changes in [{'startDate':'2026-11-20T19:30:00Z'},{'eventStatus':'https://schema.org/EventCancelled'},
                        {'homeTeam':{'name':'Wrong Player'}},{'url':'https://evil.example/match'}]:
            self.assertEqual(parse_detail(detail(**changes),F,NOW),[])
        self.assertEqual(parse_detail(detail(scores=(('Alexander Zverev',75),('Arthur Fils',75))),F,NOW),[])

    def test_only_known_index_template_typo_is_accepted_without_executing_code(self):
        row={'@type':'SportsEvent','url':F.url,'homeTeam':{'name':F.home},'awayTeam':{'name':F.away},'startDate':F.kickoff}
        html=f'<script type="application/ld+json">{json.dumps(row)}}}</script>'
        rows,_=parse_index(html,'https://www.betclan.com/todays-tennis-predictions/')
        self.assertEqual(rows[0].home,F.home)
        bad=html.replace('}</script>','; alert(1)</script>')
        self.assertEqual(parse_index(bad,'https://www.betclan.com/todays-tennis-predictions/')[0],[])

    def test_url_scope_and_unicode_encoding(self):
        self.assertIn('M%C3%BCnchen',safe_url('/predictionsdetails/football/1/München/'))
        for url in ['https://evil.example/path','http://www.betclan.com/path','https://www.betclan.com.evil.example/path']:
            with self.assertRaises(ValueError):safe_url(url)


if __name__=='__main__':unittest.main()
