from datetime import timedelta

from agentes import aprendizaje, comun, oficina, prompts
from tests.conftest import AHORA, FakeIA
from tests.test_ciclo import decidir


def apuesta(estado, mercado="h2h", cuota=2.0, prob=0.6, superficie="clay", ganancia=10.0, cierre=1.9):
    return {"agente": "estadistico-1", "estado": estado, "mercado": mercado, "cuota": cuota, "probabilidad": prob,
            "superficie": superficie, "stake": 10.0, "ganancia": ganancia, "pinnacle_cierre": cierre}


def test_desglose_y_probabilidades():
    lista = [apuesta("ganada"), apuesta("perdida", ganancia=-10.0), apuesta("ganada", mercado="totals", cuota=1.5, prob=0.75),
             apuesta("pendiente")]
    d = aprendizaje.desglose(lista)
    assert d["mercado"]["ganador"]["apuestas"] == 2 and d["mercado"]["total de juegos"]["ganancia"] == 10.0
    assert d["superficie"]["tierra"]["apuestas"] == 3
    assert "cuotas bajas (< 1.60)" in d["cuota"]
    filas = {f["desde"]: f for f in aprendizaje.calibracion(lista)}
    assert filas[0.6]["apuestas"] == 2 and filas[0.6]["salio"] == 0.5 and filas[0.6]["dijo"] == 0.6
    assert filas[0.7]["salio"] == 1.0
    assert "Por mercado" in aprendizaje.texto_desglose(lista)


class IAReglas(FakeIA):
    def __init__(self, reglas):
        super().__init__()
        self.reglas = reglas

    def pedir_json(self, instrucciones, mensaje, esquema=None):
        self.mensajes.append((instrucciones, mensaje))
        return {"reflexion": "Semana floja.", "reglas": self.reglas}


def test_reglas_como_mucho_tres_y_se_retiran():
    estado = oficina.estado_inicial(AHORA)
    oficina.reflexiones(estado, [], IAReglas(["Nada de totales en tierra", "Cuota mínima 1.70"]), AHORA)
    oscar = estado["agentes"][0]
    assert [r["texto"] for r in oscar["reglas"]] == ["Nada de totales en tierra", "Cuota mínima 1.70"]
    luego = AHORA + timedelta(days=7)
    ia = IAReglas(["Cuota mínima 1.70", "Solo si bato a Pinnacle", "Máximo 2 apuestas", "Una cuarta"])
    oficina.reflexiones(estado, [], ia, luego)
    assert [r["texto"] for r in oscar["reglas"]] == ["Cuota mínima 1.70", "Solo si bato a Pinnacle", "Máximo 2 apuestas"]
    assert oscar["reglas"][0]["desde"] == comun.hoy_madrid(AHORA)  # la que mantiene conserva su fecha
    assert oscar["reglas_retiradas"][0]["texto"] == "Nada de totales en tierra"
    assert "Nada de totales en tierra" in ia.mensajes[0][1]  # en la reflexión revisa las que tenía
    assert "Cuota mínima 1.70" in prompts.memoria(oscar, [])


def test_las_reglas_y_el_historial_llegan_al_decidir():
    ia, estado, apuestas = decidir({"Óscar": [{"seleccion": "P01b", "confianza": 1, "probabilidad": 0.55, "motivo": "Elo"}],
                                    "Lola": [{"seleccion": "P02a", "confianza": 1, "probabilidad": 62, "motivo": "x"}]})
    assert {a["agente"]: a["probabilidad"] for a in apuestas} == {"estadistico-1": 0.55, "reportero-1": 0.62}
    oscar = [m for i, m in ia.mensajes if i.startswith("Eres Óscar,")][0]
    assert "TUS REGLAS" in oscar and "DÓNDE GANAS Y DÓNDE PIERDES" in oscar and "TUS PROBABILIDADES" in oscar
    manager = [m for i, m in ia.mensajes if i.startswith("Eres Inés,")][0]
    assert "Su historial" in manager
    sala = estado["sala"][-1]["partidos"][0]
    assert sala["favorito"] == "Carlos Alcaraz" and sala["id"] == "e1"


