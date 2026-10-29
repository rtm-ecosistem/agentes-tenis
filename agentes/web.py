"""Los datos de la web (web/datos.json). La página (web/index.html) es fija y los lee al abrirse."""

from __future__ import annotations

from agentes import aprendizaje, boletos, comun, config, oficina, prompts

CAMPOS_AGENTE = ("id", "rol", "nombre", "titulo", "color", "personalidad", "como_decide", "que_lee", "estado", "alta",
                 "despedido", "carta", "carta_recibida", "sustituye_a", "sustituto", "reflexiones", "revisiones", "listo_real",
                 "reglas", "reglas_retiradas")


def _agente(a: dict, apuestas: list[dict]) -> dict:
    suyas = [x for x in apuestas if x["agente"] == a["id"]]
    por_bote = {k: {**boletos.resumen([x for x in suyas if x["bote"] == k]),
                    "valor": round(boletos.valor_bote(b, boletos.pendientes(apuestas, a["id"], k)), 2),
                    "saldo": b["saldo"], "inicial": b["inicial"]} for k, b in a["botes"].items()}
    # La evolución del bote apuesta a apuesta, para la gráfica de la ficha
    valor, serie = sum(b["inicial"] for b in a["botes"].values()), []
    for x in sorted((x for x in suyas if x.get("liquidada")), key=lambda x: x["liquidada"]):
        valor += x["ganancia"] or 0
        serie.append([x["liquidada"][:10], round(valor, 2)])
    datos = {k: a.get(k) for k in CAMPOS_AGENTE}
    return {**datos, "total": boletos.resumen(suyas), "botes": por_bote, "serie": serie[-300:],
            "situacion": prompts.situacion(a, apuestas) if a["estado"] == "activo" else None,
            "real": oficina.progreso_real(a, apuestas) if a["estado"] == "activo" else None,
            "informes": a.get("informes", [])[-12:],
            "desglose": aprendizaje.desglose(suyas), "calibracion": aprendizaje.calibracion(suyas)}


def generar(estado: dict, apuestas: list[dict]) -> dict:
    cartelera = comun.leer(config.CARTELERA, {"partidos": []})
    momento = comun.ahora()
    proximos = [p for p in cartelera.get("partidos", []) if comun.fecha_hora(p["inicio"]) > momento]
    datos = {
        "actualizado": comun.iso(momento),
        "temporada": estado.get("temporada"),
        "archivadas": estado.get("archivadas", []),
        "casa": estado.get("casa"),
        "nombres_casa": config.NOMBRES_CASA,
        "cobertura": estado.get("cobertura", {}),
        "creditos": estado.get("creditos", {}),
        "reglas": {"bote": config.BOTE_INICIAL, "stakes": config.STAKE_POR_CONFIANZA, "pendiente": config.MAX_PENDIENTE,
                   "revision": config.APUESTAS_POR_REVISION, "despido": config.PERDIDA_DESPIDO,
                   "real": config.APUESTAS_GRADUACION},
        "botes": {k: {"nombre": b["nombre"], "activo": b["activo"],
                      "mercados": [config.NOMBRES_MERCADO[m] for m in b["mercados"]]} for k, b in config.BOTES.items()},
        "agentes": [_agente(a, apuestas) for a in estado["agentes"]],
        "cartelera": {"actualizado": cartelera.get("actualizado"), "partidos": proximos},
        "apuestas": sorted(apuestas, key=lambda x: x["hora"], reverse=True)[:400],
        "sala": estado.get("sala", [])[-12:][::-1],
        "bitacora": estado.get("bitacora", [])[-30:][::-1],
        "ultima_decision": estado.get("ultima_decision"),
        "sala_aciertos": {k: v for k, v in estado.get("sala_aciertos", {}).items() if k != "vistos"},
    }
    # Si no ha cambiado nada más que la hora, no se reescribe (así no hay un cambio nuevo cada hora)
    previo = comun.leer(config.WEB_DIR / "datos.json", {})
    if {**previo, "actualizado": None} != {**datos, "actualizado": None}:
        comun.guardar(config.WEB_DIR / "datos.json", datos)
    return datos
