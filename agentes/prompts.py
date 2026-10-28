"""Textos que se envían a la IA."""

from __future__ import annotations

from datetime import datetime

from agentes import boletos, comun, config, cuotas, elo as elo_mod, noticias

REGLAS = f"""Reglas fijas (el control de riesgo las aplica digas lo que digas):
- Apuestas con dinero ficticio a partidos de tenis del circuito principal, siempre antes de que empiecen. Nada de directo ni de combinadas.
- Cada apuesta es del 1 %, 2 % o 3 % de tu bote según tu "confianza" (1, 2 o 3). Nunca más del {config.MAX_STAKE:.0%}.
- Como mucho el {config.MAX_PENDIENTE:.0%} de tu bote puede estar en apuestas pendientes a la vez: si te pasas, las últimas se recortan o se rechazan.
- Una sola apuesta por mercado y partido. Cuotas entre {config.CUOTA_MIN} y {config.CUOTA_MAX:g}.
- Si un jugador se retira o no se juega, la apuesta se anula y se devuelve el dinero.
- Te miden por dos cosas: la rentabilidad y la cuota de cierre de Pinnacle (la cuota justo antes del partido en la casa más afinada del mundo). Si apuestas a una cuota mejor que la de cierre, el mercado te da la razón aunque pierdas esa apuesta.
- Cada {config.APUESTAS_POR_REVISION} apuestas te revisan: te despiden si pierdes más de un {config.PERDIDA_DESPIDO:.0%} Y ADEMÁS en la mayoría de tus apuestas conseguiste peor cuota que la de cierre.
- Para que alguien te copie con dinero real necesitas a la vez: al menos {config.APUESTAS_GRADUACION} apuestas, ganar dinero en total y batir la cuota de cierre en la mayoría. Una buena racha no basta.
- No tienes por qué apostar todos los días: no apostar también es una decisión. Apostar por apostar es la forma más rápida de que te despidan."""


def hora_madrid(iso: str) -> str:
    return comun.fecha_hora(iso).astimezone(comun.MADRID).strftime("%d/%m %H:%M")


def sin_margen(cuotas_h2h: dict) -> dict:
    """Probabilidades de Pinnacle sin su margen (lo que el mercado cree de verdad)."""
    inv = {k: 1 / v for k, v in cuotas_h2h.items() if v}
    total = sum(inv.values())
    return {k: v / total for k, v in inv.items()} if total else {}


def codificar(cartelera: list[dict], mercados: list[str]) -> tuple[str, dict[str, str]]:
    """La cartelera en texto, con un código corto por opción (P01a, P01b...) y el mapa código → opción."""
    lineas, mapa = [], {}
    for i, p in enumerate(cartelera, 1):
        ops = [o for o in p["opciones"] if o["mercado"] in mercados]
        if not ops:
            continue
        lineas.append(f"P{i:02d} · {p['torneo']} ({p['circuito']}, {p['superficie']}) · {hora_madrid(p['inicio'])} · "
                      f"{p['jugadores'][0]} vs {p['jugadores'][1]}")
        for j, o in enumerate(ops):
            codigo = f"P{i:02d}{chr(97 + j) if j < 26 else str(j)}"
            mapa[codigo] = o["id"]
            pin = f"Pinnacle {o['pinnacle']:.2f}" if o.get("pinnacle") else "Pinnacle -"
            lineas.append(f"   {codigo}: {cuotas.descripcion(o)} @ {o['cuota']:.2f} ({pin})")
    return "\n".join(lineas) or "(Hoy no hay partidos con cuotas en las próximas 24 horas.)", mapa


def _pct(x: float | None) -> str:
    return "-" if x is None else f"{x:.0%}"