def test_la_sala_se_puntua_con_la_ultima_opinion():
    inicio = comun.iso(AHORA - timedelta(hours=5))
    def opinion(vista, pid="e1", jug=("Ana A", "Bea B")):
        return {"partido": "P01", "id": pid, "jugadores": list(jug), "inicio": inicio, "favorito": jug[0], "vista": vista, "motivo": ""}
    estado = {"sala": [{"hora": "1", "partidos": [opinion("favorito")]},
                       {"hora": "2", "partidos": [opinion("sorpresa"), opinion("favorito", "e2", ("Cris C", "Dani D")),
                                                  opinion("dudoso", "e3", ("Eva E", "Fe F"))]}]}
    partidos = [{"jugadores": ["Bea B", "Ana A"], "ganador": 0, "completo": True, "fecha": inicio[:10]},
                {"jugadores": ["Cris C", "Dani D"], "ganador": 0, "completo": True, "fecha": inicio[:10]},
                {"jugadores": ["Eva E", "Fe F"], "ganador": 1, "completo": True, "fecha": inicio[:10]}]
    assert aprendizaje.puntuar_sala(estado, partidos, AHORA) == 2
    m = estado["sala_aciertos"]
    assert m["sorpresa"] == [1, 1] and m["favorito"] == [1, 1]  # la opinión vieja de e1 no cuenta
    assert estado["sala"][0]["partidos"][0]["acierto"] is None
    assert aprendizaje.puntuar_sala(estado, partidos, AHORA) == 0  # no se cuentan dos veces
    assert "acertasteis 1 de 1" in aprendizaje.texto_sala_aciertos(estado)


def test_cansancio_de_los_ultimos_tres_dias():
    from agentes import config, resultados
    hoy = AHORA.date()
    comun.guardar(config.RESULTADOS, {"dias": [], "partidos": [
        {"fecha": (hoy - timedelta(days=1)).isoformat(), "jugadores": ["Alex de Minaur", "Tommy Paul"], "ganador": 0,
         "sets": [[6, 7], [7, 6], [7, 5]], "completo": True},
        {"fecha": (hoy - timedelta(days=2)).isoformat(), "jugadores": ["Holger Rune", "Alex de Minaur"], "ganador": 1,
         "sets": [[4, 6], [3, 6]], "completo": True},
        {"fecha": (hoy - timedelta(days=9)).isoformat(), "jugadores": ["Alex de Minaur", "X Y"], "ganador": 0,
         "sets": [[6, 0], [6, 0]], "completo": True}]})
    c = resultados.cansancio("Alex de Minaur", AHORA, resultados.historial()["partidos"])
    assert c["partidos"] == 2 and c["sets"] == 5 and c["juegos"] == 57
    assert c["ultimo"]["rival"] == "Tommy Paul" and c["ultimo"]["marcador"] == "6-7 7-6 7-5" and c["ultimo"]["gano"]
    assert "partido largo" in resultados.texto_cansancio("Alex de Minaur", c)
    ia, _, _ = decidir({})
    lola = [m for i, m in ia.mensajes if i.startswith("Eres Lola,")][0]
    assert "CANSANCIO" in lola and "Tommy Paul" in lola
    assert "CANSANCIO" in [m for i, m in ia.mensajes if i.startswith("Sois la sala")][0]


def test_la_ficha_del_partido_guarda_sus_datos_siete_dias():
    from agentes import config
    _, estado, _ = decidir({})
    info = estado["partidos_info"]["e1"]
    assert info["jugadores"] == ["Carlos Alcaraz", "Alex de Minaur"]
    assert info["detalle"][0]["mercado"] is not None and "cansancio" in info["detalle"][1]
    assert "e1" in comun.leer(config.WEB_DIR / "datos.json", {})["partidos_info"]
    estado["partidos_info"]["viejo"] = {**info, "inicio": comun.iso(AHORA - timedelta(days=8))}
    from agentes import sala
    sala.guardar_analisis(estado, [], {}, {}, AHORA)
    assert "viejo" not in estado["partidos_info"] and "e1" in estado["partidos_info"]
