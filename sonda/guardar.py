import urllib.request, pathlib
UA = "MisterMi/1.0 (+https://github.com/juliomcm-tech/mister-mi)"
out = pathlib.Path("amostras"); out.mkdir(exist_ok=True)
U = [("espn_soccer_all", "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard?dates=20261126"),
     ("espn_eng1", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard?dates=20261121"),
     ("espn_jpn1", "https://site.api.espn.com/apis/site/v2/sports/soccer/jpn.1/scoreboard?dates=20261120"),
     ("espn_euroleague", "https://site.api.espn.com/apis/site/v2/sports/basketball/euroleague/scoreboard?dates=20261119"),
     ("espn_atp", "https://site.api.espn.com/apis/site/v2/sports/tennis/atp/scoreboard?dates=20261119"),
     ("espn_nba", "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20261126"),
     ("zulubet_26", "https://www.zulubet.com/tips-26-11-2026.html")]
for name, u in U:
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=25) as r:
            b = r.read(4_000_000); (out / f"{name}.txt").write_bytes(b); print("ok", name, r.status, len(b))
    except Exception as e:
        print("falhou", name, e); (out / f"{name}.txt").write_text("ERRO " + str(e))
