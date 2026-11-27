"""Sonda única: que sites de prognósticos respondem ao robô (a partir do GitHub Actions) e se o robots.txt o permite."""
import re, urllib.request, urllib.robotparser, urllib.parse
UA = "MisterMi/1.0 (+https://github.com/juliomcm-tech/mister-mi)"
URLS = [
 "https://www.forebet.com/en/football-tips-and-predictions-for-today",
 "https://www.predictz.com/predictions/today/",
 "https://www.windrawwin.com/predictions/today/",
 "https://www.zulubet.com/",
 "https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en",
 "https://www.statarea.com/predictions",
 "https://www.soccervista.com/",
 "https://footystats.org/predictions/",
 "https://www.betensured.com/predictions",
 "https://tips180.com/",
 "https://www.sportytrader.com/en/betting-tips/football/",
 "https://www.prosoccer.gr/en/football/predictions/",
 "https://www.betshoot.com/football/",
 "https://www.footballpredictions.com/footballpredictions/",
 "https://www.feedinco.com/",
 "https://www.bettingclosed.com/predictions/date-matches/today/",
 "https://www.mybets.today/soccer-predictions/",
 "https://www.scores24.live/en/soccer/predictions",
 "https://www.betclan.com/todays-football-predictions/",
 "https://www.olbg.com/betting-tips/Football/1",
 "https://www.protipster.com/betting-tips/football",
 "https://www.academiadasapostas.com/stats/livescores",
 "https://www.oddsportal.com/",
 "https://www.betexplorer.com/",
 "https://www.goal.com/en/betting-tips",
 "https://www.covers.com/picks/nba",
 "https://www.dunkel.com/",
 "https://www.tennisexplorer.com/matches/",
]
def robots_ok(u):
    p = urllib.parse.urlparse(u); r = urllib.robotparser.RobotFileParser(); r.set_url(f"{p.scheme}://{p.netloc}/robots.txt")
    try: r.read(); return r.can_fetch(UA, u)
    except Exception as e: return f"? {type(e).__name__}"
for u in URLS:
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en"})
        with urllib.request.urlopen(req, timeout=20) as r:
            b = r.read(1_500_000).decode("utf-8", "replace"); st = r.status
    except urllib.error.HTTPError as e: st, b = e.code, ""
    except Exception as e: st, b = type(e).__name__, ""
    pct = len(re.findall(r"\b\d{1,3}\s?%", b)); tm = len(re.findall(r"\b[0-2]\d:[0-5]\d\b", b)); vs = len(re.findall(r"\bvs\.?\b| v | - ", b))
    chal = bool(re.search(r"cf-chl|challenge-platform|Just a moment|captcha", b, re.I))
    print(f"SONDA | {st} | robots={robots_ok(u)} | {len(b)//1024} KB | %={pct} horas={tm} desafio={chal} | {u}")
