"""Lo que los analistas aprenden de sus apuestas: dónde ganan y dónde pierden, si aciertan las probabilidades que
dan, sus reglas de la semana y cómo acierta la sala con sus opiniones."""

from __future__ import annotations

from datetime import datetime

from agentes import boletos, comun, config, resultados

MAX_REGLAS = 3
MAX_LECCIONES = 10
MAX_BIBLIOTECA = 10
TRAMOS_CUOTA = ((0, 1.6, "cuotas bajas (< 1.60)"), (1.6, 2.2, "cuotas medias (1.60-2.19)"),
                (2.2, 99, "cuotas altas (≥ 2.20)"))
TRAMOS_PROB = ((0, .4), (.4, .5), (.5, .6), (.6, .7), (.7, 1.01))
NOMBRES_MERCADO = {"h2h": "ganador", "spreads": "hándicap de juegos", "totals": "total de juegos", "set1": "primer set"}
NOMBRES_SUPERFICIE = {"hard": "pista dura", "clay": "tierra", "grass": "hierba", "indoor": "pista cubierta"}


def _liquidadas(apuestas: list[dict]) -> list[dict]:
    return [a for a in apuestas if a["estado"] != "pendiente"]


def _tramo_cuota(cuota: float) -> str:
    return next(n for lo, hi, n in TRAMOS_CUOTA if lo <= cuota < hi)


# --- Dónde gana y dónde pierde ---------------------------------------------------------------------------
def desglose(apuestas: list[dict]) -> dict:
    """Rentabilidad y cuota de cierre por mercado, por superficie y por tramo de cuota."""
    grupos: dict[str, dict[str, list[dict]]] = {"mercado": {}, "superficie": {}, "cuota": {}}
    for a in _liquidadas(apuestas):
        grupos["mercado"].setdefault(NOMBRES_MERCADO.get(a.get("mercado"), a.get("mercado") or "?"), []).append(a)
        grupos["superficie"].setdefault(NOMBRES_SUPERFICIE.get(a.get("superficie"), a.get("superficie") or "?"), []).append(a)
        grupos["cuota"].setdefault(_tramo_cuota(a.get("cuota") or 0), []).append(a)
    return {g: {k: boletos.resumen(v) for k, v in d.items()} for g, d in grupos.items()}


def texto_desglose(apuestas: list[dict]) -> str:
    d = desglose(apuestas)
    lineas = []
    for titulo, g in (("Por mercado", "mercado"), ("Por superficie", "superficie"), ("Por cuota", "cuota")):
        partes = [f"{k}: {r['apuestas']} apuestas, {r['ganancia']:+.2f} €, yield {r['yield']:+.1%}, bate el cierre en "
                  f"{'-' if r['pct_cierre'] is None else format(r['pct_cierre'], '.0%')}"
                  for k, r in sorted(d[g].items(), key=lambda x: -x[1]["apuestas"])]
        if partes:
            lineas.append(f"{titulo}: " + "; ".join(partes) + ".")
    return "\n".join(lineas) or "(aún no hay apuestas liquidadas)"


# --- Si aciertan las probabilidades que dan ------------------------------------------------------------
def calibracion(apuestas: list[dict]) -> list[dict]:
    """Agrupa las apuestas por la probabilidad que dio el analista y cuenta cuántas salieron."""
    filas = []
    for lo, hi in TRAMOS_PROB:
        grupo = [a for a in _liquidadas(apuestas) if a["estado"] != "nula" and a.get("probabilidad") is not None
                 and lo <= a["probabilidad"] < hi]
        if not grupo:
            continue
        ganadas = sum(1 for a in grupo if "ganada" in a["estado"])
        filas.append({"desde": lo, "hasta": min(hi, 1), "apuestas": len(grupo),
                      "dijo": round(sum(a["probabilidad"] for a in grupo) / len(grupo), 3),
                      "salio": round(ganadas / len(grupo), 3)})
    return filas


def texto_calibracion(apuestas: list[dict]) -> str:
    filas = calibracion(apuestas)
    if not filas:
        return "(aún no hay apuestas liquidadas con probabilidad)"
    return "\n".join(f"- Cuando dijiste {f['desde']:.0%}-{f['hasta']:.0%} (media {f['dijo']:.0%}): salieron el "
                     f"{f['salio']:.0%} de {f['apuestas']} apuestas" for f in filas)


# --- Reglas de la semana --------------------------------------------------------------------------------
def poner_reglas(agente: dict, nuevas: list, fecha: str) -> None:
    """Las reglas que el analista decide tener (como mucho tres). Las que repite conservan su fecha."""
    antes = {r["texto"]: r for r in agente.get("reglas", [])}
    textos = []
    for t in nuevas:
        t = str(t or "").strip()[:240]
        if t and t not in textos:
            textos.append(t)
    agente["reglas"] = [antes.get(t, {"texto": t, "desde": fecha}) for t in textos[:MAX_REGLAS]]
    retiradas = [r for t, r in antes.items() if t not in textos[:MAX_REGLAS]]
    if retiradas:
        agente["reglas_retiradas"] = (agente.get("reglas_retiradas", []) +
                                      [{**r, "hasta": fecha} for r in retiradas])[-10:]


