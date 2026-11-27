import urllib.request, urllib.robotparser, urllib.parse, pathlib, re
UA = "MisterMi/1.0 (+https://github.com/juliomcm-tech/mister-mi)"
out = pathlib.Path("amostras"); out.mkdir(exist_ok=True)
U = [("statarea", "https://www.statarea.com/olddevices/prediction/2026-11-27/"),
     ("statarea_top10", "https://www.statarea.com/olddevices/top10/2026-11-27/"),
     ("vitibet_old", "https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en&design_version=old"),
     ("prosoccer", "https://www.prosoccer.gr/en/football/predictions/"),
     ("sporticos", "https://sporticos.com/en-gb/predictions/win-draw-win"),
     ("typersi", "https://typersi.pl/"),
     ("dimers_nba", "https://www.dimers.com/nba/predictions"),
     ("scoresandodds_nba", "https://www.scoresandodds.com/nba/consensus-picks"),
     ("cbs_nfl", "https://www.cbssports.com/nfl/picks/experts/straight-up/13/"),
     ("ruedesjoueurs", "https://www.ruedesjoueurs.com/pronostics/football.html"),
     ("fpnet", "https://footballpredictions.net/football-predictions-free-betting-tips"),
     ("vprognoze", "https://vprognoze.ru/forecast/today/"),
     ("scoutingstats", "https://scoutingstats.ai/predictions/today/1x2"),
     ("bettingexpert", "https://www.bettingexpert.com/tips/index")]
def robots(u):
    p = urllib.parse.urlparse(u); r = urllib.robotparser.RobotFileParser()
    try:
        with urllib.request.urlopen(urllib.request.Request(f"{p.scheme}://{p.netloc}/robots.txt", headers={"User-Agent": UA}), timeout=15) as x:
            r.parse(x.read().decode("utf-8", "replace").splitlines())
        return r.can_fetch(UA, u)
    except urllib.error.HTTPError as e:
        return "sem robots (livre)" if e.code in (404, 410) else f"robots HTTP {e.code}"
    except Exception as e: return f"? {type(e).__name__}"
for name, u in U:
    st, b = "?", b""
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "en"}), timeout=25) as r:
            b = r.read(4_000_000); st = r.status
    except urllib.error.HTTPError as e: st = e.code
    except Exception as e: st = type(e).__name__
    t = b.decode("utf-8", "replace")
    chal = bool(re.search(r"cf-chl|challenge-platform|Just a moment|captcha", t, re.I))
    hoje = bool(re.search(r"27[./-]11[./-]2026|2026-11-27|27 Nov|Nov 27|November 27", t))
    print(f"SONDA | {name} | {st} | robots={robots(u)} | {len(t)//1024} KB | %={len(re.findall(r'\d{1,3}\s?%', t))} | desafio={chal} | hoje={hoje}")
    (out / f"{name}.txt").write_bytes(b or b"")
