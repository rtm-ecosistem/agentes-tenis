"""Las tareas de la oficina. Las lanza GitHub (con el despertador de cron-job.org para que vayan a su hora):

    python -m agentes.ciclo decision   # 9:00: cuotas, sala de analistas y apuestas de los cuatro analistas
    python -m agentes.ciclo sala       # 14:00 y 20:00: noticias e informe de la sala (domingo: reflexiones)
    python -m agentes.ciclo cierre     # cada hora: cuota de cierre de Pinnacle, resultados y revisiones
    python -m agentes.ciclo web        # solo rehacer los datos de la web
    python -m agentes.ciclo reiniciar --temporada australia-2027   # empezar de cero (lo anterior se archiva)
"""

from __future__ import annotations

import argparse
import calendar
import shutil
from datetime import datetime, timedelta

from agentes import avisos as avisos_mod, boletos, comun, config, cuotas, elo as elo_mod, ia as ia_mod, \
    noticias, oficina, prompts, resultados, sala, web

ESPECIALISTAS = ("estadistico", "reportero", "superficies")


# --- Créditos de The Odds API ------------------------------------------------------------------------
def anotar_creditos(estado: dict, api: cuotas.OddsAPI, momento: datetime, avisos) -> None:
    if api.restantes is None:
        return
    mes = momento.strftime("%Y-%m")
    c = estado.setdefault("creditos", {})
    if c.get("mes") != mes:
        c.update({"mes": mes, "gastados_mes": 0})
    c.update({"restantes": api.restantes, "usados": api.usados, "actualizado": comun.iso(momento)})
    c["gastados_mes"] = c.get("gastados_mes", 0) + api.gastados
    dia = momento.day
    dias_mes = calendar.monthrange(momento.year, momento.month)[1]
    ritmo = c["gastados_mes"] / max(dia, 1)
    c["prevision_mes"] = round(ritmo * (dias_mes - dia))
    if c["prevision_mes"] > api.restantes and c.get("aviso") != mes and dia >= 3:
        c["aviso"] = mes
        texto = (f"Al ritmo de este mes ({ritmo:.0f} créditos al día) harían falta unos {c['prevision_mes']} créditos "
                 f"hasta fin de mes y quedan {api.restantes}. Mientras tanto la oficina ahorra: solo pide el ganador "
                 f"del partido y guarda la cuota de cierre una vez por jornada.")
        oficina.anotar(estado, momento, f"⚠️ Créditos de The Odds API justos: {texto}", "creditos")
        try:
            avisos.crear_issue("⚠️ Los créditos gratis de The Odds API no llegan a fin de mes", texto +
                               "\n\nNo hace falta hacer nada: no se paga nada sin que lo decidas tú. Si quieres, "
                               "hablamos de opciones (pagar un plan, otra API gratis o apostar en menos torneos).",
                               ["creditos"])
        except Exception as e:  # noqa: BLE001
            print(f"No se pudo crear el aviso de créditos: {e}")


def en_ahorro(estado: dict, momento: datetime) -> bool:
    c = estado.get("creditos") or {}
    if c.get("restantes") is None:
        return False
    dias = calendar.monthrange(momento.year, momento.month)[1] - momento.day + 1
    return c["restantes"] / dias < 12 or c.get("aviso") == momento.strftime("%Y-%m")


# --- Decisión diaria ---------------------------------------------------------------------------------
def decidir_uno(agente: dict, estado: dict, apuestas: list[dict], bote_id: str, cartelera: list[dict], extra: str,
                sala_txt: str, ia, momento: datetime) -> tuple[dict, list[dict], list[dict]]:
    mercados = config.BOTES[bote_id]["mercados"]
    texto, mapa = prompts.codificar(cartelera, mercados)
    if not mapa:
        return {"resumen": "Hoy no hay partidos con cuotas: no apuesto."}, [], []
    r = ia.pedir_json(prompts.instrucciones(agente),
                      prompts.mensaje_analista(agente, estado, apuestas, bote_id, texto, extra, sala_txt, momento),
                      prompts.esquema_analista(list(mapa)))
    propuestas = [p for p in (r.get("apuestas") or []) if isinstance(p, dict)]
    convertidas = [{**p, "seleccion": mapa.get(str(p.get("seleccion", "")).strip(), str(p.get("seleccion")))} for p in propuestas]
    fecha = comun.hoy_madrid(momento)
    nuevos, rechazos = boletos.validar(agente, apuestas, bote_id, convertidas, cartelera, momento, fecha)
    for b in nuevos:
        b["casa"] = estado.get("casa")
        b["temporada"] = estado["temporada"]["nombre"]
    boletos.apuntar(agente, apuestas, nuevos)
    oficina.guardar_informe(agente, {
        "fecha": fecha, "hora": comun.iso(momento), "bote": bote_id, "resumen": str(r.get("resumen", "")).strip(),
        "informe": {k: str(v).strip() for k, v in (r.get("informe") or {}).items()},
        "descarte": str(r.get("descarte", "") or "").strip(), "apuestas": [b["id"] for b in nuevos], "rechazos": rechazos})
    print(f"{agente['nombre']} (bote {bote_id}): {len(nuevos)} apuestas" + (f"; rechazadas: {rechazos}" if rechazos else ""))
    return r, propuestas, nuevos


