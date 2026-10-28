# Las claves, paso a paso

Hacen falta dos claves gratis. Ninguna se pega en el chat: van como **secretos** del repositorio, que nadie puede
leer (ni siquiera tú, una vez guardados), aunque el repositorio sea público.

Para guardar un secreto: en GitHub, entra en `agentes-tenis` → **Settings** → **Secrets and variables** →
**Actions** → **New repository secret**, pon el nombre exacto y pega el valor, sin espacios.

## 1. The Odds API (cuotas)

1. Entra en https://the-odds-api.com y pulsa **Get API Key**.
2. Elige el plan **Starter** (gratis, 500 créditos al mes). No pide tarjeta.
3. Escribe tu email y confirma. La clave llega a tu correo (32 letras y números).
4. Guárdala como secreto con el nombre `ODDS_API_KEY`.

## 2. Gemini (la IA), en un proyecto nuevo

Un proyecto nuevo tiene su propia cuota gratuita, así que la bolsa no se queda sin IA.

1. Entra en https://aistudio.google.com/apikey con tu cuenta de Google.
2. Pulsa **Create API key** y, en el desplegable del proyecto, elige **Create a new project** (no el de la bolsa).
   Llámalo, por ejemplo, `oficina-tenis`.
3. Copia la clave (empieza por `AIza`).
4. Guárdala como secreto con el nombre `GEMINI_API_KEY`.

## 3. La web en Vercel

1. Entra en https://vercel.com con tu cuenta (la misma de la bolsa).
2. **Add New → Project**. Si `agentes-tenis` no aparece, pulsa **Adjust GitHub App Permissions** y añádelo a la
   lista de repositorios permitidos.
3. **Import** `agentes-tenis` → **Deploy**. No hace falta tocar nada: `vercel.json` ya dice que la web está en `web/`.
4. La web quedará en una dirección como `https://agentes-tenis.vercel.app` y se actualizará sola.

## 4. Comprobar que todo funciona

**Actions → Decisión diaria → Run workflow**, marcando *forzar*. En unos minutos verás la cartelera y las primeras
apuestas en la web. Si forzaste la decisión, ese día ya no se repite a las 9:00.