def texto_reglas(agente: dict) -> str:
    reglas = agente.get("reglas", [])
    if not reglas:
        return "(todavía no te has puesto reglas: las decides en la reflexión del domingo)"
    return "\n".join(f"{i}. {r['texto']} (desde el {r['desde']})" for i, r in enumerate(reglas, 1))


# --- La sala: cómo aciertan sus opiniones -----------------------------------------------------------------
def favorito(partido: dict) -> str | None:
    """El favorito según Pinnacle (o según la casa, si Pinnacle no tiene cuota)."""
    precios = partido.get("pinnacle_h2h") or {o["nombre"]: o["cuota"] for o in partido.get("opciones", [])
                                              if o["mercado"] == "h2h"}
    if len(precios) < 2:
        return None
    return min(precios, key=precios.get)


def puntuar_sala(estado: dict, partidos: list[dict], momento: datetime) -> int:
    """Puntúa las opiniones de la sala de los partidos ya jugados. Cuenta solo la última opinión de cada
    partido: «favorito» acierta si gana el favorito y «sorpresa» si gana el otro; «dudoso» no cuenta."""
    marcador = estado.setdefault("sala_aciertos", {"favorito": [0, 0], "sorpresa": [0, 0], "vistos": []})
    vistos = set(marcador["vistos"])
    nuevos = 0
    for informe in reversed(estado.get("sala", [])):
        for d in informe.get("partidos", []):
            pid = d.get("id")
            if not pid or "acierto" in d or not d.get("favorito") or comun.fecha_hora(d["inicio"]) > momento:
                continue
            if pid in vistos:
                d["acierto"] = None  # una opinión anterior del mismo partido: solo cuenta la última
                continue
            r = resultados.buscar({"jugadores": d["jugadores"], "inicio": d["inicio"], "partido": pid}, partidos)
            if r is None or not r.get("completo"):
                continue
            gano_favorito = comun.mismo_jugador(r["jugadores"][r["ganador"]], d["favorito"])
            vistos.add(pid)
            if d["vista"] == "dudoso":
                d["acierto"] = None
                continue
            d["acierto"] = gano_favorito if d["vista"] == "favorito" else not gano_favorito
            marcador[d["vista"]][0] += int(d["acierto"])
            marcador[d["vista"]][1] += 1
            nuevos += 1
    marcador["vistos"] = sorted(vistos)[-300:]
    return nuevos


def texto_sala_aciertos(estado: dict) -> str:
    m = estado.get("sala_aciertos")
    if not m or not (m["favorito"][1] or m["sorpresa"][1]):
        return ""
    partes = [f"cuando dijisteis «{v}» acertasteis {m[v][0]} de {m[v][1]} ({m[v][0] / m[v][1]:.0%})"
              for v in ("favorito", "sorpresa") if m[v][1]]
    return "VUESTRO HISTORIAL: " + "; ".join(partes) + ". Tenedlo en cuenta antes de ir contra el favorito."


# --- Lo que dejaron pasar -------------------------------------------------------------------------------
def puntuar_descartes(estado: dict, partidos: list[dict], momento: datetime) -> int:
    """Comprueba si la mejor apuesta que cada analista dejó pasar habría ganado (a 1 unidad, a su cuota)."""
    n = 0
    for agente in estado["agentes"]:
        cuenta = agente.setdefault("descartes", {"ganadas": 0, "perdidas": 0, "nulas": 0, "unidades": 0.0})
        for inf in agente.get("informes", []):
            d = inf.get("descarte_opcion")
            if not d or "puntos" in d or comun.fecha_hora(d["inicio"]) > momento:
                continue
            r = resultados.buscar({"jugadores": d["jugadores"], "inicio": d["inicio"], "partido": d["partido"]}, partidos)
            if r is None:
                continue
            puntos = boletos.puntuar(d, r)
            if puntos is None:
                continue
            d["puntos"] = puntos
            clave = "ganadas" if puntos > 0 else "perdidas" if puntos < 0 else "nulas"
            cuenta[clave] += 1
            cuenta["unidades"] = round(cuenta["unidades"] + (puntos * (d["cuota"] - 1) if puntos > 0 else puntos), 3)
            n += 1
    return n


def texto_descartes(agente: dict) -> str:
    c = agente.get("descartes") or {}
    total = c.get("ganadas", 0) + c.get("perdidas", 0)
    if not total:
        return "(todavía no se ha jugado ninguno de tus descartes)"
    consejo = ("dejas pasar apuestas buenas: quizá eres demasiado prudente" if c["unidades"] > 0 else
               "haces bien en descartarlas")
    return (f"La mejor apuesta que dejaste pasar cada día habría ganado {c['ganadas']} de {total} veces "
            f"({c['unidades']:+.2f} unidades apostando 1 cada vez): {consejo}.")