def decision(forzar: bool = False, momento: datetime | None = None, api=None, ia=None, avisos=None) -> None:
    momento = momento or comun.ahora()
    estado = oficina.cargar(momento)
    hoy = comun.hoy_madrid(momento)
    if not forzar and (estado.get("ultima_decision") == hoy or momento.astimezone(comun.MADRID).hour < config.HORA_DECISION):
        print("Hoy ya se decidió o aún no son las 9:00 en España: nada que hacer.")
        return
    estado["ultima_decision"] = hoy
    api = api or cuotas.OddsAPI()
    ia = ia or ia_mod.crear_ia(prisa=True)
    avisos = avisos or avisos_mod.GitHub()
    apuestas = comun.leer(config.APUESTAS, [])

    elo = elo_mod.actualizar()
    mercados = sorted({m for k, b in config.BOTES.items() if b["activo"] for m in b["mercados"]
                       if m in ("h2h", "spreads", "totals")})
    if en_ahorro(estado, momento):
        mercados = ["h2h"]
    cartelera = cuotas.cartelera(api, estado, mercados, momento)
    anotar_creditos(estado, api, momento, avisos)
    comun.guardar(config.CARTELERA, {"actualizado": comun.iso(momento), "casa": estado.get("casa"), "partidos": cartelera})
    oficina.anotar(estado, momento, f"🎾 Cartelera: {len(cartelera)} partidos en las próximas 24 horas "
                                    f"(casa: {config.NOMBRES_CASA.get(estado.get('casa'), estado.get('casa'))}).")

    datos_noticias = noticias.recoger(sorted({j for p in cartelera for j in p["jugadores"]}))
    if cartelera:
        sala.escribir(estado, cartelera, elo, datos_noticias, ia, momento)
    sala_txt = prompts.texto_sala(sala.para_decidir(estado, momento))

    extras = {"estadistico": "DATOS PARA TU MÉTODO (Elo por superficie frente al mercado)\n" + prompts.datos_estadisticos(cartelera, elo),
              "reportero": "NOTICIAS DE LOS JUGADORES DE HOY\n" + prompts.datos_noticias(cartelera, datos_noticias),
              "superficies": "DATOS POR SUPERFICIE\n" + prompts.datos_superficie(cartelera, elo)}
    for bote_id, bote in config.BOTES.items():
        if not bote["activo"] or not cartelera:
            continue
        hechos = []
        for agente in oficina.activos(estado):
            if agente["rol"] not in ESPECIALISTAS or bote_id not in agente["botes"]:
                continue
            try:
                r, propuestas, _ = decidir_uno(agente, estado, apuestas, bote_id, cartelera, extras[agente["rol"]],
                                               sala_txt, ia, momento)
                hechos.append((agente, r, propuestas))
            except Exception as e:  # noqa: BLE001
                oficina.anotar(estado, momento, f"{agente['nombre']} no pudo decidir hoy: {e}", "error")
        for agente in oficina.activos(estado):
            if agente["rol"] != "manager" or bote_id not in agente["botes"]:
                continue
            try:
                decidir_uno(agente, estado, apuestas, bote_id, cartelera, prompts.texto_especialistas(hechos), sala_txt, ia, momento)
            except Exception as e:  # noqa: BLE001
                oficina.anotar(estado, momento, f"{agente['nombre']} no pudo decidir hoy: {e}", "error")

    nuevas = [a for a in apuestas if a["hora"] == comun.iso(momento)]
    oficina.anotar(estado, momento, f"🧾 Decisión del día: {len(nuevas)} apuestas nuevas por "
                                    f"{sum(a['stake'] for a in nuevas):.2f} €.")
    comun.guardar(config.APUESTAS, apuestas)
    comun.guardar(config.ESTADO, estado)
    web.generar(estado, apuestas)


