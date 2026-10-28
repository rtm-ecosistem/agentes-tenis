"""Utilidades comunes: leer y guardar JSON, la hora española y los nombres de los jugadores."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from agentes import config

MADRID = ZoneInfo(config.ZONA)


def leer(ruta: Path, defecto):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return defecto


def guardar(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def fecha_hora(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def iso(momento: datetime) -> str:
    return momento.astimezone(timezone.utc).isoformat(timespec="minutes")


def hoy_madrid(momento: datetime | None = None) -> str:
    return (momento or ahora()).astimezone(MADRID).date().isoformat()


def sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def _limpio(texto: str) -> str:
    return re.sub(r"[^a-z ]", "", sin_tildes(texto).lower().replace("-", " ").replace("'", "")).strip()


def clave_abreviada(nombre: str) -> str:
    """«Alcaraz C.», «De Minaur A.» o «Ramos-Vinolas A.» (como en tennis-data) → «alcaraz|c», «de minaur|a»..."""
    partes = nombre.strip().split()
    iniciales = []
    while len(partes) > 1 and re.fullmatch(r"[A-Za-zÀ-ÿ](?:[.\-][A-Za-zÀ-ÿ])*\.?", partes[-1]):
        iniciales.insert(0, partes.pop())
    if not iniciales:
        return claves_completas(nombre)[0]
    return f"{_limpio(' '.join(partes))}|{_limpio(iniciales[0])[:1]}"


def claves_completas(nombre: str) -> list[str]:
    """«Alex de Minaur» → posibles claves de más a menos apellidos: «de minaur|a», «minaur|a». Con dos apellidos
    («Carlos Alcaraz Garfia») también prueba solo el primero: «alcaraz|c»."""
    partes = _limpio(nombre).split()
    if len(partes) < 2:
        return [f"{partes[0] if partes else ''}|"]
    inicial = partes[0][0]
    claves = [f"{' '.join(partes[i:])}|{inicial}" for i in range(1, len(partes))]
    if len(partes) > 2:
        claves.append(f"{partes[1]}|{inicial}")
    return claves


def clave_completa(nombre: str) -> list[str]:
    return claves_completas(nombre)[-1:]


def buscar_jugador(nombre: str, tabla: dict) -> str | None:
    """La clave con la que `nombre` (nombre y apellidos) aparece en `tabla`, o None."""
    for clave in claves_completas(nombre):
        if clave in tabla:
            return clave
    return None


def mismo_jugador(a: str, b: str) -> bool:
    return bool(set(claves_completas(a)) & set(claves_completas(b)))
