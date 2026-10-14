# URZA

**URZA es el asistente de chat de una tienda de cartas de Magic: The Gathering.** Le preguntás por una carta, un precio, o cómo se resuelve una jugada, y te responde pensando por vos. Es como hablar con un vendedor que además es juez de reglas.

---

## Qué puede hacer hoy

- **Saber si hay una carta en stock**: "¿Tenés Cavern of Souls?" → te dice cuántas hay y en qué edición.
- **Pasarle el precio**: "Precio de Llanowar Elves" → te dice el precio de la tienda en pesos (y, si querés, la referencia del mercado europeo).
- **Mostrarte la carta**: cuando hablás de una, aparece la carta para que la reconozcas de un vistazo.
- **Comprar desde el chat**: le decís qué cartas querés, Urza las va sumando al carrito y te pregunta si querés algo más o cerrar la compra. Al cerrar te pide nombre, apellido y qué día y a qué hora pasás a retirar (dentro del horario del local). No hace falta crear cuenta.
- **Resolver dudas del juego**: "¿Puedo responder con un instante antes de que mi criatura muera?" → te contesta con base en las reglas oficiales y te cita la regla.

- **Contarte el lore** de planos y personajes, y **armarte un mazo** con lo que hay en la tienda (las cartas aparecen en abanico).
- **Ver todas las cartas** de la tienda con filtros por color, PSA, precio y expansión.
- **Ofrecerle una carta a la tienda**: "tengo una X en PSA 9 a tanto" → se abre un formulario para elegir la carta exacta y dejar nombre, apellido y mail.

Detrás hay un equipo: **Urza** orquesta y consulta a **Tibalt** (vendedor), **Ajani** (juez de reglas), **Teferi** (lore) y **Saheeli** (armado de mazos).

URZA habla en español (de Argentina, como un vendedor de barrio).

## Panel del vendedor (Mesa Central)

En `http://localhost:5173/vendedor.html`, con la clave de vendedor:

- **Inventario**: todas las cartas con foto, grado (PSA), precio y stock. Para agregar una, la buscás en Scryfall, elegís la impresión y cargás cuántas tenés.
- **Pedidos**: calendario con los retiros de cada día; marcás un pedido como entregado o rechazado (si se rechaza, las cartas vuelven al stock).
- **Propuestas**: las cartas que los clientes le ofrecen a la tienda desde el chat (con nombre, apellido y mail), para aceptarlas, cargarlas al stock o rechazarlas.
- **Dashboard**: cuánto stock hay, cuánto vale, pedidos abiertos, ventas del mes, color / cartas / expansiones más vendidas y alertas de cambios bruscos de precio y stock.
- **Historial**: el protocolo de todos los pedidos, con tus comentarios, exportable a CSV.
- **Configuración**: horarios del local, precio del dólar (automático o manual) y descuentos.

## Lo que viene (en camino)

- **Alta de stock por chat para el vendedor** (desde el panel ya se puede).
- **Reconocimiento de fotos (a futuro)**: sacar o enviar una foto de una carta. Los jugadores podrán preguntar si hay stock; el vendedor podrá cargarla al stock directamente desde la foto.

---

## Requisitos

- **Python 3.13** y **Node.js** (para el frontend).
- Una **clave de Groq** (gratis): creala en https://console.groq.com.
- (Opcional) Una clave de HuggingFace (`HF_TOKEN`) para que las descargas de modelos sean más rápidas.

## Instalación

1. Instalá las dependencias de Python con `uv`:
   ```powershell
   uv sync
   ```

2. Instalá las dependencias del frontend:
   ```powershell
   cd frontend
   npm install
   cd ..
   ```

3. Cargá tus claves. Creá el archivo `backend\.env` y poné adentro:
   ```
   GROQ_API_KEY=tu_clave_acá
   VENDEDOR_CLAVE=la_clave_del_panel
   ```

## Cómo levantarlo