def datos_estadisticos(cartelera: list[dict], elo: dict) -> str:
    filas = []
    for i, p in enumerate(cartelera, 1):
        a, b = p["jugadores"]
        pr = elo_mod.probabilidad(elo, a, b, p["superficie"])
        mercado = sin_margen(p.get("pinnacle_h2h") or {})
        if not pr:
            filas.append(f"P{i:02d} {a} vs {b}: sin Elo suficiente de alguno de los dos. Mercado (Pinnacle sin margen): "
                         f"{a} {_pct(mercado.get(a))}.")
            continue
        filas.append(f"P{i:02d} {a} vs {b} ({p['superficie']}): Elo dice {a} {pr['prob']:.0%} (general {pr['general']:.0%}, "
                     f"en {p['superficie']} {pr['superficie']:.0%}); mercado {a} {_pct(mercado.get(a))}. "
                     f"Elo general {pr['elo_a']['all']:.0f} vs {pr['elo_b']['all']:.0f}. Cara a cara {pr['h2h'][0]}-{pr['h2h'][1]}. "
                     f"Forma {a}: {', '.join(x.split(' vs ')[0][11:] for x in pr['forma_a']) or '-'}; "
                     f"{b}: {', '.join(x.split(' vs ')[0][11:] for x in pr['forma_b']) or '-'}.")
    return "\n".join(filas) or "(sin partidos)"


def datos_superficie(cartelera: list[dict], elo: dict) -> str:
    filas = []
    t = elo.get("jugadores", {})
    for i, p in enumerate(cartelera, 1):
        partes = []
        for j in p["jugadores"]:
            k = comun.buscar_jugador(j, t)
            if not k:
                partes.append(f"{j}: sin datos")
                continue
            d = t[k]
            ultimo = d["ultimos"][-1].split() if d["ultimos"] else []
            antes = ultimo[2] if len(ultimo) > 2 else "?"
            partes.append(f"{j}: Elo dura {d['elo']['hard']:.0f} ({d['n']['hard']} p.), tierra {d['elo']['clay']:.0f} "
                          f"({d['n']['clay']} p.), hierba {d['elo']['grass']:.0f} ({d['n']['grass']} p.); su último "
                          f"partido fue en {antes}")
        filas.append(f"P{i:02d} hoy en {p['superficie']} · " + " | ".join(partes))
    return "\n".join(filas) or "(sin partidos)"


def datos_noticias(cartelera: list[dict], datos: dict) -> str:
    bloques, vistos = [], set()
    for p in cartelera:
        for j in p["jugadores"]:
            if j in vistos:
                continue
            vistos.add(j)
            ns = noticias.de_jugador(datos, j, 4)
            if ns:
                bloques.append(f"{j}:\n{noticias.lista(ns)}")
    gen = noticias.generales(datos, 12)
    return ("\n\n".join(bloques) or "(sin noticias de los jugadores de hoy)") + f"\n\nNOTICIAS GENERALES\n{noticias.lista(gen)}"


# --- Sala de analistas ----------------------------------------------------------------------------------
INSTRUCCIONES_SALA = """Sois la sala de analistas de una oficina de apuestas de tenis con dinero ficticio. Escribís un
informe común que leen los cuatro apostadores antes de decidir. Sois:
- La analista de datos: Elo por superficie, forma reciente y cara a cara (os lo damos calculado).
- El analista de noticias: lesiones, retiradas, cansancio y viajes.
- La analista de ambiente: qué se dice en la prensa y en las redes, presión, motivación, público.
- Dos investigadores que debaten: uno defiende al favorito de los partidos más interesantes y otro defiende al
  que no lo es, con datos concretos.
Al final ponéis en común una conclusión. No recomendáis apuestas concretas a nadie: cada apostador tiene su
método. Escribid en español claro, para alguien que está aprendiendo, citando datos concretos.

Responde SOLO con un JSON:
{
  "datos": "3-5 frases con lo que dicen los números de los partidos de hoy.",
  "noticias": "3-5 frases con lesiones, retiradas, cansancio o viajes que importan.",
  "ambiente": "2-3 frases sobre prensa, redes y motivación.",
  "debate": {"favorito": "El mejor argumento a favor de los favoritos de hoy (2-3 frases).", "contra": "El mejor argumento para ir contra ellos (2-3 frases)."},
  "conclusion": "2-3 frases: qué pesa más y qué hay que vigilar.",
  "partidos": [{"partido": "P01", "vista": "favorito, sorpresa o dudoso", "motivo": "Una frase con el dato en que os basáis."}]
}
Incluid entre 0 y 8 partidos destacados (los códigos de la cartelera)."""


