from datetime import timedelta

from agentes import boletos, ciclo, comun, config, oficina
from tests.conftest import AHORA, FakeAPI, FakeAvisos, FakeIA, evento


def decidir(apuestas_ia, api=None):
    ia = FakeIA(apuestas_ia)
    ciclo.decision(momento=AHORA, api=api or FakeAPI(), ia=ia, avisos=FakeAvisos())
    return ia, comun.leer(config.ESTADO, None), comun.leer(config.APUESTAS, [])


def test_decision_apuesta_con_las_reglas():
    ia, estado, apuestas = decidir({
        "Óscar": [{"seleccion": "P01b", "confianza": 3, "motivo": "Elo"}],
        "Lola": [{"seleccion": "P02a", "confianza": 2, "motivo": "noticia"}, {"seleccion": "P99z", "confianza": 1, "motivo": "x"}],
        "Inés": [{"seleccion": "P01b", "confianza": 3, "motivo": "coinciden"}],
    })
    assert estado["casa"] == "williamhill"
    assert len(apuestas) == 3
    oscar = next(a for a in apuestas if a["agente"] == "estadistico-1")
    assert oscar["descripcion"] == "Alex de Minaur gana el partido"
    assert oscar["cuota"] == 2.05 and oscar["pinnacle_apuesta"] == 2.02 and oscar["stake"] == 30.0
    lola = next(a for a in apuestas if a["agente"] == "reportero-1")
    assert lola["stake"] == 20.0
    o = next(a for a in estado["agentes"] if a["id"] == "estadistico-1")
    assert o["botes"]["1"]["saldo"] == 970.0
    # La Manager lee lo que proponen los especialistas, y todos leen la sala
    manager = [m for i, m in ia.mensajes if i.startswith("Eres Inés,")][0]
    assert "LO QUE PROPONEN HOY LOS TRES ESPECIALISTAS" in manager and "Óscar" in manager
    assert "ÚLTIMO INFORME DE LA SALA" in manager
    assert len(estado["sala"]) == 1
    # Una propuesta que no está en la cartelera se rechaza
    assert any("no está en la cartelera" in r for r in next(a for a in estado["agentes"] if a["id"] == "reportero-1")["informes"][-1]["rechazos"])
    # Solo una decisión al día
    ciclo.decision(momento=AHORA + timedelta(hours=2), api=FakeAPI(), ia=FakeIA({"Óscar": [{"seleccion": "P01a", "confianza": 1, "motivo": ""}]}), avisos=FakeAvisos())
    assert len(comun.leer(config.APUESTAS, [])) == 3
    assert (config.WEB_DIR / "datos.json").exists()


def test_tope_del_diez_por_ciento_pendiente():
    eventos = [evento(f"e{i}", f"Jugador A{i}", f"Jugador B{i}", AHORA + timedelta(hours=2 + i)) for i in range(6)]
    _, _, apuestas = decidir({"Óscar": [{"seleccion": f"P0{i + 1}a", "confianza": 3, "motivo": ""} for i in range(6)]},
                             FakeAPI(eventos))
    suyas = [a for a in apuestas if a["agente"] == "estadistico-1"]
    assert sum(a["stake"] for a in suyas) <= 100.0
    assert [a["stake"] for a in suyas] == [30.0, 30.0, 30.0, 10.0]


def test_no_apuesta_en_directo_ni_dos_veces_el_mismo_mercado():
    eventos = [evento("e1", "Ana A", "Bea B", AHORA - timedelta(minutes=5)), evento("e2", "Cris C", "Dani D", AHORA + timedelta(hours=3))]
    _, _, apuestas = decidir({"Óscar": [{"seleccion": "P01a", "confianza": 1, "motivo": ""},
                                        {"seleccion": "P02a", "confianza": 1, "motivo": ""},
                                        {"seleccion": "P02b", "confianza": 1, "motivo": ""}]}, FakeAPI(eventos))
    assert [a["seleccion"] for a in apuestas] == ["Cris C"]


