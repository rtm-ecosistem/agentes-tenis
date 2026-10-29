"""La vida de la oficina: la plantilla, las revisiones cada 100 apuestas, los despidos con su carta, los
sustitutos, las reflexiones de los domingos y el paso a dinero real."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from agentes import aprendizaje, boletos, comun, config, emociones, prompts

MAX_INFORMES = 40
MAX_REFLEXIONES = 20


def plantilla() -> dict:
    return json.loads((config.ESTRATEGIAS / "plantilla.json").read_text(encoding="utf-8"))


def nuevo_agente(rol: str, datos: dict, momento: datetime, numero: int = 1, **extra) -> dict:
    botes = {k: boletos.bote_nuevo() for k, b in config.BOTES.items() if b["activo"]}
    return {"id": f"{rol}-{numero}", "rol": rol, "numero": numero, "nombre": datos["nombre"], "titulo": datos["titulo"],
            "color": datos.get("color", "#555"), "personalidad": datos["personalidad"],
            "como_decide": datos["como_decide"], "que_lee": datos["que_lee"], "estado": "activo",
            "temperamento": emociones.temperamento_valido(datos.get("temperamento")),
            "alta": comun.iso(momento), "botes": botes,
            "periodo": {"inicio": comun.iso(momento), "valor": sum(b["saldo"] for b in botes.values()), "numero": 1},
            "informes": [], "reflexiones": [], "revisiones": [], **extra}


def estado_inicial(momento: datetime, temporada: str = "prueba") -> dict:
    return {"temporada": {"nombre": temporada, "inicio": comun.hoy_madrid(momento)},
            "agentes": [nuevo_agente(rol, d, momento) for rol, d in plantilla().items()],
            "sala": [], "bitacora": [], "creditos": {}, "casa": None, "cobertura": {}}


def cargar(momento: datetime | None = None) -> dict:
    estado = comun.leer(config.ESTADO, None)
    if not estado:
        estado = estado_inicial(momento or comun.ahora())
    # La plantilla de siempre recibe su temperamento si aún no lo tenía
    base = plantilla()
    for a in estado["agentes"]:
        if "temperamento" not in a:
            a["temperamento"] = emociones.temperamento_valido(base.get(a["rol"], {}).get("temperamento")) if a.get("numero", 1) == 1 else {}
    # Si se activa el bote 2, cada analista activo lo abre con 1.000 € nuevos
    for a in estado["agentes"]:
        if a["estado"] == "activo":
            for k, b in config.BOTES.items():
                if b["activo"] and k not in a["botes"]:
                    a["botes"][k] = boletos.bote_nuevo()
                    a["periodo"]["valor"] += config.BOTE_INICIAL
    return estado


def activos(estado: dict) -> list[dict]:
    return [a for a in estado["agentes"] if a["estado"] == "activo"]


def anotar(estado: dict, momento: datetime, texto: str, tipo: str = "info") -> None:
    estado.setdefault("bitacora", []).append({"hora": comun.iso(momento), "texto": texto, "tipo": tipo})
    estado["bitacora"] = estado["bitacora"][-80:]
    print(texto)


def guardar_informe(agente: dict, informe: dict) -> None:
    agente["informes"] = (agente.get("informes", []) + [informe])[-MAX_INFORMES:]


# --- Revisión cada 100 apuestas ----------------------------------------------------------------------
def revisar(estado: dict, apuestas: list[dict], ia, avisos, momento: datetime) -> None:
    for agente in list(activos(estado)):
        s = prompts.situacion(agente, apuestas)
        if s["liquidadas"] < config.APUESTAS_POR_REVISION:
            continue
        pierde = s["rentabilidad"] < -config.PERDIDA_DESPIDO
        peor_cierre = s["pct_cierre"] is not None and s["pct_cierre"] < 0.5
        revision = {"hora": comun.iso(momento), "periodo": agente["periodo"]["numero"], "apuestas": s["liquidadas"],
                     "rentabilidad": s["rentabilidad"], "pct_cierre": s["pct_cierre"], "despedido": pierde and peor_cierre}
        agente["revisiones"].append(revision)
        if pierde and peor_cierre:
            despedir(estado, agente, apuestas, ia, avisos, momento, s)
        else:
            motivo = ("gana dinero" if s["rentabilidad"] >= 0 else "pierde, pero menos de un 10 %") if not pierde else \
                "pierde más de un 10 %, pero bate la cuota de cierre en la mayoría de sus apuestas"
            anotar(estado, momento, f"✅ {agente['nombre']} supera su revisión de {s['liquidadas']} apuestas "
                                    f"({s['rentabilidad']:+.1%}; {motivo}).", "revision")
            agente["periodo"] = {"inicio": comun.iso(momento), "valor": s["valor"], "numero": agente["periodo"]["numero"] + 1}


def despedir(estado: dict, agente: dict, apuestas: list[dict], ia, avisos, momento: datetime, s: dict) -> dict:
    agente["estado"] = "despedido"
    agente["despedido"] = comun.hoy_madrid(momento)
    # Las apuestas pendientes siguen su curso y se liquidan en sus botes, pero ya no apuesta más
    try:
        r = ia.pedir_json(prompts.INSTRUCCIONES_CARTA.format(**agente), prompts.mensaje_vida(agente, apuestas))
        agente["carta"] = str(r.get("carta", "")).strip()
    except Exception as e:  # noqa: BLE001
        print(f"{agente['nombre']} no pudo escribir su carta: {e}")
        agente["carta"] = ""
    usados = ", ".join(sorted({a["nombre"] for a in estado["agentes"]}))
    datos = {k: agente[k] for k in ("titulo", "color", "como_decide", "que_lee")}
    try:
        r = ia.pedir_json(prompts.INSTRUCCIONES_SUSTITUTO.format(titulo=agente["titulo"], usados=usados), "Preséntalo.")
        datos |= {"nombre": str(r["nombre"]).strip()[:20], "personalidad": str(r["personalidad"]).strip()[:300],
                  "temperamento": r.get("temperamento")}
    except Exception as e:  # noqa: BLE001
        print(f"No se pudo inventar el sustituto: {e}")
        datos |= {"nombre": f"{agente['nombre']} II", "personalidad": agente["personalidad"]}
    if datos["nombre"] in usados.split(", "):
        datos["nombre"] = f"{datos['nombre']} ({agente['numero'] + 1})"
    numero = agente["numero"] + 1
    nuevo = nuevo_agente(agente["rol"], datos, momento, numero, sustituye_a=agente["id"], carta_recibida=agente["carta"])
    estado["agentes"].append(nuevo)
    agente["sustituto"] = nuevo["id"]
    texto = (f"🔴 Despedido {agente['nombre']} ({agente['titulo']}): {s['rentabilidad']:+.1%} en {s['liquidadas']} apuestas "
             f"y solo batió la cuota de cierre en el {s['pct_cierre']:.0%}. Le sustituye {nuevo['nombre']}.")
    anotar(estado, momento, texto, "despido")
    if agente["carta"]:
        aprendizaje.anadir_biblioteca(estado, f"Carta de despedida: {agente['carta']}", agente["nombre"], comun.hoy_madrid(momento))
    try:
        avisos.crear_issue(f"🔴 Despedido {agente['nombre']} ({agente['titulo']})",
                           f"{texto}\n\n**Su carta al sustituto:**\n\n> {agente['carta'] or '(no pudo escribirla)'}\n\n"
                           f"**{nuevo['nombre']}**: {nuevo['personalidad']}\n\nCierra este aviso cuando lo leas.", ["despido"])
    except Exception as e:  # noqa: BLE001
        print(f"No se pudo crear el aviso del despido: {e}")
    return nuevo


# --- Paso a dinero real ----------------------------------------------------------------------------------
def progreso_real(agente: dict, apuestas: list[dict]) -> dict:
    r = boletos.resumen([a for a in apuestas if a["agente"] == agente["id"]])
    listo = (r["apuestas"] >= config.APUESTAS_GRADUACION and r["ganancia"] > 0
             and r["pct_cierre"] is not None and r["pct_cierre"] > 0.5)
    return {**r, "objetivo": config.APUESTAS_GRADUACION, "listo": listo}


def revisar_dinero_real(estado: dict, apuestas: list[dict], avisos, momento: datetime) -> None:
    for agente in activos(estado):
        if agente.get("listo_real"):
            continue
        p = progreso_real(agente, apuestas)
        if not p["listo"]:
            continue
        agente["listo_real"] = comun.hoy_madrid(momento)
        texto = (f"🎓 {agente['nombre']} ({agente['titulo']}) cumple la regla para copiarle con dinero real: "
                 f"{p['apuestas']} apuestas, {p['ganancia']:+.2f} € y bate la cuota de cierre en el {p['pct_cierre']:.0%}.")
        anotar(estado, momento, texto, "real")
        try:
            avisos.crear_issue(f"🎓 {agente['nombre']} se ha ganado que le copies", texto +
                               "\n\n**Nada se mueve solo.** Si quieres los avisos para copiarle (por ejemplo, por Telegram), "
                               "dímelo y los construimos. Si prefieres esperar, cierra este aviso.", ["dinero-real"])
        except Exception as e:  # noqa: BLE001
            print(f"No se pudo crear el aviso: {e}")


# --- Lección de cada noche y biblioteca --------------------------------------------------------------
def lecciones(estado: dict, apuestas: list[dict], ia, momento: datetime) -> int:
    """Cada analista escribe una lección sobre sus apuestas resueltas en las últimas 24 horas (una vez al día)."""
    hoy, desde, n = comun.hoy_madrid(momento), comun.iso(momento - timedelta(hours=24)), 0
    for agente in activos(estado):
        if agente.get("lecciones") and agente["lecciones"][-1]["fecha"] == hoy:
            continue
        resueltas = [a for a in apuestas if a["agente"] == agente["id"] and (a.get("liquidada") or "") >= desde
                     and a["estado"] != "pendiente"]
        if not resueltas:
            continue
        try:
            r = ia.pedir_json(prompts.INSTRUCCIONES_LECCION.format(**agente), prompts.mensaje_leccion(agente, resueltas))
        except Exception as e:  # noqa: BLE001
            print(f"{agente['nombre']} no pudo escribir su lección: {e}")
            continue
        aprendizaje.guardar_leccion(agente, r.get("leccion"), hoy, len(resueltas))
        n += 1
    return n


def ordenar_biblioteca(estado: dict, apuestas: list[dict], ia, momento: datetime) -> None:
    manager = next((a for a in activos(estado) if a["rol"] == "manager"), None)
    if not manager:
        return
    try:
        r = ia.pedir_json(prompts.INSTRUCCIONES_BIBLIOTECA.format(**manager), prompts.mensaje_biblioteca(estado, apuestas))
    except Exception as e:  # noqa: BLE001
        print(f"No se pudo ordenar la biblioteca: {e}")
        return
    aprendizaje.poner_biblioteca(estado, r.get("biblioteca") or [], comun.hoy_madrid(momento))


# --- Reflexión de los domingos -----------------------------------------------------------------------
def reflexiones(estado: dict, apuestas: list[dict], ia, momento: datetime) -> None:
    hoy = comun.hoy_madrid(momento)
    desde = comun.iso(momento - timedelta(days=7))
    for agente in activos(estado):
        if agente.get("reflexiones") and agente["reflexiones"][-1]["fecha"] == hoy:
            continue
        try:
            r = ia.pedir_json(prompts.INSTRUCCIONES_REFLEXION.format(**agente), prompts.mensaje_vida(agente, apuestas, desde))
        except Exception as e:  # noqa: BLE001
            print(f"{agente['nombre']} no pudo escribir su reflexión: {e}")
            continue
        reglas = r.get("reglas")
        if not isinstance(reglas, list):  # respuesta antigua con una sola regla: se suma a las que tenía
            reglas = [x["texto"] for x in agente.get("reglas", [])] + [r.get("regla")]
            reglas = reglas[-aprendizaje.MAX_REGLAS:]
        aprendizaje.poner_reglas(agente, reglas, hoy)
        agente["reflexiones"] = (agente.get("reflexiones", []) + [{
            "fecha": hoy, "texto": str(r.get("reflexion", "")).strip(),
            "reglas": [x["texto"] for x in agente.get("reglas", [])]}])[-MAX_REFLEXIONES:]
