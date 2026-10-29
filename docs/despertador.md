# Despertadores (cron-job.org)

El reloj de GitHub llega tarde o se salta ejecuciones; cuando alguien le pide «ejecuta ya», arranca en segundos.
Eso hace cron-job.org a la hora exacta. Se usa la misma cuenta y la misma llave `despertador` de la bolsa: solo hay
que **ampliar la llave** a este repositorio y crear tres despertadores nuevos. GitHub conserva unas ejecuciones de
reserva, así que si un despertador fallara todo seguiría funcionando, aunque más tarde.

## 1. Ampliar la llave `despertador`

1. Entra en https://github.com/settings/personal-access-tokens
2. Pulsa en la llave `despertador` y luego en **Edit**.
3. En **Repository access**, con *Only select repositories*, añade `agentes-tenis` (deja también `agentes-inversion`).
4. Comprueba que en **Permissions → Repository permissions → Actions** pone *Read and write*.
5. **Update**. La llave no cambia: los despertadores de la bolsa siguen funcionando igual.

## 2. Crear los tres despertadores

Lo más rápido es abrir uno de la bolsa, pulsar **Clonar** y cambiar el título, la URL y el horario (las copias
salen apagadas: activa *Habilitar job* en cada una). Si los creas desde cero, pulsa **Create cronjob** y rellena:

- **URL:** `https://api.github.com/repos/rtm-ecosistem/agentes-tenis/actions/workflows/ARCHIVO/dispatches`,
  cambiando `ARCHIVO` por el de la tabla.
- **Execution schedule:** *Custom*, zona horaria `Europe/Madrid`, todos los días, con las horas y minutos de la tabla.
- Pestaña **Advanced**:
  - **Request method:** `POST`
  - **Headers** (tres):
    - `Authorization` = `Bearer ` seguido de la llave (con un espacio después de Bearer)
    - `Accept` = `application/vnd.github+json`
    - `X-GitHub-Api-Version` = `2022-11-28`
  - **Request body:** `{"ref":"main"}`
- **Notifications:** marca que te avise si falla.

| Title | ARCHIVO | Horas | Minutos |
|---|---|---|---|
| Tenis decisión | `decision.yml` | 9 | 0 |
| Tenis sala | `sala.yml` | 14 y 20 | 0 |
| Tenis cierre | `cierre.yml` | todas (0 a 23) | 10 |

El de cierre va cada hora porque la cuota de cierre de Pinnacle se guarda en la hora antes de cada partido con
apuestas (los de Australia se juegan de madrugada en España). Si no hay apuestas pendientes, no gasta créditos.
También lee cada hora las noticias de los jugadores que aún no han jugado: si hay alguna nueva, la sala actualiza su
informe y dice si la noticia cambia algún partido. Solo entonces se piden cuotas nuevas del ganador y los analistas
pueden apostar a ese partido (como mucho 4 créditos al día). Un partido no se consulta dos veces, salvo que la sala
marque una noticia como grave (una lesión fuerte o dudas de que juegue): entonces, una vez más. Si se pidieron cuotas
hace menos de 2 horas y el partido empieza dentro de más de 2, se espera para juntar las noticias en una sola consulta.

## 3. Probar

Cada despertador tiene **Test run**. Si responde `204`, funciona: en GitHub, en **Actions** de `agentes-tenis`,
verás la tarea arrancar en unos segundos. Si responde `401`, `403` o `404`, a la llave le falta `agentes-tenis` o el
permiso de *Actions*.

## Qué gasta

Nada: el repositorio es público y los minutos de GitHub Actions son gratis e ilimitados, sin tocar los de la bolsa.
