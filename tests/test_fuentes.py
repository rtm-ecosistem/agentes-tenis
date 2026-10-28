import io

from agentes import comun, cuotas, elo, noticias, resultados

ESPN = {"events": [{"name": "Rolex Paris Masters", "groupings": [
    {"grouping": {"slug": "mens-singles"}, "competitions": [
        {"date": "2026-10-29T13:00Z", "status": {"type": {"completed": True, "description": "Final", "state": "post"}},
         "competitors": [{"athlete": {"displayName": "Carlos Alcaraz"}, "winner": False, "linescores": [{"value": 4}, {"value": 6}, {"value": 6}]},
                         {"athlete": {"displayName": "Alex de Minaur"}, "winner": True, "linescores": [{"value": 6}, {"value": 3}, {"value": 7}]}]},
        {"date": "2026-10-29T15:00Z", "status": {"type": {"completed": True, "description": "Retired", "state": "post"}},
         "competitors": [{"athlete": {"displayName": "Jannik Sinner"}, "winner": True, "linescores": [{"value": 3}]},
                         {"athlete": {"displayName": "Casper Ruud"}, "winner": False, "linescores": [{"value": 1}]}]},
        {"date": "2026-10-29T17:00Z", "status": {"type": {"completed": False, "state": "in"}},
         "competitors": [{"athlete": {"displayName": "A B"}}, {"athlete": {"displayName": "C D"}}]}]},
    {"grouping": {"slug": "mens-doubles"}, "competitions": []}]}]}


def test_espn():
    p = resultados.leer_espn(ESPN)
    assert len(p) == 2
    assert p[0]["ganador"] == 1 and p[0]["sets"] == [[4, 6], [6, 3], [6, 7]] and p[0]["completo"]
    assert not p[1]["completo"]
    apuesta = {"partido": "x", "jugadores": ["Alex de Minaur", "Carlos Alcaraz"], "inicio": "2026-10-29T12:00+00:00"}
    r = resultados.buscar(apuesta, p)
    assert r["jugadores"][0] == "Carlos Alcaraz"  # la apuesta liquida por nombre, no por posición
    assert "Ganó Alex de Minaur (4-6 6-3 6-7)" == resultados.texto(r)


def test_odds_api_marcador():
    p = resultados.leer_odds_api([{"id": "e1", "completed": True, "commence_time": "2026-10-29T12:00:00Z",
                                   "home_team": "A B", "away_team": "C D",
                                   "scores": [{"name": "A B", "score": "1"}, {"name": "C D", "score": "2"}]}])
    assert p[0]["ganador"] == 1 and p[0]["sets"] == []


def test_circuito_principal():
    assert cuotas.es_circuito_principal({"key": "tennis_atp_paris_masters", "title": "ATP Paris Masters", "active": True})
    assert not cuotas.es_circuito_principal({"key": "tennis_atp_challenger_x", "title": "Challenger", "active": True})
    assert not cuotas.es_circuito_principal({"key": "tennis_wta_125_x", "title": "WTA 125", "active": True})
    assert not cuotas.es_circuito_principal({"key": "soccer_epl", "title": "EPL", "active": True})


def test_superficie():
    assert cuotas.superficie("tennis_atp_french_open") == "clay"
    assert cuotas.superficie("tennis_atp_wimbledon") == "grass"
    assert cuotas.superficie("tennis_wta_stuttgart_open") == "clay"
    assert cuotas.superficie("tennis_atp_paris_masters") == "hard"


def test_elegir_casa():
    def ev(*casas):
        return {"bookmakers": [{"key": c, "markets": [{"key": "h2h"}]} for c in casas]}
    assert cuotas.elegir_casa([ev("betsson", "sport888"), ev("sport888")]) == "sport888"
    assert cuotas.elegir_casa([ev("betsson", "williamhill")]) == "williamhill"  # empate: William Hill
    assert cuotas.elegir_casa([ev("betsson")], actual="sport888") == "sport888"  # una vez elegida, se mantiene


