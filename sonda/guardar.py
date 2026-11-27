import urllib.request, pathlib
UA = "MisterMi/1.0 (+https://github.com/juliomcm-tech/mister-mi)"
out = pathlib.Path("amostras"); out.mkdir(exist_ok=True)
for name, u in [("zulubet", "https://www.zulubet.com/"), ("vitibet", "https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en"),
                ("statarea", "https://www.statarea.com/predictions"), ("tips180", "https://tips180.com/"), ("prosoccer", "https://www.prosoccer.gr/en/football/predictions/"),
                ("covers_nba", "https://www.covers.com/picks/nba"), ("zulubet_robots", "https://www.zulubet.com/robots.txt"), ("vitibet_robots", "https://www.vitibet.com/robots.txt")]:
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "en"}), timeout=25) as r:
            (out / f"{name}.html").write_bytes(r.read(3_000_000)); print("ok", name)
    except Exception as e: print("falhou", name, e)
