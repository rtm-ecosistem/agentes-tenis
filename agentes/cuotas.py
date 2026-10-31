"""Cuotas de The Odds API (plan gratis): la cartelera de partidos, la casa con la que se apuesta y el árbitro
(Pinnacle), que llega en la misma consulta sin gastar créditos extra.

Cada consulta de cuotas cuesta [mercados que devuelve] × [regiones]. Se piden las casas por su nombre
(`bookmakers`), y hasta 10 casas cuentan como una sola región: pedir el ganador, el hándicap y el total de juegos
de un torneo cuesta como mucho 3 créditos. La lista de torneos en juego no gasta créditos.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import requests

from agentes import comun, config

CASAS = config.CASAS_ESPANA + [config.ARBITRO]


class SinCreditos(RuntimeError):
    pass


class OddsAPI:
    def __init__(self, clave: str | None = None, sesion=None):
        self.clave = clave or config.secreto("ODDS_API_KEY")
        self.sesion = sesion or requests.Session()
        self.restantes: int | None = None
        self.usados: int | None = None
        self.gastados = 0

    def _get(self, ruta: str, **params) -> list | dict:
        r = self.sesion.get(f"{config.ODDS_API}{ruta}", params={"apiKey": self.clave, **params}, timeout=30)
        cab = r.headers
        if cab.get("x-requests-remaining") is not None:
            try:
                self.restantes = int(float(cab["x-requests-remaining"]))
                self.usados = int(float(cab.get("x-requests-used", 0)))
                self.gastados += int(float(cab.get("x-requests-last", 0)))
            except ValueError:
                pass
        if r.status_code in (401, 429) and "quota" in r.text.lower():
            raise SinCreditos(r.text[:200])
        r.raise_for_status()
        return r.json()

    def torneos(self) -> list[dict]:
        """Los torneos de tenis en juego ahora mismo, solo del circuito principal (no gasta créditos)."""
        return [d for d in self._get("/sports") if es_circuito_principal(d)]

    def cuotas(self, deporte: str, mercados: list[str], casas: list[str] = CASAS,
               desde: datetime | None = None, hasta: datetime | None = None) -> list[dict]:
        params = {"bookmakers": ",".join(casas), "markets": ",".join(mercados), "oddsFormat": "decimal",
                  "dateFormat": "iso"}
        if desde:
            params["commenceTimeFrom"] = desde.strftime("%Y-%m-%dT%H:%M:%SZ")
        if hasta:
            params["commenceTimeTo"] = hasta.strftime("%Y-%m-%dT%H:%M:%SZ")
        return self._get(f"/sports/{deporte}/odds", **params)

    def eventos(self, deporte: str, desde: datetime | None = None, hasta: datetime | None = None) -> list[dict]:
        """Los partidos de un torneo, sin cuotas (no gasta créditos): sirve para no pagar torneos sin partidos."""
        params = {"dateFormat": "iso"}
        if desde:
            params["commenceTimeFrom"] = desde.strftime("%Y-%m-%dT%H:%M:%SZ")
        if hasta:
            params["commenceTimeTo"] = hasta.strftime("%Y-%m-%dT%H:%M:%SZ")
        return self._get(f"/sports/{deporte}/events", **params)

    def marcadores(self, deporte: str, dias: int = 3) -> list[dict]:
        """Resultados de los últimos días (2 créditos): solo se usa si la otra fuente de resultados falla."""
        return self._get(f"/sports/{deporte}/scores", daysFrom=dias, dateFormat="iso")


def es_circuito_principal(deporte: dict) -> bool:
    clave = deporte.get("key", "")
    texto = f"{clave} {deporte.get('title', '')} {deporte.get('description', '')}".lower()
    return (clave.startswith(("tennis_atp", "tennis_wta")) and not deporte.get("has_outrights")
            and deporte.get("active", True) and not any(x in texto for x in config.EXCLUIR_TORNEOS))


# --- Superficie de cada torneo -----------------------------------------------------------------------
TIERRA = ("french_open", "roland", "madrid", "italian", "rome", "monte_carlo", "barcelona", "hamburg", "bastad",
          "kitzbuhel", "gstaad", "umag", "estoril", "munich", "geneva", "lyon", "houston", "marrakech", "rio",
          "buenos_aires", "santiago", "cordoba", "bogota", "charleston", "rabat", "strasbourg", "palermo", "prague",
          "warsaw", "parma", "bucharest", "iasi", "lausanne", "budapest", "rouen", "bad_homburg_clay")
HIERBA = ("wimbledon", "queens", "halle", "eastbourne", "mallorca", "s_hertogenbosch", "hertogenbosch", "stuttgart_grass",
          "berlin", "bad_homburg", "nottingham", "newport", "birmingham")


def superficie(deporte: str, titulo: str = "", fecha: datetime | None = None) -> str:
    """«clay», «grass» o «hard». La mayoría del circuito es pista dura; Stuttgart es tierra (WTA) o hierba (ATP)."""
    texto = f"{deporte} {titulo}".lower().replace(" ", "_").replace("'", "")
    if "stuttgart" in texto:
        return "clay" if "wta" in texto else "grass"
    if any(t in texto for t in HIERBA):
        return "grass"
    if any(t in texto for t in TIERRA):
        return "clay"
    return "hard"


# --- Cartelera ---------------------------------------------------------------------------------------
def seleccion_id(evento: str, mercado: str, nombre: str, punto) -> str:
    return f"{evento}|{mercado}|{nombre}|{'' if punto is None else punto}"


def _mercados_de(casa: dict) -> dict[str, list[dict]]:
    return {m["key"]: m.get("outcomes", []) for m in casa.get("markets", [])}


def precio_en(evento: dict, casa: str, mercado: str, nombre: str, punto) -> float | None:
    for c in evento.get("bookmakers", []):
        if c.get("key") != casa:
            continue
        for o in _mercados_de(c).get(mercado, []):
            if o.get("name") == nombre and (punto is None or o.get("point") == punto):
                return float(o["price"])
    return None


def cobertura(eventos: list[dict]) -> dict[str, int]:
    """Cuántos partidos cubre cada casa española (y cuántos mercados en total, para desempatar)."""
    puntos = {c: 0 for c in config.CASAS_ESPANA}
    for e in eventos:
        for c in e.get("bookmakers", []):
            if c.get("key") in puntos and c.get("markets"):
                puntos[c["key"]] += 1000 + len(c["markets"])
    return puntos


def mercados_por_casa(eventos: list[dict]) -> dict[str, dict[str, int]]:
    """En cuántos partidos da cada casa española cada mercado, para saber qué casa ofrece más."""
    cuenta = {c: {} for c in config.CASAS_ESPANA}
    for e in eventos:
        for c in e.get("bookmakers", []):
            if c.get("key") in cuenta:
                for m in c.get("markets", []):
                    cuenta[c["key"]][m["key"]] = cuenta[c["key"]].get(m["key"], 0) + 1
    return cuenta


def elegir_casa(eventos: list[dict], actual: str | None = None) -> str:
    """La casa española que cubre más partidos de tenis; si están igualadas, William Hill. Una vez elegida se
    mantiene (para comparar a todos con la misma) salvo que otra cubra claramente más partidos, o que se fije otra
    a mano con la variable CASA."""
    if config.CASA_FORZADA in config.CASAS_ESPANA:
        return config.CASA_FORZADA
    puntos = cobertura(eventos)
    mejor = max(puntos.values()) if puntos else 0
    if actual:
        # Se mantiene, salvo que otra cubra claramente más partidos (el doble y al menos 3 más)
        suyos, otra = puntos.get(actual, 0) // 1000, mejor // 1000
        if otra < 2 * suyos or otra - suyos < 3:
            return actual
        nueva = max(puntos, key=lambda c: puntos[c])
        print(f"Cambio de casa: {actual} cubre {suyos} partidos y {nueva} {otra}.")
        return nueva
    if mejor == 0:
        return "williamhill"
    empatadas = [c for c, p in puntos.items() if p // 1000 == mejor // 1000]
    return "williamhill" if "williamhill" in empatadas else max(empatadas, key=lambda c: puntos[c])


def partido(evento: dict, torneo: dict, casa: str) -> dict:
    """Un partido de la cartelera con las opciones de la casa elegida y la cuota de Pinnacle de cada una."""
    inicio = comun.fecha_hora(evento["commence_time"])
    opciones = []
    for c in evento.get("bookmakers", []):
        if c.get("key") != casa:
            continue
        for mercado, salidas in _mercados_de(c).items():
            for o in salidas:
                punto = o.get("point")
                pin = precio_en(evento, config.ARBITRO, mercado, o["name"], punto)
                opciones.append({"id": seleccion_id(evento["id"], mercado, o["name"], punto), "mercado": mercado,
                                 "nombre": o["name"], "punto": punto, "cuota": float(o["price"]), "pinnacle": pin})
    pinnacle_h2h = {o["name"]: o["price"] for c in evento.get("bookmakers", []) if c.get("key") == config.ARBITRO
                    for m in c.get("markets", []) if m["key"] == "h2h" for o in m.get("outcomes", [])}
    return {"id": evento["id"], "deporte": evento.get("sport_key", torneo.get("key")),
            "torneo": torneo.get("title") or evento.get("sport_title", ""), "circuito": "WTA" if "wta" in torneo.get("key", "") else "ATP",
            "superficie": superficie(torneo.get("key", ""), torneo.get("title", ""), inicio),
            "inicio": comun.iso(inicio), "jugadores": [evento["home_team"], evento["away_team"]],
            "opciones": opciones, "pinnacle_h2h": pinnacle_h2h}


def descripcion(opcion: dict, jugadores: list[str] | None = None) -> str:
    """«Alcaraz gana», «Sinner -3.5 juegos», «Más de 22.5 juegos»."""
    m, n, p = opcion["mercado"], opcion["nombre"], opcion.get("punto")
    if m == "h2h":
        return f"{n} gana el partido"
    if m == "spreads":
        return f"{n} {p:+g} juegos" if p is not None else f"{n} (hándicap)"
    if m == "totals":
        return f"{'Más' if n.lower() == 'over' else 'Menos'} de {p:g} juegos" if p is not None else n
    return f"{n} ({config.NOMBRES_MERCADO.get(m, m)})"


def cartelera(api: OddsAPI, estado: dict, mercados: list[str], momento: datetime | None = None) -> list[dict]:
    """Los partidos del circuito principal de las próximas 24 horas, con sus cuotas. Elige la casa si aún no hay."""
    momento = momento or comun.ahora()
    hasta = momento + timedelta(hours=config.HORAS_VENTANA)
    eventos = []
    for t in api.torneos():
        try:
            if not api.eventos(t["key"], desde=momento, hasta=hasta):
                continue  # sin partidos en las próximas horas: no se pagan sus cuotas
            for e in api.cuotas(t["key"], mercados, desde=momento, hasta=hasta):
                eventos.append((e, t))
        except requests.HTTPError as e:
            print(f"No se pudieron leer las cuotas de {t['key']}: {e}")
    estado["cobertura"] = cobertura([e for e, _ in eventos])
    estado["mercados_casas"] = mercados_por_casa([e for e, _ in eventos])
    if eventos:
        estado["casa"] = elegir_casa([e for e, _ in eventos], estado.get("casa"))
    casa = estado.get("casa") or "williamhill"
    partidos = [partido(e, t, casa) for e, t in eventos]
    return sorted(partidos, key=lambda p: p["inicio"])
