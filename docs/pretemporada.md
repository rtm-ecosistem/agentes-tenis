# Pretemporada simulada

Antes de empezar en serio, los analistas repasan día a día los partidos ya jugados de 2026 (del 1 de enero al
25 de octubre). Así llegan a la oficina con reglas, lecciones y una biblioteca hechas.

## Qué se simula

- **Cartelera:** los partidos reales de cada día (como mucho 16, los de mejor ranking), sacados de
  tennis-data.co.uk. Llevan la cuota de Bet365 (o la media del mercado, si falta) y, como referencia, la de cierre de
  Pinnacle o, si falta (tennis-data no la da desde febrero de 2026), la de Betfair Exchange. Solo hay
  ganador del partido: ni hándicap ni totales.
- **El día:** la sala escribe su informe, los analistas deciden (con la apuesta de práctica) y por la noche se
  liquida con el resultado real. Después cada uno escribe su lección, y los domingos llegan la reflexión con
  sus reglas y la biblioteca.
- **Sin trampas:** el Elo y el cansancio de cada día solo usan partidos anteriores. De esos días no hay
  noticias, y no hay despidos.
- **Coste:** no gasta créditos de cuotas. Usa la IA ligera (`MODELO_PRETEMPORADA`, por defecto la de
  `MODELO_GEMINI_LIGERO`), unas 10 llamadas por día simulado. Si la IA se queda sin cuota, ese día se repite
  en la siguiente ejecución. Para no dejar sin cuota a la oficina, va despacio (una llamada cada 8 s) y como
  mucho hace 380 llamadas al día (`LLAMADAS_PRETEMPORADA_DIA`; la ligera gratuita da 500).

## Los ficheros de tennis-data

tennis-data.co.uk no deja descargar desde los servidores de GitHub (responde 403). Por eso los ficheros del año
se suben a mano a `datos/tennis-data/`: `2026.xlsx` (ATP) y `2026w.xlsx` (WTA). El Elo de años anteriores sale
de las otras fuentes públicas.

## Cómo se lanza

En GitHub, Actions → «Pretemporada simulada» → Run workflow:

- con **activar** sin marcar, solo avanza los días que pongas (para probar);
- con **activar** marcado, sigue sola cada 3 horas hasta terminar.

La simulación se guarda en la rama `pretemporada`, que Vercel no publica. Al terminar, una sola vez, pasa a
la oficina las reglas, lecciones, reflexiones y la biblioteca, y en Aprendizaje aparece la tarjeta
«Pretemporada simulada». El dinero de la oficina no se toca.
