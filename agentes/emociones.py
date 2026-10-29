"""El ánimo de cada analista: una mezcla de emociones que sale de hechos (cómo va en el periodo, sus rachas, lo que
dejó pasar, si bate el cierre...) sin gastar ninguna llamada a la IA.

Cada analista tiene su temperamento (a quién la revancha le pesa el doble, a quién la euforia casi no le llega) y
las emociones se van apagando con los días: una mala racha le dura un par de días. Antes de decidir lee su ánimo
como un espejo de las trampas típicas del apostador y dice si le está influyendo; sus reglas siguen mandando y las
emociones nunca cambian por código lo que apuesta. Cada boleto guarda la emoción con la que se hizo, para que
aprenda con qué ánimo acierta y con cuál falla.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from agentes import boletos, comun, config, prompts

EMOCIONES = {
    "euforia": ("😄", "Euforia"), "confianza": ("😊", "Confianza"), "calma": ("😌", "Calma"),
    "alivio": ("😮‍💨", "Alivio"), "orgullo": ("😎", "Orgullo"), "tension": ("😬", "Tensión"),
    "frustracion": ("😤", "Frustración"), "miedo": ("😨", "Miedo"), "envidia": ("😒", "Envidia"),
    "aburrimiento": ("🥱", "Aburrimiento"), "arrepentimiento": ("😣", "Arrepentimiento"),
    "impaciencia": ("😑", "Impaciencia"), "codicia": ("🤑", "Codicia"), "sorpresa": ("😲", "Sorpresa"),
    "revancha": ("😠", "Revancha"),
}
VIDA_HORAS = 48.0        # cada dos días una emoción se queda en la mitad si nada la alimenta
MINIMO = 0.03            # por debajo se olvida
CALMA_BASE = 0.35        # sin nada que le mueva, el analista está en calma


def _pct(x: float, signo: bool = False) -> str:
    return (f"{x * 100:+.1f} %" if signo else f"{x * 100:.1f} %").replace(".", ",")


def temperamento_valido(t) -> dict[str, float]:
    """Solo emociones conocidas y multiplicadores entre 0,5 y 2 (lo que inventa la IA para un fichaje también)."""
    if not isinstance(t, dict):
        return {}
    limpio = {}
    for e, v in t.items():
        try:
            if e in EMOCIONES:
                limpio[e] = round(min(2.0, max(0.5, float(v))), 2)
        except (TypeError, ValueError):
            continue
    return limpio


def _apagar(animo: dict, ahora: datetime) -> None:
    try:
        horas = (ahora - datetime.fromisoformat(animo["hora"])).total_seconds() / 3600
    except (KeyError, ValueError, TypeError):
        horas = 0
    if horas > 0:
        factor = 0.5 ** (horas / VIDA_HORAS)
        animo["mezcla"] = {e: v * factor for e, v in animo["mezcla"].items()}
    animo["hora"] = comun.iso(ahora)


def sentir(agente: dict, hechos: list[tuple[str, float, str]], ahora: datetime, sumar: bool = False) -> None:
    """`hechos` = [(emoción, fuerza 0-1, motivo)]. Las situaciones (ir perdiendo, una racha) suben la emoción hasta
    su fuerza; los sucesos (cobrar una cuota alta) se suman a lo que ya sentía. El temperamento lo multiplica."""
    animo = agente.setdefault("animo", {"mezcla": {}, "motivos": {}, "hora": comun.iso(ahora)})
    _apagar(animo, ahora)
    temperamento = agente.get("temperamento", {})
    for emocion, fuerza, motivo in hechos:
        if emocion not in EMOCIONES:
            continue
        f = fuerza * temperamento.get(emocion, 1.0)
        actual = animo["mezcla"].get(emocion, 0.0)
        animo["mezcla"][emocion] = min(1.0, actual + f if sumar else max(actual, f))
        animo["motivos"][emocion] = motivo
    for e in [e for e, v in animo["mezcla"].items() if v < MINIMO]:
        animo["mezcla"].pop(e)
        animo["motivos"].pop(e, None)
    animo["mezcla"] = {e: round(v, 3) for e, v in animo["mezcla"].items()}


def mezcla(agente: dict) -> list[dict]:
    """Las emociones de ahora en porcentaje, de la que más pesa a la que menos."""
    animo = agente.get("animo") or {"mezcla": {}, "motivos": {}}
    valores = dict(animo["mezcla"])
    resto = sum(v for e, v in valores.items() if e != "calma")
    calma = max(valores.get("calma", 0.0), CALMA_BASE - resto)
    if calma > 0:
        valores["calma"] = calma
    total = sum(valores.values()) or 1
    filas = [{"emocion": e, "cara": EMOCIONES[e][0], "nombre": EMOCIONES[e][1], "pct": round(v / total, 3),
              "motivo": animo["motivos"].get(e) or ("No hay nada que le preocupe ni le emocione." if e == "calma" else "")}
             for e, v in valores.items()]
    return sorted(filas, key=lambda f: -f["pct"])


def dominante(agente: dict) -> dict:
    return mezcla(agente)[0]


def texto(agente: dict) -> str:
    filas = [f for f in mezcla(agente) if f["pct"] >= 0.1]
    lineas = "\n".join(f"- {f['nombre']} {f['pct'] * 100:.0f} %: {f['motivo']}" for f in filas)
    return ("TU ÁNIMO AHORA: lo que te ha pasado te empuja hacia estas emociones. No es una orden: es un espejo para "
            "que reconozcas las trampas en las que caen los apostadores (la euforia y la codicia tras una racha hacen "
            "apostar de más; la revancha empuja a perseguir lo perdido; el miedo, a no apostar cuando sí hay valor; la "
            "envidia, a perseguir lo que otros acertaron).\n" + lineas +
            "\nTu método y tus reglas van primero: decide como si no sintieras nada y di en \"animo\" cómo te sientes "
            "y cómo evitas que te influya.")


# --- Lo que le mueve: hechos que ya están en sus datos -------------------------------------------------

def _con_dinero(apuestas: list[dict], agente: dict) -> list[dict]:
    return sorted((a for a in apuestas if a["agente"] == agente["id"] and a["estado"] not in ("pendiente", "nula")
                   and a.get("liquidada")), key=lambda a: a["liquidada"])


def senales(agente: dict, estado: dict, apuestas: list[dict], momento: datetime) -> list[tuple[str, float, str]]:
    hechos = []
    s = prompts.situacion(agente, apuestas)
    rent = s["rentabilidad"]
    if rent < -config.PERDIDA_DESPIDO * 0.6:
        hechos.append(("miedo", 0.6, f"Pierde un {_pct(-rent)} en el periodo y el despido llega al {config.PERDIDA_DESPIDO:.0%}."))
    if rent < 0 and s["liquidadas"] and s["faltan"] <= 20:
        hechos.append(("miedo", 0.5, f"Le faltan {s['faltan']} apuestas para su revisión y va perdiendo."))
    if s["liquidadas"]:
        if rent > 0.05:
            hechos.append(("euforia", 0.4, f"Gana un {_pct(rent)} en el periodo."))
        elif rent > 0:
            hechos.append(("confianza", 0.35, f"Va ganando en el periodo ({_pct(rent, True)})."))
        elif rent > -0.03:
            hechos.append(("tension", 0.3, f"Va un poco por debajo de lo que empezó ({_pct(rent, True)})."))
        else:
            hechos.append(("tension", 0.45, f"Pierde un {_pct(-rent)} en el periodo y tiene que remontar."))

    hechas = _con_dinero(apuestas, agente)
    ultimas = hechas[-3:]
    if len(ultimas) == 3 and all((a["ganancia"] or 0) > 0 for a in ultimas):
        hechos += [("euforia", 0.3, "Sus 3 últimas apuestas han salido ganadoras."),
                   ("codicia", 0.35, "Con la racha le tienta apostar más y más alto.")]
    elif len(ultimas) == 3 and all((a["ganancia"] or 0) < 0 for a in ultimas):
        hechos += [("frustracion", 0.4, "Ha perdido sus 3 últimas apuestas."),
                   ("revancha", 0.5, "Le tienta recuperar enseguida lo que ha perdido.")]
    elif len(ultimas) >= 2 and sum((a["ganancia"] or 0) < 0 for a in ultimas) >= 2:
        hechos.append(("frustracion", 0.35, f"{sum((a['ganancia'] or 0) < 0 for a in ultimas)} de sus 3 últimas apuestas han salido mal."))
    if hechas:
        u = hechas[-1]
        if (u["ganancia"] or 0) < 0 and u["cuota"] < 1.45:
            hechos.append(("sorpresa", 0.4, f"Perdió con un favorito clarísimo: {u['descripcion']} @ {u['cuota']:.2f}."))
        if (u["ganancia"] or 0) < 0 and u.get("confianza") == 3:
            hechos.append(("arrepentimiento", 0.35, f"Puso su confianza máxima en {u['descripcion']} y la perdió."))

    con_cierre = [a for a in hechas[-20:] if boletos.bate_cierre(a) is not None]
    if len(con_cierre) >= 5:
        baten = sum(boletos.bate_cierre(a) for a in con_cierre)
        if baten / len(con_cierre) >= 0.6:
            hechos.append(("confianza", 0.35, f"Bate la cuota de cierre de Pinnacle en {baten} de sus últimas {len(con_cierre)} apuestas."))
        elif baten / len(con_cierre) <= 0.35:
            hechos.append(("tension", 0.3, f"Solo bate la cuota de cierre en {baten} de sus últimas {len(con_cierre)} apuestas."))

    jugados = [i["descarte_opcion"] for i in agente.get("informes", [])[-3:]
               if (i.get("descarte_opcion") or {}).get("puntos") is not None]
    if jugados and jugados[-1]["puntos"] > 0:
        d = jugados[-1]
        hechos.append(("envidia", 0.35, f"Dejó pasar {d['descripcion']} @ {d['cuota']:.2f} y habría ganado."))

    t = estado.get("tonta") or {}
    mio = boletos.resumen([a for a in apuestas if a["agente"] == agente["id"]])
    if t.get("apuestas", 0) >= 10 and mio["apuestas"] >= 10 and mio["yield"] > t["unidades"] / t["apuestas"]:
        hechos.append(("orgullo", 0.3, "Le está ganando a la estrategia tonta de apostar siempre al favorito."))

    if estado.get("ultima_decision"):
        suyas = [a["hora"] for a in apuestas if a["agente"] == agente["id"]]
        desde = comun.fecha_hora(max(suyas)) if suyas else comun.fecha_hora(agente["alta"])
        dias = (momento - desde) / timedelta(days=1)
        if dias >= 4:
            hechos.append(("aburrimiento", 0.45, f"Lleva {dias:.0f} días sin apostar."))
        elif dias >= 2:
            hechos.append(("impaciencia", 0.35, f"Lleva {dias:.0f} días sin ver ninguna apuesta clara."))

    # Cambio de signo en el periodo: alivio y orgullo al volver a ganar, frustración al empezar a perder
    antes = (agente.get("animo") or {}).get("rent")
    if s["liquidadas"] and antes is not None:
        if antes <= 0 < rent:
            hechos += [("alivio", 0.5, "Ha vuelto a ganar dinero en el periodo."), ("orgullo", 0.3, "Ha remontado.")]
        elif antes > 0 >= rent:
            hechos.append(("frustracion", 0.3, "Ha pasado de ganar a perder en el periodo."))
    return hechos


def actualizar(agente: dict, estado: dict, apuestas: list[dict], momento: datetime) -> dict:
    """Recalcula el ánimo (antes de decidir y cada hora). Devuelve la emoción que manda."""
    sentir(agente, senales(agente, estado, apuestas, momento), momento)
    agente["animo"]["rent"] = round(prompts.situacion(agente, apuestas)["rentabilidad"], 5)
    return dominante(agente)


def por_liquidadas(agente: dict, hechas: list[dict], momento: datetime) -> None:
    """Sucesos al cobrar o perder: una cuota alta cobrada da orgullo; perder con confianza máxima, arrepentimiento."""
    hechos = []
    for a in hechas:
        if (a["ganancia"] or 0) > 0 and a["cuota"] >= 2.5:
            hechos += [("orgullo", 0.35, f"Cobró {a['descripcion']} a {a['cuota']:.2f}."),
                       ("euforia", 0.2, f"Cobró {a['descripcion']} a {a['cuota']:.2f}.")]
        elif (a["ganancia"] or 0) < 0 and a.get("confianza") == 3:
            hechos.append(("arrepentimiento", 0.3, f"Perdió {a['descripcion']} con su confianza máxima."))
    if hechos:
        sentir(agente, hechos, momento, sumar=True)


# --- Con qué ánimo acierta y con cuál falla --------------------------------------------------------------

def por_emocion(apuestas: list[dict]) -> dict[str, dict]:
    """Por cada emoción con la que se apostó: apuestas, ganadas y rendimiento."""
    grupos: dict[str, list[dict]] = {}
    for a in apuestas:
        if a.get("emocion") in EMOCIONES and a["estado"] not in ("pendiente", "nula"):
            grupos.setdefault(a["emocion"], []).append(a)
    salida = {}
    for e, lista in grupos.items():
        r = boletos.resumen(lista)
        salida[e] = {"apuestas": r["apuestas"], "ganadas": sum((a["ganancia"] or 0) > 0 for a in lista),
                     "ganancia": r["ganancia"], "yield": round(r["yield"], 4)}
    return salida


def texto_notas(apuestas: list[dict]) -> str:
    cuentas = por_emocion(apuestas)
    if not cuentas:
        return ""
    partes = [f"con {EMOCIONES[e][1].lower()} {c['ganadas']} de {c['apuestas']} ganadas (rendimiento {c['yield']:+.1%})"
              for e, c in sorted(cuentas.items(), key=lambda kv: -kv[1]["apuestas"])]
    return "Cómo te salen las apuestas según tu ánimo al hacerlas: " + "; ".join(partes) + "."


def para_decidir(agente: dict, apuestas: list[dict]) -> str:
    """Lo que el analista lee de su ánimo antes de decidir (nada si las emociones están apagadas)."""
    if not config.EMOCIONES_EN_DECISION or not agente.get("animo"):
        return ""
    return "\n".join(t for t in (texto(agente), texto_notas([a for a in apuestas if a["agente"] == agente["id"]])) if t)