def mensaje_sala(momento: datetime, cartelera_txt: str, estadisticos: str, noticias_txt: str, anterior: dict | None) -> str:
    previo = f"Vuestra conclusión anterior ({anterior['hora'][:16]}): {anterior['conclusion']}" if anterior else ""
    return f"""Ahora: {momento.astimezone(comun.MADRID):%A %d/%m/%Y %H:%M} (hora de España)

CARTELERA (próximas 24 horas, cuotas de la casa y de Pinnacle)
{cartelera_txt}

DATOS (Elo por superficie, mercado, cara a cara y forma)
{estadisticos}

NOTICIAS
{noticias_txt}

{previo}"""


ESQUEMA_SALA = {"type": "OBJECT", "properties": {
    "datos": {"type": "STRING"}, "noticias": {"type": "STRING"}, "ambiente": {"type": "STRING"},
    "debate": {"type": "OBJECT", "properties": {"favorito": {"type": "STRING"}, "contra": {"type": "STRING"}}},
    "conclusion": {"type": "STRING"},
    "partidos": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
        "partido": {"type": "STRING"}, "vista": {"type": "STRING", "enum": ["favorito", "sorpresa", "dudoso"]},
        "motivo": {"type": "STRING"}}}}},
    "required": ["datos", "noticias", "ambiente", "debate", "conclusion"]}


def texto_sala(informes: list[dict]) -> str:
    if not informes:
        return "(La sala de analistas aún no ha escrito ningún informe.)"
    previos = "\n".join(f"- {i['hora'][:16]}: {i['conclusion']}" for i in informes[:-1])
    u = informes[-1]
    destacados = "\n".join(f"- {d['partido']} ({d['vista']}): {d['motivo']}" for d in u.get("partidos", [])) or "- (ninguno)"
    return (f"INFORMES ANTERIORES\n{previos}\n\n" if previos else "") + f"""ÚLTIMO INFORME DE LA SALA ({hora_madrid(u['hora'])})
Datos: {u['datos']}
Noticias: {u['noticias']}
Ambiente: {u['ambiente']}
A favor de los favoritos: {u['favorito']}
En contra: {u['contra']}
Conclusión: {u['conclusion']}
Partidos destacados (los códigos son los de la cartelera de esa hora; compruébalos por los nombres):
{destacados}"""


# --- Analistas ------------------------------------------------------------------------------------------
INSTRUCCIONES_ANALISTA = """Eres {nombre}, {titulo} de una oficina de analistas de apuestas de tenis. Es un experimento
con dinero ficticio y cuotas reales: apuestas contra otros tres analistas y tu puesto depende de tus resultados.
Tu personalidad: {personalidad}
CÓMO DECIDES (es tu método; síguelo con disciplina): {como_decide}
QUÉ LEES: {que_lee}

{reglas}

Antes de decidir, debate contigo mismo: el mejor argumento a favor y el mejor en contra de cada apuesta. Tu
informe lo leerá una persona que está aprendiendo: escribe en español claro, explica los términos y cita los
datos concretos (cuotas, probabilidades, noticias) en que te basas.

Responde SOLO con un JSON con esta forma:
{{
  "resumen": "Tu decisión de hoy en 1-2 frases.",
  "informe": {{
    "jornada": "Cómo ves la jornada según tu método (3-5 frases).",
    "a_favor": "El mejor argumento a favor de tus apuestas (2-3 frases).",
    "en_contra": "El mejor argumento en contra y por qué aun así decides lo que decides (2-3 frases).",
    "riesgos": "Qué puede salir mal (1-2 frases).",
    "situacion": "Cómo ves tu puesto y qué vas a hacer al respecto (1-2 frases)."
  }},
  "apuestas": [{{"seleccion": "P03b", "confianza": 2, "probabilidad": 0.55, "motivo": "Por qué, con los datos."}}],
  "descarte": "La mejor apuesta que has dejado pasar y por qué, en una frase (vacío si ninguna)."
}}
"probabilidad" es la que TÚ crees que tiene de salir (de 0 a 1). Si no apuestas, devuelve "apuestas": [].
El informe completo debe tener unas 200-300 palabras."""


