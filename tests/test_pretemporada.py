import io
from datetime import date

from agentes import comun, config, oficina, pretemporada
from tests.conftest import AHORA, FakeIA

CAB = ["ATP", "Location", "Tournament", "Date", "Surface", "Round", "Winner", "Loser", "WRank", "LRank",
       "W1", "L1", "W2", "L2", "W3", "L3", "Comment", "B365W", "B365L", "PSW", "PSL"]


def fichero(filas):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(CAB)
    for f in filas:
        ws.append(f)
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


class Sesion:
    """tennis-data de mentira: 2026 con tres días de julio y un año anterior para el Elo."""

    def __init__(self):
        self.atp = fichero([
            [1, "x", "Hamburg", "2026-07-01", "Clay", "1R", "Alcaraz C.", "De Minaur A.", 2, 8, 6, 4, 6, 3, None, None, "Completed", 1.30, 3.60, 1.33, 3.70],
            [1, "x", "Hamburg", "2026-07-01", "Clay", "1R", "Ruud C.", "Sinner J.", 9, 1, 6, 4, 3, 6, 7, 5, "Completed", 3.40, 1.33, 3.60, 1.32],
            [1, "x", "Hamburg", "2026-07-02", "Clay", "2R", "Alcaraz C.", "Ruud C.", 2, 9, 2, 1, None, None, None, None, "Retired", 1.40, 3.00, 1.42, 3.05],
            [1, "x", "Hamburg", "2026-07-05", "Clay", "F", "Alcaraz C.", "Zverev A.", 2, 3, 6, 2, 6, 2, None, None, "Completed", 1.50, 2.60, 1.52, 2.70],
        ])
        self.viejo = fichero([[1, "x", "Paris", "2025-06-01", "Clay", "F", "Alcaraz C.", "Sinner J.", 2, 1, 6, 4, 6, 4, None, None, "Completed", 2.0, 1.8, 2.0, 1.85]])

    def get(self, url, headers=None, timeout=None):
        contenido = self.atp if url.endswith("/2026/2026.xlsx") else self.viejo if url.endswith("/2025/2025.xlsx") else None

        class R:
            def __init__(self, c):
                self.content = c

            def raise_for_status(self):
                if self.content is None:
                    raise RuntimeError("404")
        return R(contenido)


def test_nombres_de_tennis_data():
    assert pretemporada.nombre_completo("De Minaur A.") == "A. De Minaur"
    assert pretemporada.nombre_completo("Auger-Aliassime F.") == "F. Auger-Aliassime"
    assert comun.mismo_jugador("A. De Minaur", "Alex de Minaur")


def test_la_pretemporada_avanza_aprende_y_se_traslada():
    ia = FakeIA(descartes={"Óscar": "P01a", "Lola": "P01b", "Bruno": "P02a", "Inés": "P02b"})
    p = pretemporada.avanzar(2, "2026-07-01", "2026-07-06", ia=ia, sesion=Sesion(), solo_si_activa=True)
    assert p["dias"] == 0   # no está activada: no avanza sola
    p = pretemporada.avanzar(2, "2026-07-01", "2026-07-06", ia=ia, sesion=Sesion())
    assert p["dias"] == 2 and p["siguiente"] == "2026-07-03" and not p["terminada"]
    apuestas = comun.leer(config.DATOS / "pretemporada" / "apuestas.json", [])
    assert apuestas and all(a["practica"] and a["estado"] != "pendiente" for a in apuestas)
    # La retirada del día 2 anula las apuestas a ese partido
    assert {a["estado"] for a in apuestas if a["fecha"] == "2026-07-02"} <= {"nula"}
    # El cansancio del día 2 ve el partido del día 1 y nunca el del propio día
    sala = [m for i, m in ia.mensajes if i.startswith("Sois la sala")]
    assert "Alcaraz" in sala[1] and "2026-07-02" not in sala[1].split("CANSANCIO")[-1]
    p = pretemporada.avanzar(10, ia=ia, sesion=Sesion())
    assert p["terminada"] and p["dias"] == 3   # el 3 y el 4 no hay partidos
    # Lo aprendido pasa a la oficina; su dinero no se toca
    real = oficina.estado_inicial(AHORA)
    comun.guardar(config.ESTADO, real)
    real["agentes"][0]["reglas"] = []
    sim = comun.leer(config.DATOS / "pretemporada" / "estado.json", {})
    sim["agentes"][0]["reglas"] = [{"texto": "No apostar a cuotas bajas", "desde": "2026-07-05"}]
    sim["agentes"][0]["lecciones"] = [{"fecha": "2026-07-05", "texto": "Lección", "apuestas": 1}]
    comun.guardar(config.DATOS / "pretemporada" / "estado.json", sim)
    assert pretemporada.trasladar(AHORA)
    estado = comun.leer(config.ESTADO, None)
    oscar = estado["agentes"][0]
    assert oscar["reglas"][0]["texto"] == "No apostar a cuotas bajas" and oscar["lecciones"][0]["texto"] == "Lección"
    assert oscar["pretemporada"]["resumen"]["apuestas"] >= 1
    assert oscar["botes"]["1"]["saldo"] == config.BOTE_INICIAL
    assert estado["pretemporada"]["dias"] == 3
    assert not pretemporada.trasladar(AHORA)   # solo una vez
    from agentes import prompts
    assert "TU PRETEMPORADA" in prompts.memoria(oscar, [])


def test_dia_sin_cuota_de_la_ia_se_repite():
    class SinCuota(FakeIA):
        def pedir_json(self, instrucciones, mensaje, esquema=None):
            if instrucciones.startswith("Eres Lola,"):
                raise RuntimeError("429 sin cuota")
            return super().pedir_json(instrucciones, mensaje, esquema)
    p = pretemporada.avanzar(3, "2026-07-01", "2026-07-06", ia=SinCuota(), sesion=Sesion())
    assert p["dias"] == 0 and p["siguiente"] == "2026-07-01"
    assert comun.leer(config.DATOS / "pretemporada" / "apuestas.json", []) == []


def test_lee_los_ficheros_subidos_si_tennis_data_no_deja_descargar():
    class Bloqueada(Sesion):
        def get(self, url, headers=None, timeout=None):
            return super().get("nada")
    carpeta = config.DATOS / "tennis-data"
    carpeta.mkdir(parents=True)
    (carpeta / "2026.xlsx").write_bytes(Sesion().atp)
    p = pretemporada.avanzar(1, "2026-07-01", "2026-07-06", ia=FakeIA(descartes={"Óscar": "P01a"}), sesion=Bloqueada())
    assert p["dias"] == 1


def test_tope_diario_de_llamadas(monkeypatch):
    monkeypatch.setattr(config, "LLAMADAS_PRETEMPORADA_DIA", 15)
    p = pretemporada.avanzar(5, "2026-07-01", "2026-07-06", ia=FakeIA(), sesion=Sesion())
    assert p["dias"] == 1 and p["hoy"]["llamadas"] > 0   # un día (unas 9 llamadas) y para antes de pasarse
