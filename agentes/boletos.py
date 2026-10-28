"""Los botes y los boletos: el control de riesgo, la liquidación y la cuota de cierre de Pinnacle.

Las reglas son fijas y se aplican digan lo que digan los analistas: del 1 % al 3 % del bote por apuesta, como
mucho el 10 % del bote pendiente a la vez, nada de combinadas ni de directo (solo se apuesta a partidos que aún
no han empezado, con la cuota que había en la consulta).
"""

from __future__ import annotations

from datetime import datetime

from agentes import comun, config, cuotas


def bote_nuevo() -> dict:
    return {"saldo": config.BOTE_INICIAL, "inicial": config.BOTE_INICIAL, "maximo": config.BOTE_INICIAL}


def pendientes(apuestas: list[dict], agente: str, bote: str | None = None) -> list[dict]:
    return [a for a in apuestas if a["agente"] == agente and a["estado"] == "pendiente"
            and (bote is None or a["bote"] == bote)]


def valor_bote(bote: dict, apuestas_pendientes: list[dict]) -> float:
    """Lo que vale el bote: el saldo libre más lo que hay en juego (a precio de compra)."""
    return bote["saldo"] + sum(a["stake"] for a in apuestas_pendientes)


def margen(agente: dict, apuestas: list[dict], bote_id: str) -> dict:
    """Las cuentas de los límites hechas de antemano, para que el analista sepa cuánto puede apostar."""
    bote = agente["botes"][bote_id]
    pend = pendientes(apuestas, agente["id"], bote_id)
    valor = valor_bote(bote, pend)
    en_juego = sum(a["stake"] for a in pend)
    libre = max(0.0, min(config.MAX_PENDIENTE * valor - en_juego, bote["saldo"]))
    return {"valor": valor, "en_juego": en_juego, "libre": libre,
            "stakes": {c: round(p * valor, 2) for c, p in config.STAKE_POR_CONFIANZA.items()}}


def validar(agente: dict, apuestas: list[dict], bote_id: str, propuestas: list[dict], cartelera: list[dict],
            momento: datetime, fecha: str) -> tuple[list[dict], list[str]]:
    """Convierte las propuestas del analista en boletos que cumplen las reglas. Devuelve (boletos, rechazos)."""
    opciones = {o["id"]: (p, o) for p in cartelera for o in p["opciones"]}
    mercados = set(config.BOTES[bote_id]["mercados"])
    m = margen(agente, apuestas, bote_id)
    libre, nuevos, rechazos, partidos_usados = m["libre"], [], [], set()
    ya = {(a["partido"], a["mercado"]) for a in pendientes(apuestas, agente["id"], bote_id)}
    for prop in propuestas:
        sel = str(prop.get("seleccion", ""))
        if sel not in opciones:
            rechazos.append(f"«{sel[:60]}» no está en la cartelera")
            continue
        p, o = opciones[sel]
        if o["mercado"] not in mercados:
            rechazos.append(f"{cuotas.descripcion(o)}: ese mercado no es de este bote")
            continue
        if comun.fecha_hora(p["inicio"]) <= momento:
            rechazos.append(f"{cuotas.descripcion(o)}: el partido ya ha empezado (nada de apuestas en directo)")
            continue
        if (p["id"], o["mercado"]) in ya or (p["id"], o["mercado"]) in partidos_usados:
            rechazos.append(f"{cuotas.descripcion(o)}: ya hay una apuesta a ese mercado de ese partido")
            continue
        if not config.CUOTA_MIN <= o["cuota"] <= config.CUOTA_MAX:
            rechazos.append(f"{cuotas.descripcion(o)}: cuota {o['cuota']} fuera del rango permitido")
            continue
        try:
            confianza = min(3, max(1, int(prop.get("confianza", 1))))
        except (TypeError, ValueError):
            confianza = 1
        stake = round(min(config.STAKE_POR_CONFIANZA[confianza] * m["valor"], config.MAX_STAKE * m["valor"]), 2)
        if stake > libre:
            stake = round(libre, 2)
            if stake < max(config.MIN_STAKE_EUR, config.STAKE_POR_CONFIANZA[1] * m["valor"] * 0.5):
                rechazos.append(f"{cuotas.descripcion(o)}: ya tiene el {config.MAX_PENDIENTE:.0%} del bote en juego")
                continue
        libre -= stake
        partidos_usados.add((p["id"], o["mercado"]))
        nuevos.append({
            "id": f"{fecha}-{agente['id']}-{bote_id}-{len(nuevos) + 1}-{p['id'][:8]}",
            "agente": agente["id"], "bote": bote_id, "fecha": fecha, "hora": comun.iso(momento),
            "partido": p["id"], "deporte": p["deporte"], "torneo": p["torneo"], "superficie": p["superficie"],
            "jugadores": p["jugadores"], "inicio": p["inicio"], "mercado": o["mercado"], "seleccion": o["nombre"],
            "punto": o["punto"], "descripcion": cuotas.descripcion(o), "cuota": o["cuota"], "casa": p.get("casa"),
            "pinnacle_apuesta": o.get("pinnacle"), "pinnacle_cierre": None, "confianza": confianza, "stake": stake,
            "motivo": str(prop.get("motivo", "")).strip()[:600], "estado": "pendiente", "ganancia": None,
            "resultado": None, "temporada": None,
        })
    return nuevos, rechazos