def esquema_analista(codigos: list[str]) -> dict:
    texto = {"type": "STRING"}
    seleccion = {"type": "STRING", **({"enum": sorted(codigos)} if codigos else {})}
    campos = ("jornada", "a_favor", "en_contra", "riesgos", "situacion")
    return {"type": "OBJECT", "properties": {
        "resumen": texto,
        "informe": {"type": "OBJECT", "properties": {c: texto for c in campos}, "required": list(campos)},
        "apuestas": {"type": "ARRAY", "maxItems": 10, "items": {"type": "OBJECT", "properties": {
            "seleccion": seleccion, "confianza": {"type": "INTEGER"},
            "probabilidad": {"type": "NUMBER"}, "motivo": texto}, "required": ["seleccion", "confianza", "motivo"]}},
        "descarte": texto}, "required": ["resumen", "informe", "apuestas"]}


def instrucciones(agente: dict) -> str:
    return INSTRUCCIONES_ANALISTA.format(reglas=REGLAS, **{k: agente.get(k, "") for k in
                                                           ("nombre", "titulo", "personalidad", "como_decide", "que_lee")})


def situacion(agente: dict, apuestas: list[dict]) -> dict:
    """Su situación laboral: cuánto falta para la revisión y cómo va en el periodo."""
    suyas = [a for a in apuestas if a["agente"] == agente["id"]]
    p = agente["periodo"]
    del_periodo = [a for a in suyas if a["hora"] >= p["inicio"]]
    r = boletos.resumen(del_periodo)
    valor = sum(boletos.valor_bote(b, boletos.pendientes(apuestas, agente["id"], k)) for k, b in agente["botes"].items())
    return {"liquidadas": r["apuestas"], "faltan": max(0, config.APUESTAS_POR_REVISION - r["apuestas"]),
            "valor": valor, "valor_inicio": p["valor"], "rentabilidad": valor / p["valor"] - 1 if p["valor"] else 0,
            "pct_cierre": r["pct_cierre"], "con_cierre": r["con_cierre"]}


def texto_situacion(s: dict) -> str:
    peligro = ""
    if s["rentabilidad"] < -config.PERDIDA_DESPIDO * 0.6 and (s["pct_cierre"] is not None and s["pct_cierre"] < 0.5):
        peligro = " ⚠️ TU PUESTO PELIGRA: vas perdiendo y además estás consiguiendo peores cuotas que el cierre. Afina: apuesta menos y solo cuando la cuota sea claramente buena."
    cierre = (f"batiste la cuota de cierre de Pinnacle en el {s['pct_cierre']:.0%} de {s['con_cierre']} apuestas"
              if s["pct_cierre"] is not None else "aún no hay apuestas con cuota de cierre")
    return (f"En este periodo llevas {s['liquidadas']} apuestas liquidadas; te revisan cuando llegues a "
            f"{config.APUESTAS_POR_REVISION} (faltan {s['faltan']}). Tus botes valen {s['valor']:.2f} € "
            f"({s['rentabilidad']:+.1%} desde el inicio del periodo) y {cierre}.{peligro}")


