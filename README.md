# URZA

**URZA es el asistente de chat de una tienda de cartas de Magic: The Gathering.** Le preguntás por una carta, un precio, o cómo se resuelve una jugada, y te responde pensando por vos. Es como hablar con un vendedor que además es juez de reglas.

---

## Qué puede hacer hoy

- **Saber si hay una carta en stock**: "¿Tenés Cavern of Souls?" → te dice cuántas hay y en qué edición.
- **Pasarle el precio**: "Precio de Llanowar Elves" → te dice el precio de la tienda en pesos (y, si querés, la referencia del mercado europeo).
- **Mostrarte la carta**: cuando hablás de una, aparece la carta para que la reconozcas de un vistazo.
- **Comprar desde el chat**: le decís qué cartas querés, Urza las va sumando al carrito y te pregunta si querés algo más o cerrar la compra. Al cerrar te pide nombre, apellido y qué día y a qué hora pasás a retirar (dentro del horario del local). No hace falta crear cuenta.
- **Resolver dudas del juego**: "¿Puedo responder con un instante antes de que mi criatura muera?" → te contesta con base en las reglas oficiales y te cita la regla.

URZA habla en español (de Argentina, como un vendedor de barrio).

## Panel del vendedor (Mesa Central)

En `http://localhost:5173/vendedor.html`, con la clave de vendedor:

- **Inventario**: todas las cartas con foto, grado (PSA), precio y stock. Para agregar una, la buscás en Scryfall, elegís la impresión y cargás cuántas tenés.
- **Pedidos**: calendario con los retiros de cada día; marcás un pedido como entregado o rechazado (si se rechaza, las cartas vuelven al stock).
- **Dashboard**: cuánto stock hay, cuánto vale, pedidos abiertos, actividad reciente.
- **Historial**: el protocolo de todos los pedidos, con tus comentarios, exportable a CSV.
- **Configuración**: horarios del local, precio del dólar (automático o manual) y descuentos.

## Lo que viene (en camino)

- **Un agente de historia**: preguntar por el lore de MTG (planos, personajes, trasfondo de las cartas).
- **Alta de stock por chat para el vendedor** (desde el panel ya se puede).
- **Armador de mazos**: recomendaciones para construir un mazo, usando cartas que la tienda ya tiene en stock.
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

### Base de reglas (una sola vez)

Si el agente no responde dudas de reglas, hay que cargar primero las reglas completas:
```powershell
cd backend
uv run python ingestar_reglas.py
```
Esto descarga las reglas oficiales y las indexa. Puede tardar un rato la primera vez.

## Problemas comunes

- **La app no levanta y muestra un error de API key**: revisá que `backend\.env` exista y tenga tu `GROQ_API_KEY` (ojea que no haya espacios).
- **"429" al preguntar**: el plan gratis de Groq tiene límites por minuto; esperá unos segundos y volvé a preguntar.
- **No responde dudas de reglas**: falta correr `ingestar_reglas.py` (sección de arriba).
- **La primera consulta tarda**: los modelos de lenguaje se descargan la primera vez; las siguientes van rápido.