"""Las pruebas trabajan en una carpeta temporal: nunca tocan los datos de verdad ni salen a internet."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from agentes import config

AHORA = datetime(2026, 10, 29, 8, 5, tzinfo=timezone.utc)  # 9:05 en España


@pytest.fixture(autouse=True)
def datos_temporales(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATOS", tmp_path / "datos")
    for nombre, fichero in (("ESTADO", "estado.json"), ("APUESTAS", "apuestas.json"), ("CARTELERA", "cartelera.json"),
                            ("NOTICIAS", "noticias.json"), ("ELO", "elo.json"), ("RESULTADOS", "resultados.json")):
        monkeypatch.setattr(config, nombre, tmp_path / "datos" / fichero)
    monkeypatch.setattr(config, "ARCHIVO", tmp_path / "datos" / "archivo")
    monkeypatch.setattr(config, "WEB_DIR", tmp_path / "web")
    monkeypatch.setattr("agentes.noticias.recoger", lambda jugadores, sesion=None: {"noticias": []})
    monkeypatch.setattr("agentes.elo.actualizar", lambda sesion=None, forzar=False: {"jugadores": {}, "h2h": {}})
    monkeypatch.setattr("agentes.resultados.descargar_espn", lambda dia, sesion=None: [])
    yield tmp_path


def evento(id_, a, b, inicio, wh=(1.80, 2.05), pin=(1.85, 2.02), spread=-3.5, total=22.5):
    def casa(clave, precios, extra=0.0):
        return {"key": clave, "title": clave, "markets": [
            {"key": "h2h", "outcomes": [{"name": a, "price": precios[0]}, {"name": b, "price": precios[1]}]},
            {"key": "spreads", "outcomes": [{"name": a, "price": 1.9 + extra, "point": spread},
                                            {"name": b, "price": 1.9 + extra, "point": -spread}]},
            {"key": "totals", "outcomes": [{"name": "Over", "price": 1.87 + extra, "point": total},
                                           {"name": "Under", "price": 1.93 + extra, "point": total}]}]}
    return {"id": id_, "sport_key": "tennis_atp_paris_masters", "sport_title": "ATP Paris Masters",
            "commence_time": (inicio).strftime("%Y-%m-%dT%H:%M:%SZ"), "home_team": a, "away_team": b,
            "bookmakers": [casa("williamhill", wh), casa("pinnacle", pin, 0.02)]}


class FakeAPI:
    def __init__(self, eventos=None, cierre=None):
        self.eventos = eventos if eventos is not None else [
            evento("e1", "Carlos Alcaraz", "Alex de Minaur", AHORA + timedelta(hours=4)),
            evento("e2", "Jannik Sinner", "Casper Ruud", AHORA + timedelta(hours=7), wh=(1.30, 3.60), pin=(1.28, 3.9)),
        ]
        self.cierre = cierre
        self.restantes, self.usados, self.gastados = 480, 20, 6
        self.llamadas = []

    def torneos(self):
        return [{"key": "tennis_atp_paris_masters", "title": "ATP Paris Masters", "active": True}]

    def cuotas(self, deporte, mercados, casas=None, desde=None, hasta=None):
        self.llamadas.append((deporte, tuple(mercados), tuple(casas or [])))
        return self.cierre if (self.cierre is not None and casas == ["pinnacle"]) else self.eventos

    def marcadores(self, deporte, dias=3):
        return []


class FakeIA:
    """Responde según quién pregunta: la sala, cada analista o las cartas."""

    def __init__(self, apuestas=None):
        self.apuestas = apuestas or {}
        self.mensajes = []

    def pedir_json(self, instrucciones, mensaje, esquema=None):
        self.mensajes.append((instrucciones, mensaje))
        if instrucciones.startswith("Sois la sala"):
            return {"datos": "d", "noticias": "n", "ambiente": "a", "debate": {"favorito": "f", "contra": "c"},
                    "conclusion": "conclusión", "partidos": [{"partido": "P01", "vista": "favorito", "motivo": "m"}]}
        if "te acaban de" in instrucciones:
            return {"carta": "Querido sustituto: apuesta menos."}
        if "acaba de despedir" in instrucciones:
            return {"nombre": "Marta", "personalidad": "Tranquila."}
        if "reflexión" in instrucciones:
            return {"reflexion": "Semana regular.", "regla": "Solo cuotas > Pinnacle."}
        for nombre, apuestas in self.apuestas.items():
            if instrucciones.startswith(f"Eres {nombre},"):
                return {"resumen": f"Decide {nombre}", "informe": {"jornada": "j", "a_favor": "a", "en_contra": "e",
                                                                   "riesgos": "r", "situacion": "s"},
                        "apuestas": apuestas, "descarte": ""}
        return {"resumen": "No apuesto", "informe": {}, "apuestas": []}


class FakeAvisos:
    def __init__(self):
        self.issues = []

    def crear_issue(self, titulo, cuerpo, etiquetas):
        self.issues.append((titulo, cuerpo, etiquetas))
        return len(self.issues)