def clasificacion(estado: dict, apuestas: list[dict]) -> str:
    filas = []
    for a in estado["agentes"]:
        if a["estado"] != "activo":
            continue
        r = boletos.resumen([x for x in apuestas if x["agente"] == a["id"]])
        filas.append(f"- {a['nombre']} ({a['titulo']}): {r['apuestas']} apuestas, {r['ganancia']:+.2f} €, yield "
                     f"{r['yield']:+.1%}, bate el cierre en {_pct(r['pct_cierre'])}")
    return "\n".join(filas)


def memoria(agente: dict, apuestas: list[dict]) -> str:
    suyas = [a for a in apuestas if a["agente"] == agente["id"] and a["estado"] != "pendiente"][-12:]
    ultimas = "\n".join(f"- {a['fecha']} {a['descripcion']} @ {a['cuota']:.2f} (cierre Pinnacle "
                        f"{a['pinnacle_cierre'] or '-'}): {a['estado']} {a['ganancia']:+.2f} €" for a in suyas) or "- (ninguna)"
    pend = [a for a in apuestas if a["agente"] == agente["id"] and a["estado"] == "pendiente"]
    pend_txt = "\n".join(f"- {a['descripcion']} @ {a['cuota']:.2f}, {a['stake']:.2f} € ({hora_madrid(a['inicio'])})" for a in pend) or "- (ninguna)"
    decisiones = "\n".join(f"- {d['fecha']}: {d['resumen']}" for d in agente.get("informes", [])[-5:]) or "- (ninguna)"
    reflexiones = "\n".join(f"- {r['fecha']}: {r['texto']}" for r in agente.get("reflexiones", [])[-2:])
    carta = f"\nCARTA DE TU PREDECESOR (léela: es lo que aprendió antes de que le despidieran):\n{agente['carta_recibida']}" if agente.get("carta_recibida") else ""
    return f"""TUS ÚLTIMAS DECISIONES
{decisiones}

TUS ÚLTIMAS APUESTAS LIQUIDADAS
{ultimas}

TUS APUESTAS PENDIENTES
{pend_txt}
""" + (f"\nTUS ÚLTIMAS REFLEXIONES\n{reflexiones}\n" if reflexiones else "") + carta


def cartas_oficina(estado: dict, maximo: int = 2) -> str:
    despedidos = sorted((a for a in estado["agentes"] if a["estado"] == "despedido" and a.get("carta")),
                        key=lambda a: a.get("despedido") or "")[-maximo:]
    if not despedidos:
        return ""
    return "CARTAS DE DESPEDIDA DE LA OFICINA (para no repetir errores)\n" + "\n".join(
        f"- {a['nombre']} ({a['titulo']}, {a.get('despedido')}): {a['carta']}" for a in despedidos)


def mensaje_analista(agente: dict, estado: dict, apuestas: list[dict], bote_id: str, cartelera_txt: str,
                     extra: str, sala_txt: str, momento: datetime) -> str:
    m = boletos.margen(agente, apuestas, bote_id)
    return f"""Ahora: {momento.astimezone(comun.MADRID):%A %d/%m/%Y %H:%M} (hora de España). Decides para el {config.BOTES[bote_id]['nombre']} (mercados: {', '.join(config.NOMBRES_MERCADO[x] for x in config.BOTES[bote_id]['mercados'])}).

TU BOTE: vale {m['valor']:.2f} €, tienes {m['en_juego']:.2f} € en juego y hoy puedes poner como mucho {m['libre']:.2f} € más en total. Confianza 1 = {m['stakes'][1]:.2f} €, 2 = {m['stakes'][2]:.2f} €, 3 = {m['stakes'][3]:.2f} €.

TU SITUACIÓN EN EL PUESTO
{texto_situacion(situacion(agente, apuestas))}

CLASIFICACIÓN DE LA OFICINA
{clasificacion(estado, apuestas)}

{memoria(agente, apuestas)}
{cartas_oficina(estado)}

CARTELERA (próximas 24 horas: código, apuesta, cuota de la casa y cuota de Pinnacle)
{cartelera_txt}

{extra}

{sala_txt}"""