def test_cierre_guarda_pinnacle_y_liquida(monkeypatch):
    decidir({"Óscar": [{"seleccion": "P01b", "confianza": 3, "motivo": ""}, {"seleccion": "P01c", "confianza": 1, "motivo": ""},
                       {"seleccion": "P01e", "confianza": 1, "motivo": ""}]})
    cierre = [evento("e1", "Carlos Alcaraz", "Alex de Minaur", AHORA + timedelta(hours=4), pin=(1.70, 2.20))]
    api = FakeAPI(cierre=cierre)
    # A las 12:20 (falta menos de una hora para el partido) se guarda la cuota de cierre, solo de Pinnacle
    ciclo.cierre(momento=AHORA + timedelta(hours=3, minutes=15), api=api, ia=FakeIA(), avisos=FakeAvisos())
    apuestas = comun.leer(config.APUESTAS, [])
    assert api.llamadas[-1][2] == ("pinnacle",)
    assert {a["mercado"]: round(a["pinnacle_cierre"], 2) for a in apuestas} == {"h2h": 2.2, "spreads": 1.92, "totals": 1.89}
    assert boletos.bate_cierre(apuestas[0]) is False  # 2.05 < 2.20: el mercado no le dio la razón
    # Al acabar el partido: de Minaur gana 6-4 3-6 7-6 → 16 juegos a 16 (Alcaraz -3.5 pierde) y 32 juegos (más de 22.5)
    resultado = {"jugadores": ["Carlos Alcaraz", "Alex de Minaur"], "ganador": 1, "sets": [[4, 6], [6, 3], [6, 7]],
                 "completo": True, "fecha": "2026-10-29"}
    monkeypatch.setattr("agentes.resultados.descargar_espn", lambda dia, sesion=None: [resultado])
    ciclo.cierre(momento=AHORA + timedelta(hours=8), api=api, ia=FakeIA(), avisos=FakeAvisos())
    apuestas = comun.leer(config.APUESTAS, [])
    assert [a["estado"] for a in apuestas] == ["ganada", "perdida", "ganada"]
    o = next(a for a in comun.leer(config.ESTADO, None)["agentes"] if a["id"] == "estadistico-1")
    assert o["botes"]["1"]["saldo"] == round(1000 - 30 - 10 - 10 + 30 * 2.05 + 10 * 1.87, 2)


def test_retirada_anula():
    a = {"seleccion": "Carlos Alcaraz", "mercado": "h2h", "punto": None}
    assert boletos.puntuar(a, {"jugadores": ["Carlos Alcaraz", "X Y"], "ganador": 1, "sets": [[3, 1]], "completo": False}) == 0.0


def test_lineas_de_cuarto_y_empates():
    total = {"seleccion": "Over", "mercado": "totals", "punto": 22.0}
    res = {"jugadores": ["A B", "C D"], "ganador": 0, "sets": [[6, 4], [6, 6]], "completo": True}
    assert boletos.puntuar(total, res) == 0.0  # 22 juegos justos: se devuelve
    assert boletos.puntuar({**total, "punto": 21.75}, res) == 0.5  # media ganada (21.5 gana, 22 se devuelve)
    assert boletos.puntuar({**total, "punto": 22.25}, res) == -0.5
    spread = {"seleccion": "A B", "mercado": "spreads", "punto": -2.5}
    assert boletos.puntuar(spread, res) == -1.0  # 12-10: gana por 2, no cubre -2.5


def test_despido_y_sustituto():
    estado = oficina.estado_inicial(AHORA)
    oscar = estado["agentes"][0]
    apuestas = []
    for i in range(100):
        a = {"agente": oscar["id"], "bote": "1", "hora": comun.iso(AHORA + timedelta(minutes=i)), "estado": "pendiente",
             "stake": 10.0, "cuota": 1.9, "pinnacle_cierre": 2.0, "ganancia": None, "fecha": "2026-10-29",
             "descripcion": "x", "torneo": "t", "motivo": "m"}
        oscar["botes"]["1"]["saldo"] -= 10
        boletos.liquidar(a, oscar, -1.0 if i < 60 else 1.0, "r", AHORA)
        apuestas.append(a)
    avisos = FakeAvisos()
    oficina.revisar(estado, apuestas, FakeIA(), avisos, AHORA + timedelta(days=30))
    assert oscar["estado"] == "despedido" and oscar["carta"].startswith("Querido")
    nuevo = estado["agentes"][-1]
    assert nuevo["nombre"] == "Marta" and nuevo["rol"] == "estadistico" and nuevo["carta_recibida"] == oscar["carta"]
    assert nuevo["botes"]["1"]["saldo"] == 1000.0
    assert avisos.issues and "Despedido" in avisos.issues[0][0]


