"""La sala de analistas: un equipo común (datos, noticias, ambiente y un debate a favor y en contra del favorito)
que escribe varios informes al día. Cada informe es una sola llamada a la IA, para caber en la cuota gratuita."""

from __future__ import annotations

from datetime import datetime, timedelta

from agentes import aprendizaje, comun, config, prompts

MAX_HISTORIAL = 45  # unas dos semanas con tres informes al día


def escribir(estado: dict, cartelera: list[dict], elo: dict, datos_noticias: dict, ia, momento: datetime) -> dict | None:
    texto_cartelera, _ = prompts.codificar(cartelera, config.BOTES["1"]["mercados"])
    anterior = estado["sala"][-1] if estado.get("sala") else None
    try:
        r = ia.pedir_json(prompts.INSTRUCCIONES_SALA,
                          prompts.mensaje_sala(momento, texto_cartelera, prompts.datos_estadisticos(cartelera, elo),
                                               prompts.datos_noticias(cartelera, datos_noticias), anterior,
                                               aprendizaje.texto_sala_aciertos(estado),
                                               prompts.datos_cansancio(cartelera, momento)),
                          prompts.ESQUEMA_SALA)
    except Exception as e:  # noqa: BLE001
        print(f"La sala de analistas no pudo escribir su informe: {e}")
        return None
    debate = r.get("debate") if isinstance(r.get("debate"), dict) else {}
    por_codigo = {f"P{i:02d}": p for i, p in enumerate(cartelera, 1)}
    partidos = []
    for d in r.get("partidos") or []:
        if isinstance(d, dict) and d.get("partido") in por_codigo:
            p = por_codigo[d["partido"]]
            partidos.append({"partido": f"{d['partido']} ({p['jugadores'][0]} vs {p['jugadores'][1]})", "id": p["id"],
                             "jugadores": p["jugadores"], "inicio": p["inicio"], "favorito": aprendizaje.favorito(p),
                             "vista": d.get("vista") if d.get("vista") in ("favorito", "sorpresa", "dudoso") else "dudoso",
                             "motivo": str(d.get("motivo", "")).strip()})
    informe = {"hora": comun.iso(momento), "datos": str(r.get("datos", "")).strip(),
               "noticias": str(r.get("noticias", "")).strip(), "ambiente": str(r.get("ambiente", "")).strip(),
               "favorito": str(debate.get("favorito", "")).strip(), "contra": str(debate.get("contra", "")).strip(),
               "conclusion": str(r.get("conclusion", "")).strip(), "partidos": partidos[:8]}
    estado["sala"] = (estado.get("sala", []) + [informe])[-MAX_HISTORIAL:]
    return informe


def para_decidir(estado: dict, momento: datetime, maximo: int = 3) -> list[dict]:
    """Los informes de las últimas 24 horas (como mucho tres): el último entero y las conclusiones de los otros."""
    limite = comun.iso(momento - timedelta(hours=24))
    return [i for i in estado.get("sala", []) if i["hora"] > limite][-maximo:]