# --- Sala de la tarde y de la noche ------------------------------------------------------------------
def tarea_sala(momento: datetime | None = None, ia=None, forzar: bool = False) -> None:
    momento = momento or comun.ahora()
    estado = oficina.cargar(momento)
    hora = momento.astimezone(comun.MADRID)
    franja = f"{hora.date()}-{max([h for h in config.HORAS_SALA if h <= hora.hour], default=-1)}"
    if not forzar and estado.get("ultima_sala") == franja:
        print("La sala ya escribió el informe de esta franja.")
        return
    estado["ultima_sala"] = franja
    ia = ia or ia_mod.crear_ia(prisa=True)
    apuestas = comun.leer(config.APUESTAS, [])
    guardada = comun.leer(config.CARTELERA, {"partidos": []})
    # Los partidos que aún no han empezado de la última cartelera (no se gastan créditos)
    cartelera = [p for p in guardada["partidos"] if comun.fecha_hora(p["inicio"]) > momento]
    datos_noticias = noticias.recoger(sorted({j for p in cartelera for j in p["jugadores"]}))
    if cartelera:
        sala.escribir(estado, cartelera, comun.leer(config.ELO, {}), datos_noticias, ia, momento)
    if hora.weekday() == 6 and hora.hour >= 19:
        oficina.reflexiones(estado, apuestas, ia, momento)
    comun.guardar(config.ESTADO, estado)
    web.generar(estado, apuestas)


# --- Cierre: cuota de Pinnacle, resultados y revisiones ----------------------------------------------
def guardar_cierres(estado: dict, apuestas: list[dict], api, momento: datetime) -> int:
    sin_cierre = [a for a in apuestas if a["estado"] == "pendiente" and not a.get("pinnacle_cierre")
                  and comun.fecha_hora(a["inicio"]) > momento]
    urgentes = [a for a in sin_cierre if comun.fecha_hora(a["inicio"]) - momento <= timedelta(minutes=config.MINUTOS_ANTES_CIERRE + 15)]
    if not urgentes:
        return 0
    horas = config.HORAS_JORNADA if en_ahorro(estado, momento) else 3
    limite = momento + timedelta(hours=horas)
    guardadas = 0
    for deporte in sorted({a["deporte"] for a in urgentes}):
        grupo = [a for a in sin_cierre if a["deporte"] == deporte and comun.fecha_hora(a["inicio"]) <= limite]
        mercados = sorted({a["mercado"] for a in grupo})
        try:
            eventos = {e["id"]: e for e in api.cuotas(deporte, mercados, [config.ARBITRO], desde=momento)}
        except Exception as e:  # noqa: BLE001
            print(f"No se pudo leer la cuota de cierre de {deporte}: {e}")
            continue
        for a in grupo:
            ev = eventos.get(a["partido"])
            precio = cuotas.precio_en(ev, config.ARBITRO, a["mercado"], a["seleccion"], a.get("punto")) if ev else None
            if precio:
                a["pinnacle_cierre"] = precio
                a["hora_cierre"] = comun.iso(momento)
                guardadas += 1
    return guardadas


def liquidar_pendientes(estado: dict, apuestas: list[dict], api, momento: datetime) -> int:
    agentes = {a["id"]: a for a in estado["agentes"]}
    pendientes = [a for a in apuestas if a["estado"] == "pendiente"
                  and comun.fecha_hora(a["inicio"]) < momento - timedelta(minutes=90)]
    partidos, leidos = [], []
    for dia in sorted(set(resultados.dias_a_mirar(pendientes, momento)) | set(resultados.recientes(momento, 1))):
        del_dia = resultados.descargar_espn(dia)
        if del_dia is not None:
            partidos += del_dia
            # Los dos últimos días pueden tener partidos aún por jugar: se vuelven a leer
            if dia < (momento - timedelta(days=1)).date():
                leidos.append(dia)
    resultados.guardar_historial(partidos, leidos)
    liquidadas, consultados = 0, {}
    for a in pendientes:
        r = resultados.buscar(a, partidos)
        horas = (momento - comun.fecha_hora(a["inicio"])).total_seconds() / 3600
        if r is None and horas > 36 and a["mercado"] == "h2h" and api is not None:
            if a["deporte"] not in consultados:
                try:
                    consultados[a["deporte"]] = resultados.leer_odds_api(api.marcadores(a["deporte"]))
                except Exception as e:  # noqa: BLE001
                    print(f"Marcador de The Odds API ({a['deporte']}): {e}")
                    consultados[a["deporte"]] = []
            r = resultados.buscar(a, consultados[a["deporte"]])
        if r is None:
            if horas > 96:
                boletos.liquidar(a, agentes[a["agente"]], 0.0, "Sin resultado en 4 días: apuesta anulada", momento)
                liquidadas += 1
            continue
        puntos = boletos.puntuar(a, r)
        if puntos is None:
            if horas > 96:
                boletos.liquidar(a, agentes[a["agente"]], 0.0, resultados.texto(r) + " · sin juegos para liquidarla: anulada", momento)
                liquidadas += 1
            continue
        boletos.liquidar(a, agentes[a["agente"]], puntos, resultados.texto(r), momento)
        liquidadas += 1
    return liquidadas