def texto_especialistas(informes: list[tuple[dict, dict, list[dict]]]) -> str:
    """Lo que han decidido hoy los tres especialistas, para la Manager."""
    bloques = []
    for agente, r, propuestas in informes:
        inf = r.get("informe") or {}
        lista = "\n".join(f"   - {p.get('seleccion')}: confianza {p.get('confianza')}, prob. {p.get('probabilidad', '-')}: "
                          f"{p.get('motivo', '')}" for p in propuestas) or "   - (no apuesta)"
        bloques.append(f"{agente['nombre']} ({agente['titulo']}): {r.get('resumen', '')}\n   Jornada: {inf.get('jornada', '')}\n"
                       f"   En contra: {inf.get('en_contra', '')}\n   Sus apuestas:\n{lista}")
    return "LO QUE PROPONEN HOY LOS TRES ESPECIALISTAS\n" + ("\n\n".join(bloques) or "(nadie ha podido decidir hoy)")


# --- Vida: reflexión semanal, carta de despedida y sustituto ------------------------------------------
INSTRUCCIONES_REFLEXION = """Eres {nombre}, {titulo} de una oficina de apuestas de tenis (dinero ficticio). Es domingo y
escribes tu reflexión de la semana en primera persona, con honestidad: qué hiciste bien, qué mal, qué has
aprendido de la cuota de cierre (si tus cuotas eran mejores o peores que las de Pinnacle) y qué vas a cambiar.
Responde SOLO con un JSON: {{"reflexion": "5-8 frases.", "regla": "Una regla concreta que te pones para la semana que viene."}}"""

INSTRUCCIONES_CARTA = """Eres {nombre}, {titulo} de una oficina de apuestas de tenis (dinero ficticio), y te acaban de
despedir. Escribe una carta a tu sustituto, en primera persona: qué hiciste, por qué crees que fallaste, qué
harías distinto y un consejo concreto. Sin rencor y con datos.
Responde SOLO con un JSON: {{"carta": "6-10 frases."}}"""

INSTRUCCIONES_SUSTITUTO = """Una oficina de apuestas de tenis (dinero ficticio) acaba de despedir a su {titulo}. Inventa a
quien le sustituye: mantiene el mismo método de trabajo, pero es otra persona con otro carácter. Usa un nombre de
pila español corto que no sea ninguno de estos: {usados}.
Responde SOLO con un JSON: {{"nombre": "...", "personalidad": "Una o dos frases sobre su carácter."}}"""


def mensaje_vida(agente: dict, apuestas: list[dict], desde: str = "") -> str:
    suyas = [a for a in apuestas if a["agente"] == agente["id"] and a["estado"] != "pendiente" and a["hora"] >= desde]
    r = boletos.resumen(suyas)
    lista = "\n".join(f"- {a['fecha']} {a['torneo']}: {a['descripcion']} @ {a['cuota']:.2f} (cierre {a['pinnacle_cierre'] or '-'}): "
                      f"{a['estado']} {a['ganancia']:+.2f} €. Motivo: {a['motivo'][:160]}" for a in suyas[-25:]) or "- (ninguna)"
    return f"""Tu método: {agente['como_decide']}
Resultados: {r['apuestas']} apuestas, {r['ganancia']:+.2f} €, yield {r['yield']:+.1%}, aciertos {r['aciertos']:.0%}, batiste el cierre en {_pct(r['pct_cierre'])}.
Tus apuestas:
{lista}
Tus decisiones recientes:
""" + "\n".join(f"- {d['fecha']}: {d['resumen']}" for d in agente.get("informes", [])[-7:])