# --- Lección de cada día ----------------------------------------------------------------------------------
def guardar_leccion(agente: dict, texto: str, fecha: str, apuestas: int) -> None:
    texto = str(texto or "").strip()[:400]
    if texto:
        agente["lecciones"] = (agente.get("lecciones", []) + [{"fecha": fecha, "texto": texto, "apuestas": apuestas}])[-MAX_LECCIONES:]


def texto_lecciones(agente: dict, maximo: int = 3) -> str:
    return "\n".join(f"- {x['fecha']}: {x['texto']}" for x in agente.get("lecciones", [])[-maximo:]) or "(ninguna todavía)"


# --- Biblioteca común -------------------------------------------------------------------------------------
def poner_biblioteca(estado: dict, entradas: list, fecha: str) -> None:
    autores = {a["nombre"] for a in estado["agentes"]}
    nuevas = []
    for e in entradas:
        if isinstance(e, dict) and str(e.get("texto", "")).strip():
            autor = str(e.get("autor", "")).strip()
            nuevas.append({"texto": str(e["texto"]).strip()[:300], "autor": autor if autor in autores else "La oficina",
                           "fecha": str(e.get("fecha") or fecha)[:10]})
    if nuevas:
        estado["biblioteca"] = nuevas[:MAX_BIBLIOTECA]


def anadir_biblioteca(estado: dict, texto: str, autor: str, fecha: str) -> None:
    if texto:
        estado["biblioteca"] = (estado.get("biblioteca", []) + [{"texto": texto[:300], "autor": autor, "fecha": fecha}])[-MAX_BIBLIOTECA:]


def texto_biblioteca(estado: dict) -> str:
    b = estado.get("biblioteca", [])
    if not b:
        return ""
    return "BIBLIOTECA DE LA OFICINA (lo mejor que ha aprendido la oficina; tenlo presente)\n" + "\n".join(
        f"- {e['texto']} ({e['autor']}, {e['fecha']})" for e in b)


# --- La estrategia tonta ------------------------------------------------------------------------------------
def apuntar_tonta(estado: dict, cartelera: list[dict], momento: datetime) -> int:
    """Apunta una apuesta de 1 unidad al favorito de Pinnacle en cada partido de la cartelera, a la cuota de la casa."""
    t = estado.setdefault("tonta", {"apuestas": 0, "ganadas": 0, "unidades": 0.0, "pendientes": []})
    ya = {x["partido"] for x in t["pendientes"]} | set(t.get("vistos", []))
    n = 0
    for p in cartelera:
        fav = favorito(p)
        op = next((o for o in p["opciones"] if o["mercado"] == "h2h" and o["nombre"] == fav), None)
        if not fav or not op or p["id"] in ya or comun.fecha_hora(p["inicio"]) <= momento:
            continue
        t["pendientes"].append({"partido": p["id"], "jugadores": p["jugadores"], "inicio": p["inicio"], "mercado": "h2h",
                                "seleccion": fav, "punto": None, "cuota": op["cuota"]})
        n += 1
    return n


def liquidar_tonta(estado: dict, partidos: list[dict], momento: datetime) -> int:
    t = estado.get("tonta")
    if not t:
        return 0
    quedan, n = [], 0
    for x in t["pendientes"]:
        r = resultados.buscar(x, partidos) if comun.fecha_hora(x["inicio"]) < momento else None
        puntos = boletos.puntuar(x, r) if r else None
        if puntos is None:
            # Sin resultado en 4 días se olvida
            if (momento - comun.fecha_hora(x["inicio"])).days < 4:
                quedan.append(x)
            continue
        t["vistos"] = (t.get("vistos", []) + [x["partido"]])[-400:]
        if puntos == 0:
            continue
        t["apuestas"] += 1
        t["ganadas"] += int(puntos > 0)
        t["unidades"] = round(t["unidades"] + (x["cuota"] - 1 if puntos > 0 else -1), 3)
        n += 1
    t["pendientes"] = quedan
    return n


def resumen_tonta(estado: dict) -> dict | None:
    t = estado.get("tonta")
    if not t or not t["apuestas"]:
        return None
    return {"apuestas": t["apuestas"], "aciertos": t["ganadas"] / t["apuestas"], "yield": t["unidades"] / t["apuestas"]}


def texto_tonta(estado: dict, agente: dict | None = None, apuestas: list[dict] | None = None) -> str:
    r = resumen_tonta(estado)
    if not r:
        return ""
    texto = (f"LA ESTRATEGIA TONTA (apostar siempre lo mismo al favorito de Pinnacle en todos los partidos): "
             f"{r['apuestas']} apuestas, acierta el {r['aciertos']:.0%} y su rendimiento es {r['yield']:+.1%}.")
    if agente is not None and apuestas is not None:
        mio = boletos.resumen([a for a in apuestas if a["agente"] == agente["id"]])
        if mio["apuestas"]:
            mejor = mio["yield"] > r["yield"]
            texto += (f" El tuyo es {mio['yield']:+.1%}: " + ("le ganas, tu método aporta algo." if mejor else
                      "NO le ganas: tu método todavía no aporta nada frente a apostar al favorito."))
    return texto