def test_nombres():
    assert comun.clave_abreviada("De Minaur A.") in comun.claves_completas("Alex de Minaur")
    assert comun.clave_abreviada("Auger-Aliassime F.") in comun.claves_completas("Félix Auger-Aliassime")
    assert comun.mismo_jugador("Carlos Alcaraz", "Carlos Alcaraz Garfia")
    assert not comun.mismo_jugador("Carlos Alcaraz", "Carlos Taberner")


def test_elo_por_superficie():
    partidos = [{"fecha": f"{2000 + i}-05-10", "superficie": "clay", "ganador": "nadal|r", "perdedor": "sinner|j",
                 "nombres": ["Nadal R.", "Sinner J."]} for i in range(15)]
    partidos += [{"fecha": "2026-06-01", "superficie": "hard", "ganador": "sinner|j", "perdedor": "nadal|r",
                  "nombres": ["Sinner J.", "Nadal R."]}]
    e = elo.calcular(partidos)
    tierra = elo.probabilidad(e, "Rafael Nadal", "Jannik Sinner", "clay")
    dura = elo.probabilidad(e, "Rafael Nadal", "Jannik Sinner", "hard")
    assert tierra["prob"] > dura["prob"] > 0.5
    assert tierra["h2h"] == [15, 1]


def test_elo_tennis_data():
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["ATP", "Location", "Tournament", "Date", "Surface", "Winner", "Loser", "Comment"])
    ws.append([1, "Paris", "Paris Masters", "2026-10-28", "Hard", "Alcaraz C.", "De Minaur A.", "Completed"])
    ws.append([1, "Paris", "Paris Masters", "2026-10-28", "Hard", "Sinner J.", "Ruud C.", "Walkover"])
    f = io.BytesIO()
    wb.save(f)
    p = elo.leer_tennis_data(f.getvalue(), "ATP")
    assert len(p) == 1 and p[0]["ganador"] == "alcaraz|c" and p[0]["perdedor"] == "de minaur|a"


def test_rss():
    xml = """<rss><channel><item><title>Alcaraz, baja en París</title><link>https://x/1</link>
    <pubDate>Wed, 28 Oct 2026 10:00:00 GMT</pubDate><description>&lt;p&gt;Lesión en el pie&lt;/p&gt;</description></item></channel></rss>"""
    n = noticias.leer_rss(xml, "Punto de Break")
    assert n[0]["titulo"] == "Alcaraz, baja en París" and n[0]["resumen"] == "Lesión en el pie"
    assert noticias.de_jugador({"noticias": n}, "Carlos Alcaraz") == n
    assert noticias.de_jugador({"noticias": n}, "Jannik Sinner") == []


def test_rss_con_ampersand_suelto():
    xml = "<rss><channel><item><title>Djokovic & Sinner</title><link>https://x/2?a=1&b=2</link></item></channel></rss>"
    assert noticias.leer_rss(xml, "X")[0]["titulo"] == "Djokovic & Sinner"


def test_historial_de_resultados(monkeypatch):
    from datetime import datetime, timezone
    llamadas = []
    monkeypatch.setattr(resultados, "descargar_espn", lambda dia, sesion=None: llamadas.append(dia) or [
        {"jugadores": ["A B", "C " + "abcdefghijklmnopqrstuvwxyzab"[dia.day] * 3], "ganador": 0, "sets": [[6, 1]], "completo": True, "fecha": dia.isoformat(), "torneo": "Roland Garros"}])
    momento = datetime(2026, 10, 28, tzinfo=timezone.utc)
    resultados.rellenar(momento, maximo=5)
    resultados.rellenar(momento, maximo=5)
    assert len(llamadas) == 10 and len(set(llamadas)) == 10  # no repite días ya leídos
    assert len(resultados.historial()["partidos"]) == 10
    e = elo.calcular(elo.de_resultados(resultados.historial()["partidos"], {}))
    assert e["jugadores"]["b|a"]["n"]["clay"] == 10