def cierre(momento: datetime | None = None, api=None, ia=None, avisos=None) -> None:
    momento = momento or comun.ahora()
    estado = oficina.cargar(momento)
    apuestas = comun.leer(config.APUESTAS, [])
    try:
        api = api or cuotas.OddsAPI()
    except RuntimeError as e:
        print(e)
        api = None
    avisos = avisos or avisos_mod.GitHub()
    if api:
        n = guardar_cierres(estado, apuestas, api, momento)
        if n:
            print(f"Cuota de cierre de Pinnacle guardada en {n} apuestas")
    n = liquidar_pendientes(estado, apuestas, api, momento)
    resultados.rellenar(momento)
    elo_mod.actualizar()
    if n:
        oficina.anotar(estado, momento, f"🏁 {n} apuestas liquidadas.")
    if api:
        anotar_creditos(estado, api, momento, avisos)
    if any(prompts.situacion(a, apuestas)["liquidadas"] >= config.APUESTAS_POR_REVISION for a in oficina.activos(estado)):
        oficina.revisar(estado, apuestas, ia or ia_mod.crear_ia(prisa=True), avisos, momento)
    oficina.revisar_dinero_real(estado, apuestas, avisos, momento)
    comun.guardar(config.APUESTAS, apuestas)
    comun.guardar(config.ESTADO, estado)
    web.generar(estado, apuestas)


# --- Empezar de cero ---------------------------------------------------------------------------------
def reiniciar(temporada: str, momento: datetime | None = None) -> None:
    """Archiva la temporada actual (la prueba no cuenta en el historial) y empieza otra desde cero."""
    momento = momento or comun.ahora()
    previo = comun.leer(config.ESTADO, None)
    if previo:
        destino = config.ARCHIVO / previo["temporada"]["nombre"]
        destino.mkdir(parents=True, exist_ok=True)
        for f in (config.ESTADO, config.APUESTAS):
            if f.exists():
                shutil.move(str(f), destino / f.name)
    estado = oficina.estado_inicial(momento, temporada)
    if previo:
        estado["casa"] = previo.get("casa")
        estado["creditos"] = previo.get("creditos", {})
        estado["archivadas"] = previo.get("archivadas", []) + [previo["temporada"]["nombre"]]
    oficina.anotar(estado, momento, f"🆕 Empieza la temporada «{temporada}» desde cero.")
    comun.guardar(config.ESTADO, estado)
    comun.guardar(config.APUESTAS, [])
    web.generar(estado, [])


def main() -> None:
    p = argparse.ArgumentParser(description="La oficina del tenis")
    p.add_argument("tarea", choices=["decision", "sala", "cierre", "web", "reiniciar"])
    p.add_argument("--forzar", action="store_true", help="Ejecutar aunque no sea la hora")
    p.add_argument("--temporada", default="", help="Nombre de la temporada nueva (solo con reiniciar)")
    args = p.parse_args()
    if args.tarea == "decision":
        decision(forzar=args.forzar)
    elif args.tarea == "sala":
        tarea_sala(forzar=args.forzar)
    elif args.tarea == "cierre":
        cierre()
    elif args.tarea == "reiniciar":
        if not args.temporada:
            raise SystemExit("Indica el nombre de la temporada nueva con --temporada")
        reiniciar(args.temporada)
    else:
        estado = oficina.cargar()
        apuestas = comun.leer(config.APUESTAS, [])
        comun.guardar(config.ESTADO, estado)
        web.generar(estado, apuestas)


if __name__ == "__main__":
    main()
