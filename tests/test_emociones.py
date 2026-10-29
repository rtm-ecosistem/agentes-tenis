from datetime import timedelta

from agentes import comun, config, emociones, oficina, prompts, web
from tests.conftest import AHORA
from tests.test_ciclo import decidir


def liquidada(agente, i, ganancia, cuota=2.0, confianza=1, emocion=None):
    return {"id": f"x{i}", "agente": agente["id"], "bote": "1", "hora": comun.iso(AHORA - timedelta(days=3, minutes=-i)),
            "liquidada": comun.iso(AHORA - timedelta(days=2, minutes=-i)), "estado": "ganada" if ganancia > 0 else "perdida",
            "stake": 10.0, "cuota": cuota, "ganancia": ganancia, "pinnacle_cierre": None, "confianza": confianza,
            "descripcion": f"Apuesta {i}", "emocion": emocion, "fecha": "2026-10-26", "torneo": "t", "motivo": "m"}


def test_racha_perdedora_da_frustracion_y_revancha_segun_el_temperamento():
    estado = oficina.estado_inicial(AHORA)
    oscar, lola = estado["agentes"][0], estado["agentes"][1]
    assert oscar["temperamento"]["revancha"] == 0.5  # sale de la plantilla
    apuestas = [liquidada(a, i, -10.0) for a in (oscar, lola) for i in range(3)]
    for a in (oscar, lola):
        emociones.actualizar(a, estado, apuestas, AHORA)
    assert lola["animo"]["mezcla"]["revancha"] == 0.5
    assert oscar["animo"]["mezcla"]["revancha"] == 0.25  # Óscar es frío: la siente la mitad
    assert emociones.dominante(lola)["emocion"] in ("revancha", "frustracion")
    assert "revancha" in emociones.texto(lola).lower()


def test_las_emociones_se_apagan_en_dos_dias():
    agente = {"id": "a", "temperamento": {}}
    emociones.sentir(agente, [("euforia", 0.8, "racha")], AHORA)
    emociones.sentir(agente, [], AHORA + timedelta(hours=48))
    assert abs(agente["animo"]["mezcla"]["euforia"] - 0.4) < 0.01
    emociones.sentir(agente, [], AHORA + timedelta(days=20))
    assert "euforia" not in agente["animo"]["mezcla"]
    assert emociones.dominante(agente)["emocion"] == "calma"


def test_sucesos_al_liquidar_se_suman():
    agente = {"id": "a", "temperamento": {}}
    emociones.por_liquidadas(agente, [{"ganancia": 15.0, "cuota": 3.0, "descripcion": "Ruud gana"},
                                      {"ganancia": -30.0, "cuota": 1.8, "confianza": 3, "descripcion": "Sinner -3.5"}], AHORA)
    m = agente["animo"]["mezcla"]
    assert m["orgullo"] == 0.35 and m["arrepentimiento"] == 0.3


def test_temperamento_de_un_fichaje_se_limpia():
    assert emociones.temperamento_valido({"revancha": 5, "pena": 1.2, "calma": "0.2", "miedo": "x"}) == {"revancha": 2.0, "calma": 0.5}


def test_cada_boleto_guarda_su_emocion_y_el_analista_lee_su_animo():
    ia, estado, apuestas = decidir({"Óscar": [{"seleccion": "P01b", "confianza": 2, "motivo": "Elo"}]})
    oscar = next(a for a in estado["agentes"] if a["id"] == "estadistico-1")
    boleto = next(a for a in apuestas if a["agente"] == "estadistico-1")
    assert boleto["emocion"] in emociones.EMOCIONES
    assert oscar["informes"][-1]["emocion"] == boleto["emocion"]
    mensaje = [m for i, m in ia.mensajes if i.startswith("Eres Óscar,")][0]
    assert "TU ÁNIMO AHORA" in mensaje
    assert estado["emociones_desde"]
    datos = comun.leer(config.WEB_DIR / "datos.json", {})
    assert datos["emociones"]["despues"]["pendientes"] == len(apuestas)
    assert datos["agentes"][0]["animo"]["mezcla"]


def test_interruptor_quita_el_animo_de_la_decision(monkeypatch):
    monkeypatch.setattr(config, "EMOCIONES_EN_DECISION", False)
    ia, estado, apuestas = decidir({"Óscar": [{"seleccion": "P01b", "confianza": 2, "motivo": "Elo"}]})
    mensaje = [m for i, m in ia.mensajes if i.startswith("Eres Óscar,")][0]
    assert "TU ÁNIMO AHORA" not in mensaje
    assert apuestas[0]["emocion"]  # se sigue apuntando para poder comparar


def test_con_que_animo_acierta():
    agente = {"id": "a"}
    lista = [liquidada(agente, 0, 10.0, emocion="calma"), liquidada(agente, 1, -10.0, emocion="revancha"),
             liquidada(agente, 2, -10.0, emocion="revancha"), liquidada(agente, 3, 10.0)]
    c = emociones.por_emocion(lista)
    assert c["calma"]["ganadas"] == 1 and c["revancha"] == {"apuestas": 2, "ganadas": 0, "ganancia": -20.0, "yield": -1.0}
    assert "con revancha 0 de 2" in emociones.texto_notas(lista)
    estado = oficina.estado_inicial(AHORA)
    oscar = estado["agentes"][0]
    assert "según tu ánimo" in prompts.mensaje_vida(oscar, [liquidada(oscar, 0, -10.0, emocion="revancha")])
    assert web.comparar_emociones(estado, []) is None