def apuntar(agente: dict, apuestas: list[dict], nuevos: list[dict]) -> None:
    for b in nuevos:
        agente["botes"][b["bote"]]["saldo"] = round(agente["botes"][b["bote"]]["saldo"] - b["stake"], 2)
        apuestas.append(b)


# --- Liquidación ---------------------------------------------------------------------------------------
def _parcial(diferencia: float) -> float:
    """1 gana, 0 nula (se devuelve), -1 pierde."""
    return 1.0 if diferencia > 0 else -1.0 if diferencia < 0 else 0.0


def _resultado_linea(diferencia_sin_linea: float, punto: float) -> float:
    """Con líneas de cuarto (−1.25, 22.75...) la apuesta se parte en dos mitades, como en las casas."""
    if abs(punto * 4 - round(punto * 4)) < 1e-9 and abs(punto * 2 - round(punto * 2)) > 1e-9:
        return (_parcial(diferencia_sin_linea + punto - 0.25) + _parcial(diferencia_sin_linea + punto + 0.25)) / 2
    return _parcial(diferencia_sin_linea + punto)


def puntuar(apuesta: dict, resultado: dict) -> float | None:
    """De -1 (perdida) a 1 (ganada); 0 si se anula. None si con el resultado no se puede saber.
    `resultado`: {"jugadores": [a, b], "ganador": 0|1, "sets": [[6, 4], [3, 6], ...], "completo": bool}."""
    if not resultado.get("completo"):
        return 0.0  # retirada, abandono o walkover: se devuelve el dinero
    jug = resultado["jugadores"]
    lado = 0 if comun.mismo_jugador(apuesta["seleccion"], jug[0]) else 1 if comun.mismo_jugador(apuesta["seleccion"], jug[1]) else None
    juegos = [sum(s[0] for s in resultado.get("sets", [])), sum(s[1] for s in resultado.get("sets", []))]
    m = apuesta["mercado"]
    if m == "h2h":
        return None if lado is None else (1.0 if resultado["ganador"] == lado else -1.0)
    if m == "spreads":
        if lado is None or apuesta.get("punto") is None or not resultado.get("sets"):
            return None
        return _resultado_linea(juegos[lado] - juegos[1 - lado], float(apuesta["punto"]))
    if m == "totals":
        if apuesta.get("punto") is None or not resultado.get("sets"):
            return None
        total = juegos[0] + juegos[1]
        over = apuesta["seleccion"].lower() == "over"
        return _resultado_linea(total if over else -total, -float(apuesta["punto"]) if over else float(apuesta["punto"]))
    if m == "set1":
        if lado is None or not resultado.get("sets"):
            return None
        s = resultado["sets"][0]
        return 1.0 if (s[lado] > s[1 - lado]) else -1.0
    return None


def liquidar(apuesta: dict, agente: dict, puntos: float, texto: str, momento: datetime) -> None:
    """Paga la apuesta: con 1 cobra stake × cuota; con 0 se devuelve el stake; con -1 pierde el stake."""
    stake, cuota = apuesta["stake"], apuesta["cuota"]
    gana = max(puntos, 0) * stake * (cuota - 1)
    pierde = max(-puntos, 0) * stake
    ganancia = round(gana - pierde, 2)
    apuesta["ganancia"] = ganancia
    apuesta["estado"] = "ganada" if puntos > 0 else "perdida" if puntos < 0 else "nula"
    if 0 < abs(puntos) < 1:
        apuesta["estado"] = "media ganada" if puntos > 0 else "media perdida"
    apuesta["resultado"] = texto
    apuesta["liquidada"] = comun.iso(momento)
    bote = agente["botes"][apuesta["bote"]]
    bote["saldo"] = round(bote["saldo"] + stake + ganancia, 2)


def bate_cierre(apuesta: dict) -> bool | None:
    """Si apostó a una cuota mejor que la de cierre de Pinnacle (None si no hay cuota de cierre)."""
    cierre = apuesta.get("pinnacle_cierre")
    if not cierre:
        return None
    return apuesta["cuota"] > cierre


def resumen(lista: list[dict]) -> dict:
    """Rentabilidad y cuota de cierre de un conjunto de apuestas."""
    liquidadas = [a for a in lista if a["estado"] not in ("pendiente",)]
    con_dinero = [a for a in liquidadas if a["estado"] != "nula"]
    apostado = sum(a["stake"] for a in con_dinero)
    ganancia = sum(a["ganancia"] or 0 for a in liquidadas)
    clv = [bate_cierre(a) for a in liquidadas]
    clv = [c for c in clv if c is not None]
    ganadas = sum(1 for a in con_dinero if (a["ganancia"] or 0) > 0)
    return {"apuestas": len(liquidadas), "pendientes": len(lista) - len(liquidadas), "apostado": round(apostado, 2),
            "ganancia": round(ganancia, 2), "yield": ganancia / apostado if apostado else 0.0,
            "aciertos": ganadas / len(con_dinero) if con_dinero else 0.0,
            "con_cierre": len(clv), "baten_cierre": sum(clv), "pct_cierre": sum(clv) / len(clv) if clv else None}
