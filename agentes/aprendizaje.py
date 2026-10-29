"""Lo que los analistas aprenden de sus apuestas: dónde ganan y dónde pierden, si aciertan las probabilidades que
dan, sus reglas de la semana y cómo acierta la sala con sus opiniones."""

from __future__ import annotations

from datetime import datetime

from agentes import boletos, comun, resultados

MAX_REGLAS = 3
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