def test_revision_superada_si_bate_el_cierre():
    estado = oficina.estado_inicial(AHORA)
    oscar = estado["agentes"][0]
    apuestas = []
    for i in range(100):
        a = {"agente": oscar["id"], "bote": "1", "hora": comun.iso(AHORA + timedelta(minutes=i)), "estado": "pendiente",
             "stake": 10.0, "cuota": 2.1, "pinnacle_cierre": 2.0, "ganancia": None}
        oscar["botes"]["1"]["saldo"] -= 10
        boletos.liquidar(a, oscar, -1.0 if i < 60 else 1.0, "r", AHORA)
        apuestas.append(a)
    oficina.revisar(estado, apuestas, FakeIA(), FakeAvisos(), AHORA + timedelta(days=30))
    assert oscar["estado"] == "activo" and oscar["periodo"]["numero"] == 2


def test_reiniciar_archiva_la_prueba():
    decidir({"Óscar": [{"seleccion": "P01b", "confianza": 3, "motivo": ""}]})
    ciclo.reiniciar("australia-2027", AHORA + timedelta(days=60))
    estado = comun.leer(config.ESTADO, None)
    assert estado["temporada"]["nombre"] == "australia-2027" and estado["archivadas"] == ["prueba"]
    assert comun.leer(config.APUESTAS, None) == []
    assert (config.ARCHIVO / "prueba" / "apuestas.json").exists()


def test_noticias_cada_hora_actualizan_la_sala_y_permiten_apostar(monkeypatch):
    monkeypatch.setattr(config, "CREDITOS_NOTICIAS_DIA", 1)
    decidir({})
    noticias_hoy = {"noticias": []}
    monkeypatch.setattr("agentes.noticias.recoger", lambda jugadores, sesion=None: noticias_hoy)
    api = FakeAPI()
    # La primera hora solo se apunta lo que ya había; sin noticias nuevas no se llama a la IA ni se gastan créditos
    ia = FakeIA()
    ciclo.cierre(momento=AHORA + timedelta(minutes=65), api=api, ia=ia, avisos=FakeAvisos())
    ciclo.cierre(momento=AHORA + timedelta(minutes=125), api=api, ia=ia, avisos=FakeAvisos())
    assert ia.mensajes == [] and api.llamadas[1:] == []
    # Sale una noticia de Ruud: la sala escribe y deciden sobre su partido, con cuotas solo del ganador
    noticias_hoy["noticias"] = [{"id": "n1", "titulo": "Casper Ruud, con molestias en la espalda", "resumen": "",
                                 "enlace": "", "fecha": comun.iso(AHORA), "fuente": "Punto de Break", "jugador": "Casper Ruud"}]
    ia = FakeIA({"Óscar": [{"seleccion": "P01a", "confianza": 2, "motivo": "Ruud tocado"}]})
    ciclo.cierre(momento=AHORA + timedelta(minutes=185), api=api, ia=ia, avisos=FakeAvisos())
    estado, apuestas = comun.leer(config.ESTADO, None), comun.leer(config.APUESTAS, [])
    assert api.llamadas[-1][:2] == ("tennis_atp_paris_masters", ("h2h",))
    assert len(estado["sala"]) == 2
    assert [(a["seleccion"], a["mercado"]) for a in apuestas] == [("Jannik Sinner", "h2h")]
    assert "molestias" in [m for i, m in ia.mensajes if i.startswith("Eres Óscar,")][0]
    assert estado["creditos"]["noticias"]["gastados"] == 1
    # La misma noticia otra hora no vuelve a disparar nada, y el tope de créditos del día ya se ha pasado
    ia = FakeIA()
    ciclo.cierre(momento=AHORA + timedelta(minutes=245), api=api, ia=ia, avisos=FakeAvisos())
    assert ia.mensajes == []
    noticias_hoy["noticias"].append({**noticias_hoy["noticias"][0], "id": "n2", "titulo": "Ruud sí jugará"})
    llamadas = len(api.llamadas)
    ciclo.cierre(momento=AHORA + timedelta(minutes=305), api=api, ia=ia, avisos=FakeAvisos())
    assert len(api.llamadas) == llamadas and len(ia.mensajes) == 1   # solo la sala


def test_no_se_pagan_cuotas_de_torneos_sin_partidos():
    class DosTorneos(FakeAPI):
        def torneos(self):
            return super().torneos() + [{"key": "tennis_wta_vacio", "title": "WTA sin partidos", "active": True}]
    api = DosTorneos()
    decidir({}, api)
    assert [ll[0] for ll in api.llamadas] == ["tennis_atp_paris_masters"]
