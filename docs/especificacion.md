# Oficina de analistas de tenis: especificación v1

28 de octubre de 2026

## Objetivo

Es un experimento para aprender, igual que la oficina de bolsa. Cuatro agentes de IA apuestan al tenis con cuotas reales y dinero ficticio. Solo se pasa a dinero real si alguno cumple la regla de la sección «Evaluación». Si ninguno lo consigue, el experimento habrá servido igual.

El repositorio es nuevo, `agentes-tenis`, y público. La bolsa (`agentes-inversion`) no se toca.

## Qué tenis y qué apuestas

Solo el circuito principal: los Grand Slams, los Masters y los torneos ATP 250/500 y WTA 250/500/1000. Los Challenger y los ITF quedan fuera por ahora. Solo se apuesta antes de que empiece el partido: nada en directo y nada de combinadas.

Cada analista lleva dos botes separados, para ver en qué se le da mejor:

| Bote | Mercados | Cuándo arranca |
| --- | --- | --- |
| 1 | Ganador del partido, hándicap de juegos y total de juegos | Desde el principio |
| 2 | Los del bote 1, más ganador del primer set y resultado exacto en sets | Cuando haya una fuente gratis y fiable de esas cuotas |

Para el bote 2 se buscará una clave gratis con cuotas en diferido (la API de Betfair) u otra API gratuita. Si no hay ninguna, se arranca solo con el bote 1.

## Cuotas

Las cuotas vienen de [The Odds API](https://the-odds-api.com/sports/tennis-odds.html) en su plan gratis, de unos 500 créditos al mes. Para el tenis cubre bien el ganador del partido, y el hándicap y el total de juegos solo con algunas casas.

- **Casa con la que se apuesta:** una casa con licencia en España de las que da la API ([lista](https://the-odds-api.com/sports-odds-data/bookmaker-apis.html)): 888sport, William Hill o Betsson. La elegirá Claude según cuál cubra más partidos de tenis; si están igualadas, William Hill. La API lee la web internacional de la casa, así que la cuota de la web .es puede variar un poco.
- **Árbitro:** la cuota de Pinnacle llega en la misma consulta, sin gastar créditos extra. Poco antes de cada jornada se hace una segunda consulta para guardar la cuota de cierre de Pinnacle. Si el analista apostó a una cuota mejor que esa, el mercado le da la razón, aunque luego pierda la apuesta.
- **Límite gratis:** si los créditos no llegan, Claude avisa antes de proponer pagar nada.

## Dinero y riesgo

Estas reglas son fijas: ningún analista puede saltárselas.

- Cada bote empieza con 1.000 € ficticios.
- Cada apuesta va del 1 % al 3 % del bote, según lo seguro que esté el analista. Nunca más del 3 %.
- Como mucho, el 10 % del bote puede estar en apuestas pendientes a la vez.
- Nada de combinadas ni de apuestas en directo.

## Plantilla y sala de analistas

Hay tres especialistas y un Manager que junta el trabajo de los tres. Si el Manager gana más que cada uno por separado, sabremos que juntar opiniones funciona.

| Agente | Cómo decide | Qué lee |
| --- | --- | --- |
| El Estadístico | Calcula la probabilidad con un Elo por superficie y apuesta cuando la cuota paga más de lo calculado | Datos e informes de la sala |
| El Reportero | Busca lesiones, cansancio, viajes y falta de motivación | Noticias e informes de la sala |
| El Especialista en superficies | Se fija en los cambios de pista y en los jugadores que rinden distinto según la superficie | Datos por superficie e informes de la sala |
| El Manager | Apuesta solo cuando lo ve claro después de leer a los otros tres | Los informes de los tres especialistas y de la sala |

Se mantiene la «vida» de la bolsa: cada analista ve su situación laboral y la clasificación, tiene memoria de sus últimas decisiones, escribe una reflexión cada semana y, si le despiden, deja una carta a su sustituto.

**Sala de analistas:** un equipo común, con la misma estructura que el de la bolsa pero especializado en tenis. Lo forman un analista de datos (Elo, forma, cara a cara), uno de noticias (lesiones, retiradas, viajes), uno de ambiente (redes y prensa) y un debate a favor y en contra del favorito. Escribe varios informes al día y los agentes los leen antes de decidir.

## Evaluación, despidos y paso a dinero real

A cada analista se le mide por dos cosas: la rentabilidad y la cuota de cierre de Pinnacle, es decir, si apostó a una cuota mejor que la que había justo antes del partido.

- **Despido:** cada 100 apuestas se revisa a cada analista. Se le despide si pierde más de un 10 % y además, en la mayoría de sus apuestas, consiguió peor cuota que la de cierre.
- **Paso a dinero real:** un analista solo «se gana» que le copies cuando cumple tres cosas a la vez: al menos 500 apuestas, gana dinero en total y en la mayoría de sus apuestas consiguió mejor cuota que la de cierre. Una buena racha no basta.
- **Avisos para copiar** (por ejemplo, por Telegram): se construyen cuando un analista cumpla esa regla, no antes.

## Horario, noticias e infraestructura

- **Decisión diaria:** a las 9:00, hora española, sobre los partidos de las 24 horas siguientes. Poco antes de cada jornada se guarda la cuota de cierre de Pinnacle.
- **Noticias:** cuantos más medios fiables, mejor. Se empieza con Punto de Break, Tennis.com, la web oficial de la ATP y la de la WTA, y Google Noticias con el nombre de cada jugador del día.
- **IA:** Gemini en su capa gratuita, con una clave propia en un proyecto nuevo de Google AI Studio, para no gastar la cuota de la bolsa.
- **Dónde funciona:** con tareas automáticas de GitHub y los datos guardados en el propio repositorio. Como el repositorio es público, los minutos de GitHub son ilimitados y no se gastan los de la bolsa.
- **Repositorio público sin datos personales:** las claves van como secretos, los commits salen con el email privado de GitHub (`noreply`) y no se guarda ningún dato tuyo.
- **Despertadores:** se usa tu cuenta de cron-job.org y se amplía la llave `despertador` para que también lance las tareas de `agentes-tenis`. Habrá una guía paso a paso, como la de la bolsa.

## Web y calendario

La web es nueva, en Vercel, aparte de la de la bolsa. Mantiene la oficina estilo Habbo según la captura que mandarás. Cambian las pantallas:

- cartelera de partidos en lugar de cotizaciones;
- boletos de apuesta en lugar de cartera;
- clasificación por rentabilidad y por cuota de cierre.

El nombre provisional es «La oficina del tenis».

Calendario:

1. **Ahora:** construcción.
2. **Lo que queda de temporada** (París, Finales de la WTA y de la ATP, Copa Davis): prueba con fallos permitidos.
3. **Pausa del circuito** hasta finales de diciembre: ajustes.
4. **Gira australiana, a finales de diciembre:** el experimento de verdad arranca de cero. Lo que haya pasado en la prueba no cuenta en el historial.

## Lo que necesito de ti

Todo esto se pide al empezar a construir, con una guía para cada paso:

- [ ] Captura del estilo de oficina que quieres
- [ ] Clave gratis de The Odds API (necesita tu email)
- [ ] Clave gratis de Gemini en un proyecto nuevo de Google AI Studio
- [ ] Ampliar la llave `despertador` y crear los despertadores en cron-job.org
- [ ] Crear el proyecto en Vercel para la web nueva

## Fuentes

- [The Odds API: cuotas de tenis](https://the-odds-api.com/sports/tennis-odds.html)
- [The Odds API: lista de casas de apuestas](https://the-odds-api.com/sports-odds-data/bookmaker-apis.html)
