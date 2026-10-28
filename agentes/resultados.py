"""Resultados de los partidos, con los juegos de cada set para liquidar el hándicap y el total de juegos.

La fuente principal es el marcador público de ESPN (gratis, sin clave). Si un partido no aparece allí en dos días,
se mira el marcador de The Odds API, que solo da el ganador (2 créditos por torneo), y con él se liquida al menos
el ganador del partido.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import requests

from agentes import comun, config

ESPN = "https://site.api.espn.com/apis/site/v2/sports/tennis/{circuito}/scoreboard"
ACABADO = ("final", "post", "completed")
INCOMPLETO = ("retired", "ret", "walkover", "w/o", "abandoned", "default", "cancel", "postponed", "suspended")


def _estado(comp: dict) -> tuple[bool, bool, str]:
    """(terminado, completo, texto). Terminado con retirada o walkover = terminado pero no completo."""
    tipo = (comp.get("status") or {}).get("type") or {}
    texto = " ".join(str(tipo.get(k, "")) for k in ("name", "description", "detail", "shortDetail")).lower()
    incompleto = any(x in texto for x in INCOMPLETO)
    terminado = bool(tipo.get("completed")) or tipo.get("state") == "post" or any(x in texto for x in ACABADO) or incompleto
    return terminado, terminado and not incompleto, texto.strip()


def leer_espn(datos: dict) -> list[dict]:
    """Los partidos individuales terminados del marcador de ESPN."""
    partidos = []
    for ev in datos.get("events", []):
        torneo = ev.get("name") or ev.get("shortName") or ""
        grupos = ev.get("groupings") or [{"competitions": ev.get("competitions", [])}]
        for g in grupos:
            slug = ((g.get("grouping") or {}).get("slug") or "").lower()
            if "doubles" in slug:
                continue
            for comp in g.get("competitions", []):
                terminado, completo, texto = _estado(comp)
                rivales = comp.get("competitors", [])
                if not terminado or len(rivales) != 2:
                    continue
                nombres = [((c.get("athlete") or {}).get("displayName") or (c.get("athlete") or {}).get("fullName")
                            or c.get("name") or "") for c in rivales]
                if not all(nombres) or any("/" in n for n in nombres):
                    continue
                lineas = [[int(float(s.get("value", 0) or 0)) for s in c.get("linescores", [])] for c in rivales]
                sets = [[a, b] for a, b in zip(*lineas)] if all(lineas) else []
                ganador = 0 if rivales[0].get("winner") else 1 if rivales[1].get("winner") else None
                if ganador is None and sets:
                    ganados = [sum(1 for s in sets if s[i] > s[1 - i]) for i in (0, 1)]
                    ganador = 0 if ganados[0] > ganados[1] else 1
                partidos.append({"jugadores": nombres, "ganador": ganador, "sets": sets, "completo": completo and ganador is not None,
                                 "torneo": torneo, "fecha": (comp.get("date") or ev.get("date") or "")[:10],
                                 "estado": texto, "fuente": "ESPN"})
    return partidos


def descargar_espn(dia: date, sesion=None) -> list[dict]:
    sesion = sesion or requests
    partidos = []
    for circuito in ("atp", "wta"):
        try:
            r = sesion.get(ESPN.format(circuito=circuito), params={"dates": dia.strftime("%Y%m%d")}, timeout=30)
            r.raise_for_status()
            for p in leer_espn(r.json()):
                partidos.append({**p, "circuito": circuito.upper()})
        except (requests.RequestException, ValueError) as e:
            print(f"No se pudo leer el marcador de ESPN ({circuito}, {dia}): {e}")
    return partidos


def leer_odds_api(eventos: list[dict]) -> list[dict]:
    """Del marcador de The Odds API solo se saca el ganador (cuenta sets, no juegos)."""
    partidos = []
    for e in eventos:
        if not e.get("completed") or not e.get("scores"):
            continue
        puntos = {s["name"]: float(s.get("score") or 0) for s in e["scores"]}
        jug = [e["home_team"], e["away_team"]]
        if jug[0] not in puntos or jug[1] not in puntos or puntos[jug[0]] == puntos[jug[1]]:
            continue
        partidos.append({"jugadores": jug, "ganador": 0 if puntos[jug[0]] > puntos[jug[1]] else 1, "sets": [],
                         "completo": True, "id": e["id"], "fecha": e["commence_time"][:10], "fuente": "The Odds API"})
    return partidos


def buscar(apuesta: dict, partidos: list[dict]) -> dict | None:
    """El resultado del partido de la apuesta: mismo par de jugadores y fecha cercana."""
    a, b = apuesta["jugadores"]
    inicio = comun.fecha_hora(apuesta["inicio"]).date()
    for p in partidos:
        if p.get("id") == apuesta["partido"]:
            return p
        if p.get("fecha"):
            try:
                if abs((date.fromisoformat(p["fecha"]) - inicio).days) > 2:
                    continue
            except ValueError:
                pass
        x, y = p["jugadores"]
        if comun.mismo_jugador(a, x) and comun.mismo_jugador(b, y):
            return p
        if comun.mismo_jugador(a, y) and comun.mismo_jugador(b, x):
            # Mismo partido con los jugadores al revés: se ponen en el orden de la apuesta
            return {**p, "jugadores": [x, y]}
    return None


def texto(resultado: dict) -> str:
    j = resultado["jugadores"]
    marcador = " ".join(f"{s[0]}-{s[1]}" for s in resultado.get("sets", []))
    if not resultado.get("completo"):
        return f"{j[0]} – {j[1]}: no se completó ({resultado.get('estado') or 'retirada'}) · apuesta anulada"
    ganador = j[resultado["ganador"]]
    return f"Ganó {ganador}" + (f" ({marcador})" if marcador else "")


def dias_a_mirar(pendientes: list[dict], momento: datetime) -> list[date]:
    """Los días (en hora de EE. UU., la de ESPN) en que se jugaron los partidos pendientes ya empezados."""
    dias = set()
    for a in pendientes:
        inicio = comun.fecha_hora(a["inicio"])
        if inicio > momento:
            continue
        for d in (-1, 0, 1):
            dia = (inicio + timedelta(days=d)).date()
            if dia <= momento.date():
                dias.add(dia)
    return sorted(dias)


def recientes(momento: datetime, dias: int = 2) -> list[date]:
    return [(momento - timedelta(days=d)).date() for d in range(dias, -1, -1)]


def guardar_historial(partidos: list[dict]) -> None:
    """Se guardan los resultados (solo datos de tenis públicos) para ir actualizando el Elo."""
    previos = comun.leer(config.RESULTADOS, [])
    vistos = {(p["fecha"], *sorted(p["jugadores"])) for p in previos}
    for p in partidos:
        k = (p.get("fecha", ""), *sorted(p["jugadores"]))
        if p.get("sets") and k not in vistos:
            vistos.add(k)
            previos.append({c: p.get(c) for c in ("fecha", "torneo", "circuito", "jugadores", "ganador", "sets", "completo")})
    comun.guardar(config.RESULTADOS, previos[-6000:])
