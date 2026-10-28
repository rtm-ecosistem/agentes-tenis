"""Noticias de tenis: Punto de Break, Tennis.com, la ATP, la WTA y Google Noticias con el nombre de cada jugador
del día. Solo se guardan titulares, enlaces y un resumen corto de los últimos días."""

from __future__ import annotations

import hashlib
import html
import re
import xml.etree.ElementTree as ET
from datetime import timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import requests

from agentes import comun, config

GOOGLE = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={gl}:{idioma}"
CABECERAS = {"User-Agent": "Mozilla/5.0 (compatible; oficina-tenis/1.0)"}


def _texto(nodo, etiqueta: str) -> str:
    el = nodo.find(etiqueta)
    return (el.text or "").strip() if el is not None and el.text else ""


def _limpiar(t: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t or ""))).strip()


def leer_rss(xml: bytes | str, fuente: str) -> list[dict]:
    raiz = ET.fromstring(xml)
    noticias = []
    for item in raiz.iter("item"):
        titulo = _limpiar(_texto(item, "title"))
        if not titulo:
            continue
        enlace = _texto(item, "link")
        try:
            fecha = comun.iso(parsedate_to_datetime(_texto(item, "pubDate")))
        except (TypeError, ValueError):
            fecha = comun.iso(comun.ahora())
        origen = _texto(item, "source") or fuente
        noticias.append({"id": hashlib.sha1((enlace or titulo).encode()).hexdigest()[:12], "titulo": titulo,
                         "resumen": _limpiar(_texto(item, "description"))[:400], "enlace": enlace, "fecha": fecha,
                         "fuente": origen})
    return noticias


def _descargar(url: str, fuente: str, sesion) -> list[dict]:
    try:
        r = sesion.get(url, headers=CABECERAS, timeout=30)
        r.raise_for_status()
        return leer_rss(r.content, fuente)
    except (requests.RequestException, ET.ParseError) as e:
        print(f"Noticias: no se pudo leer {fuente} ({url[:80]}): {e}")
        return []


def google(consulta: str, idioma: str = "es") -> str:
    gl = "ES" if idioma == "es" else "US"
    return GOOGLE.format(q=quote(consulta), hl=idioma if idioma == "es" else "en-US", gl=gl, idioma=idioma)


def recoger(jugadores: list[str], sesion=None) -> dict:
    """Junta las noticias nuevas con las guardadas y quita las de hace más de una semana."""
    sesion = sesion or requests.Session()
    nuevas = []
    for f in config.FUENTES_NOTICIAS:
        leidas = _descargar(f["rss"], f["nombre"], sesion) if f["rss"] else []
        if not leidas:  # sin RSS propio, o caído: la misma web a través de Google Noticias
            leidas = _descargar(google(f"site:{f['sitio']} when:3d", f["idioma"]), f["nombre"], sesion)
        for n in leidas:
            n["fuente"] = f["nombre"]
        nuevas += leidas
    for j in jugadores[:config.MAX_JUGADORES_NOTICIAS]:
        for n in _descargar(google(f'"{j}" when:3d', "es"), "Google Noticias", sesion)[:6]:
            n["jugador"] = j
            nuevas.append(n)
    guardadas = comun.leer(config.NOTICIAS, {"noticias": []})
    limite = comun.iso(comun.ahora() - timedelta(days=config.DIAS_NOTICIAS))
    por_id = {n["id"]: n for n in guardadas.get("noticias", []) if n["fecha"] >= limite}
    for n in nuevas:
        if n["fecha"] >= limite:
            previa = por_id.get(n["id"], {})
            por_id[n["id"]] = {**n, **({"jugador": previa["jugador"]} if previa.get("jugador") and not n.get("jugador") else {})}
    datos = {"actualizado": comun.iso(comun.ahora()),
             "noticias": sorted(por_id.values(), key=lambda n: n["fecha"], reverse=True)[:800]}
    comun.guardar(config.NOTICIAS, datos)
    return datos


def de_jugador(datos: dict, jugador: str, maximo: int = 5) -> list[dict]:
    apellidos = {c.split("|")[0] for c in comun.claves_completas(jugador)}
    salida = []
    for n in datos.get("noticias", []):
        t = comun.sin_tildes(f"{n['titulo']} {n.get('resumen', '')}").lower()
        if (n.get("jugador") and comun.mismo_jugador(n["jugador"], jugador)) or any(
                len(a) > 3 and re.search(rf"\b{re.escape(a)}\b", t) for a in apellidos):
            salida.append(n)
        if len(salida) >= maximo:
            break
    return salida


def generales(datos: dict, maximo: int = 25) -> list[dict]:
    return [n for n in datos.get("noticias", []) if not n.get("jugador")][:maximo]


def lista(noticias: list[dict]) -> str:
    return "\n".join(f"- [{n['fuente']}, {n['fecha'][:10]}] {n['titulo']}" + (f": {n['resumen'][:180]}" if n.get("resumen") else "")
                     for n in noticias) or "- (sin noticias)"
