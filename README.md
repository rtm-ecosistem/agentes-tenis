# La oficina del tenis

Cuatro analistas de IA apuestan al tenis con **cuotas reales y dinero ficticio**. Es un experimento para aprender,
como la oficina de bolsa: solo se pasaría a dinero real si alguno cumple la regla de la sección «Evaluación» de la
[especificación](docs/especificacion.md). Si ninguno lo consigue, el experimento habrá servido igual.

- **Web:** la carpeta `web/`, publicada gratis en Vercel. Tiene cinco pestañas: la **oficina** (estilo videojuego de
  píxeles, con los analistas trabajando, la sala de analistas y el rincón del sofá), la **cartelera** de partidos con
  sus cuotas, los **boletos** de apuesta, la **clasificación** (por rentabilidad y por cuota de cierre) y los informes
  de la **sala**. Al pulsar en un analista se abre su ficha.
- **Todas las apuestas:** [datos/apuestas.json](datos/apuestas.json).

## La plantilla

| Analista | Cómo decide | Qué lee |
| --- | --- | --- |
| Óscar, el Estadístico | Calcula la probabilidad con un Elo por superficie y apuesta cuando la cuota paga más de lo calculado | Datos e informes de la sala |
| Lola, la Reportera | Busca lesiones, cansancio, viajes y falta de motivación | Noticias e informes de la sala |
| Bruno, el Especialista en superficies | Se fija en los cambios de pista y en quien rinde distinto según la superficie | Datos por superficie e informes de la sala |
| Inés, la Manager | Apuesta solo cuando lo ve claro después de leer a los otros tres | Los informes de los tres y de la sala |

La **sala de analistas** es un equipo común: datos (Elo, forma, cara a cara), noticias (lesiones, retiradas,
viajes), ambiente (prensa y redes) y un debate a favor y en contra del favorito. Escribe a las 9:00, 14:00 y 20:00.

Cada analista tiene **vida**, como en la bolsa: ve su situación en el puesto y la clasificación, recuerda sus
últimas decisiones y apuestas, escribe una reflexión cada domingo y, si le despiden, deja una carta a su sustituto.

## Cómo funciona cada día (hora de España)

1. **9:00 · Decisión.** Se leen las cuotas de los partidos de las 24 horas siguientes (solo circuito principal: Grand
   Slams, Masters, ATP 250/500 y WTA 250/500/1000) en The Odds API, con la casa española elegida y Pinnacle como
   árbitro. Se recogen las noticias, la sala escribe su informe, deciden los tres especialistas y, después de
   leerlos, la Manager.
2. **Control de riesgo**, diga lo que diga la IA: cada apuesta es del 1 al 3 % del bote, como mucho el 10 % del bote
   en juego a la vez, una apuesta por mercado y partido, nada de directo ni de combinadas.
3. **Cada hora · Cierre.** Poco antes de cada partido con apuestas se guarda la cuota de cierre de Pinnacle. Al
   acabar, se liquidan las apuestas con el resultado (con los juegos de cada set, para el hándicap y el total).
   Si un jugador se retira, la apuesta se anula y se devuelve el dinero.
4. **14:00 y 20:00 · Sala.** Noticias nuevas e informe de la sala. Los domingos a las 20:00, reflexiones.
5. **Cada 100 apuestas, revisión.** Despido si pierde más de un 10 % y además consiguió peor cuota que la de cierre en
   la mayoría de sus apuestas. El sustituto mantiene el método, pero es otra persona y lee la carta.
6. **Dinero real**, solo si alguien cumple a la vez: al menos 500 apuestas, gana dinero en total y bate la cuota de
   cierre en la mayoría. Entonces llega un aviso (una *issue* de GitHub, que te llega por email).

Los **botes**: el bote 1 (ganador, hándicap de juegos y total de juegos) funciona desde el principio. El bote 2
(además, primer set y resultado exacto en sets) arrancará cuando haya una fuente gratis y fiable de esas cuotas:
basta con crear la variable `BOTE2_ACTIVO` con el valor `1`.

## Puesta en marcha (una sola vez)

La guía paso a paso de las claves está en [docs/claves.md](docs/claves.md) y la de los despertadores en
[docs/despertador.md](docs/despertador.md). Los secretos van en **Settings → Secrets and variables → Actions**:

| Secreto | Qué es |
| --- | --- |
| `ODDS_API_KEY` | Clave gratis de The Odds API |
| `GEMINI_API_KEY` | Clave gratis de Gemini, de un proyecto nuevo de Google AI Studio (no la de la bolsa) |

El repositorio es público: las claves solo van como secretos, los cambios automáticos se firman con el email
privado de GitHub (`noreply`) y no se guarda ningún dato personal.

## Temporadas

Ahora mismo es la **temporada de prueba** (lo que queda de 2026: París, las Finales y la Copa Davis), con fallos
permitidos. Para empezar de cero en la gira australiana: **Actions → Empezar una temporada nueva → Run workflow**,
con un nombre como `australia-2027`. Lo anterior se guarda en `datos/archivo/` y no cuenta en el historial.

## De dónde salen los datos

- Cuotas: [The Odds API](https://the-odds-api.com/sports/tennis-odds.html), plan gratis (unos 500 créditos al mes).
  Si no llegan, la oficina ahorra (solo el ganador del partido) y avisa antes de proponer pagar nada.
- Resultados: el marcador público de ESPN; si falta un partido, el de The Odds API.
- Elo: resultados públicos de [tennis-data.co.uk](http://www.tennis-data.co.uk/) más los que va recogiendo la oficina.
- Noticias: Punto de Break, Tennis.com, la ATP, la WTA y Google Noticias con el nombre de cada jugador del día.
- IA: Gemini, en su capa gratuita.
