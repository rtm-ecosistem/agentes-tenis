"""Parámetros del experimento. Las claves vienen de variables de entorno (secretos de GitHub)."""

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
ESTADO = DATOS / "estado.json"
APUESTAS = DATOS / "apuestas.json"
CARTELERA = DATOS / "cartelera.json"
NOTICIAS = DATOS / "noticias.json"
ELO = DATOS / "elo.json"
RESULTADOS = DATOS / "resultados.json"
ARCHIVO = DATOS / "archivo"
ESTRATEGIAS = RAIZ / "estrategias"
WEB_DIR = RAIZ / "web"

ZONA = "Europe/Madrid"

# --- Dinero y riesgo (reglas fijas: ningún analista puede saltárselas) ------------------------------
BOTE_INICIAL = 1000.0
STAKE_POR_CONFIANZA = {1: 0.01, 2: 0.02, 3: 0.03}   # del 1 % al 3 % del bote, según lo seguro que esté
MAX_STAKE = 0.03
MAX_PENDIENTE = 0.10        # como mucho el 10 % del bote en apuestas pendientes a la vez
MIN_STAKE_EUR = 1.0
CUOTA_MIN = 1.10            # por debajo no compensa ni el riesgo de una retirada
CUOTA_MAX = 15.0

# Cada bote tiene sus mercados. El 2 arranca cuando haya una fuente gratis y fiable de esas cuotas.
BOTES = {
    "1": {"nombre": "Bote 1", "mercados": ["h2h", "spreads", "totals"], "activo": True},
    "2": {"nombre": "Bote 2", "mercados": ["h2h", "spreads", "totals", "set1", "sets_exactos"],
          "activo": os.environ.get("BOTE2_ACTIVO", "0").strip() == "1"},
}
NOMBRES_MERCADO = {"h2h": "Ganador del partido", "spreads": "Hándicap de juegos", "totals": "Total de juegos",
                   "set1": "Ganador del primer set", "sets_exactos": "Resultado exacto en sets"}

# --- Evaluación, despidos y paso a dinero real -----------------------------------------------------
APUESTAS_POR_REVISION = 100     # cada 100 apuestas liquidadas se revisa a cada analista
PERDIDA_DESPIDO = 0.10          # despido si pierde más de un 10 %...
# ...y además en la mayoría de sus apuestas consiguió peor cuota que la de cierre de Pinnacle
APUESTAS_GRADUACION = 500       # paso a dinero real: al menos 500 apuestas, gana dinero y bate el cierre en la mayoría

# --- Cuotas (The Odds API, plan gratis de unos 500 créditos al mes) ---------------------------------
ODDS_API = "https://api.the-odds-api.com/v4"
CASAS_ESPANA = ["williamhill", "sport888", "betsson"]    # con licencia en España; si empatan, William Hill
NOMBRES_CASA = {"williamhill": "William Hill", "sport888": "888sport", "betsson": "Betsson", "pinnacle": "Pinnacle"}
ARBITRO = "pinnacle"
CASA_FORZADA = os.environ.get("CASA", "").strip()        # para fijar la casa a mano si hiciera falta
CREDITOS_MES = 500
HORAS_VENTANA = 24              # la decisión mira los partidos de las 24 horas siguientes
CREDITOS_NOTICIAS_DIA = 4       # con noticias que la sala ve importantes, como mucho 4 créditos al día (1 por torneo afectado)
HORAS_ENTRE_CREDITOS_NOTICIAS = 2   # tras pedir cuotas por noticias, se esperan 2 horas para juntar más...
HORAS_URGENTE_NOTICIAS = 3          # ...salvo que el partido empiece dentro de menos de 3 horas
MINUTOS_SIN_APUESTAS = 30       # con noticias, solo partidos que empiezan dentro de más de media hora
MINUTOS_ANTES_CIERRE = 60       # la cuota de cierre se guarda en la hora antes del primer partido de la jornada
HORAS_CIERRE = 6                # una consulta de cierre por torneo vale para los partidos de las 6 horas siguientes
HORAS_JORNADA = 14              # una consulta de cierre vale para los partidos de las 14 horas siguientes
# Solo el circuito principal: fuera Challenger, ITF, WTA 125 y dobles
EXCLUIR_TORNEOS = ("challenger", "itf", "125", "doubles", "dobles", "utr", "exhibition")

# --- Horario (hora española) --------------------------------------------------------------------------
HORA_DECISION = 9
HORAS_SALA = (8, 14, 20)

# --- Emociones -------------------------------------------------------------------------------------------
# Con 0 los analistas dejan de leer su ánimo antes de decidir (se sigue calculando y guardando para comparar)
EMOCIONES_EN_DECISION = os.environ.get("EMOCIONES_EN_DECISION", "1").strip() != "0"

# --- IA -------------------------------------------------------------------------------------------------
PROVEEDOR_IA = os.environ.get("PROVEEDOR_IA", "gemini").strip() or "gemini"
MODELO_GEMINI = os.environ.get("MODELO_GEMINI", "gemini-3.8-flash").strip() or "gemini-3.8-flash"
MODELO_GEMINI_LIGERO = os.environ.get("MODELO_GEMINI_LIGERO", "gemini-3.5-flash-lite").strip() or "gemini-3.5-flash-lite"
MODELO_CLAUDE = os.environ.get("MODELO_CLAUDE", "claude-haiku-5-5").strip() or "claude-haiku-5-5"

# --- Noticias -------------------------------------------------------------------------------------------
# Cuantos más medios fiables, mejor. Si una fuente no tiene RSS propio, se lee a través de Google Noticias.
FUENTES_NOTICIAS = [
    {"nombre": "Punto de Break", "rss": "https://www.puntodebreak.com/feed", "sitio": "puntodebreak.com", "idioma": "es"},
    {"nombre": "Tennis.com", "rss": "https://www.tennis.com/roots/rss-feeds/news", "sitio": "tennis.com", "idioma": "en"},
    {"nombre": "ATP Tour", "rss": "https://www.atptour.com/en/media/rss-feed/xml-feed", "sitio": "atptour.com", "idioma": "en"},
    {"nombre": "WTA", "rss": "", "sitio": "wtatennis.com", "idioma": "en"},
]
DIAS_NOTICIAS = 7
MAX_JUGADORES_NOTICIAS = 40     # Google Noticias con el nombre de cada jugador del día (como mucho 40)


def secreto(nombre: str) -> str:
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        raise RuntimeError(f"Falta la variable {nombre}. Añádela en GitHub → Settings → Secrets and variables → Actions.")
    return valor