**Backend** (parado dentro de la carpeta `backend/`):
```powershell
..\.venv\Scripts\python.exe -m uvicorn api:app --reload --port 8000
```
Si todo anda, `http://localhost:8000/salud` responde `{"ok": true}`.

**Frontend** (parado dentro de la carpeta `frontend/`):
```powershell
npm run dev
```
Después abrí `http://localhost:5173` en el navegador y chateá. El panel del vendedor está en `http://localhost:5173/vendedor.html`.

### Usarlo desde el celular u otra compu del mismo wifi

Todo corre en la compu que levanta el backend: los demás sólo necesitan el navegador, no instalan nada.

1. Levantá backend y frontend como siempre.
2. `npm run dev` muestra dos direcciones: `Local` y `Network` (por ejemplo `http://192.168.0.15:5173`). Desde el otro dispositivo abrí la de **Network**.
3. La primera vez Windows pregunta si deja pasar a Node por el firewall: aceptá para **redes privadas**.

### Compartirlo por internet (link gratis de Cloudflare)

Para que alguien lo use desde otra casa. Es gratis y no necesita cuenta. El link cambia cada vez y funciona mientras tu compu esté prendida con todo corriendo.

1. **Una sola vez**, instalá `cloudflared` (PowerShell):
   ```powershell
   winget install --id Cloudflare.cloudflared
   ```
   (cerrá y abrí PowerShell después de instalarlo).
2. **Poné una clave propia del panel** en `backend/.env` (`VENDEDOR_CLAVE=algo-dificil`) y reiniciá el backend. Por el link público el panel no deja entrar con la clave de fábrica `urza`, y frena a quien pruebe muchas claves.
3. Levantá el backend como siempre. Para el frontend, en vez de `npm run dev` usá la versión compilada, que carga más rápido:
   ```powershell
   cd frontend
   npm run build
   npm run preview
   ```
4. En **otra** ventana de PowerShell:
   ```powershell
   cloudflared tunnel --url http://localhost:4173
   ```
   Después de unos segundos aparece un link `https://...trycloudflare.com`. Ese es el que compartís: la tienda es el link y el panel es el link + `/vendedor.html`.

Para cortarlo: `Ctrl+C` en esa ventana. (Con `npm run dev` también anda: en ese caso el túnel va a `http://localhost:5173`.)

### Bases del bot (reglas y lore)

Ajani (reglas) y Teferi (lore) responden buscando en dos bases que se arman en la compu que corre el backend y **no se suben a git**. Se instalan desde el panel: **Configuración → Bases del bot → Instalar todo** (muestra el avance; las reglas tardan minutos, el lore puede tardar horas y si se corta retoma). También se pueden copiar las carpetas `backend/reglas_db`, `backend/lore_db` y `backend/lore` de un compañero que ya las tenga.

### Base de reglas (una sola vez)

Si el agente no responde dudas de reglas, hay que cargar primero las reglas completas:
```powershell
cd backend
uv run python -m ingesta.ingestar_reglas
```
Esto descarga las reglas oficiales y las indexa. Puede tardar un rato la primera vez.

## Pruebas automáticas

Hay más de 100 pruebas que revisan el backend y el chat sin usar internet ni la API key (no tocan tu base de datos: si existe, prueban con una copia):

```powershell
cd backend
uv run --with pytest python -m pytest tests -q
```

Si todo está bien, al final dice algo como `107 passed` y ningún `failed`.

## Problemas comunes

- **La app no levanta y muestra un error de API key**: revisá que `backend\.env` exista y tenga tu `GROQ_API_KEY` (ojea que no haya espacios).
- **"429" al preguntar**: el plan gratis de Groq tiene límites por minuto; esperá unos segundos y volvé a preguntar.
- **No responde dudas de reglas**: falta correr `ingestar_reglas.py` (sección de arriba).
- **La primera consulta tarda**: los modelos de lenguaje se descargan la primera vez; las siguientes van rápido.