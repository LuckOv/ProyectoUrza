# URZA — Asistente Inteligente de Tienda de Magic: The Gathering

**URZA es un asistente virtual multiagente diseñado para tiendas de cartas de Magic: The Gathering.** 
Permite a los jugadores consultar stock físico, comparar precios de mercado, estudiar reglas oficiales con un juez, explorar el lore del multiverso, armar mazos competitivos, reconocer cartas y mesas de juego por fotos, y realizar compras o vender cartas a la tienda tanto desde la **Web** como desde **Telegram** (con soporte de **mensajes de texto y notas de voz**).

Detrás de Urza opera un equipo de planeswalkers especializados:
- 🧙‍♂️ **Urza**: Orquestador central (LangGraph + ChatGroq Qwen3.8-27b).
- 😈 **Tibalt**: Vendedor (stock local en SQLite, precios en ARS con dólar dinámico, carrito y compras).
- 🦁 **Ajani**: Juez oficial de reglas (RAG sobre Comprehensive Rules con ChromaDB y reranker cross-encoder).
- ⏳ **Teferi**: Erudito e historiador (RAG sobre el lore de MTG Wiki).
- ⚙️ **Saheeli**: Constructora de mazos (RAG sobre teoría de curvas de maná, arquetipos y stock real).
- 👁️ **Karn**: Visión computacional (Gemini 2.5 Flash para cartas físicas y arbitraje de campos de batalla).

---

## 🚀 Capacidades y Funcionalidades

### Para los Jugadores (Web & Telegram)
- **Consultar Stock y Precios**: Respuestas exactas con variantes por edición, estado de conservación o graduación (PSA 1–10) y conversión automática a pesos según el dólar configurado.
- **Precio de Referencia del Mercado**: Cotización de mercado europeo vía CardMarket / Scryfall en euros para cartas fuera de inventario.
- **Ficha 3D Interactiva y Abanico**: Visualización de cartas en 3D en la tienda web con selector de variantes y abanico dinámico de sugerencias de mazo.
- **Juez de Reglas con Cita Oficial**: Resolución precisa de dudas sobre interacción, prioridad y fases citando números de regla oficiales de Magic.
- **Visión Multimodal (Karn)**: Subí o sacá una foto a una carta física para cotizarla y saber si hay stock, o enviá una foto de tu campo de batalla con permanentes girados para arbitrar una jugada.
- **Notas de Voz y Audios en Telegram**: Mandale audios o notas de voz a Urza; el sistema transcribe en milisegundos con Groq Whisper Large v3 (o Gemini Flash) y aplica un corrector fonético entrenado en la jerga de MTG.
- **Compra sin registro**: Armado de carrito charlando con el bot y reserva de stock inmediata indicando día y hora de retiro en el local.
- **Ofrecer Cartas a la Tienda**: Propuestas de venta desde el chat con buscador exhaustivo de Scryfall y carga automática de datos.

### Para el Vendedor / Dueño de la Tienda
- **Mesa Central (`/vendedor.html`)**: Panel de gestión protegido por clave con grilla de inventario, edición rápida, alertas de precio, control de pedidos en calendario y métricas de ventas.
- **Django Admin (`/admin/`)**: Administración nativa del backend Django (usuario `admin`, clave `urza123`).
- **Modo Dueño en Telegram**: El dueño de la tienda recibe notificaciones automáticas inmediatas ante cada compra o propuesta de venta, y puede solicitar desde su Telegram personal reportes ejecutivos con `/ventas`, `/pedidos` y `/alertas`.
- **Interacción Fluida en Grupos**: El bot puede participar en grupos de Telegram respetando ventanas de conversación de 3 minutos para responder de corrido sin necesidad de etiquetarlo en cada mensaje.

---

## 🛠️ Requisitos Técnicos

- **Python 3.13** con gestor de paquetes **`uv`** (o pip/venv).
- **Node.js 18+** y npm (para el frontend en React 19 + Vite).
- Claves de API en `backend/.env`:
  - `GROQ_API_KEY`: Para el razonamiento de Urza, Ajani, Teferi, Saheeli y transcripción Whisper.
  - `GEMINI_API_KEY`: Para visión por computadora con Karn y respaldo de transcripción.
  - `TELEGRAM_BOT_TOKEN` y `TELEGRAM_OWNER_ID`: Para el bot de Telegram y modo dueño.
  - `VENDEDOR_CLAVE`: Clave de acceso a Mesa Central (por defecto: `urza`).

---

## ⚡ Guía Rápida de Inicio

### 1. Instalación inicial
```powershell
# Dependencias de Python
uv sync

# Dependencias de Frontend
cd frontend
npm install
cd ..
```

### 2. Configuración de credenciales
Creá el archivo `backend/.env` (podés guiarte con `backend/.env.example`):
```ini
GROQ_API_KEY=tu_clave_de_groq
GEMINI_API_KEY=tu_clave_de_gemini
VENDEDOR_CLAVE=urza
TELEGRAM_BOT_TOKEN=tu_token_de_botfather
TELEGRAM_OWNER_ID=tu_id_de_telegram
```

### 3. Ingesta de Bases de Conocimiento (RAG)
Si es la primera vez que se ejecuta en tu equipo:
```powershell
cd backend
uv run python -m ingesta.ingestar_reglas   # Descarga e indexa Comprehensive Rules
uv run python -m ingesta.ingestar_mazos    # Indexa teoría de armado de mazos
```
*(Nota: también se pueden instalar o monitorear desde Mesa Central en la pestaña Configuración → Bases del bot).*

---

## 💻 Comandos de Ejecución

Consultá el archivo completo **[`COMANDOS.md`](COMANDOS.md)** para más detalles.

### Terminal 1: Backend (Django)
```powershell
cd backend
..\.venv\Scripts\python.exe manage.py runserver 8000
```
- API REST & Salud: `http://localhost:8000/salud`
- Documentación OpenAPI Swagger: `http://localhost:8000/docs`
- Django Admin: `http://localhost:8000/admin/`

> **Nota:** Al arrancar el backend, si `TELEGRAM_BOT_TOKEN` está configurado, el bot de Telegram **se inicia automáticamente en segundo plano** y envía un saludo de `🟢 URZA ONLINE`.

### Terminal 2: Frontend (React + Vite)
```powershell
cd frontend
npm run dev
```
- Tienda para Jugadores: `http://localhost:5173/`
- Mesa Central (Vendedor): `http://localhost:5173/vendedor.html`

### Terminal 3 (Opcional): Bot de Telegram Dedicado
Si querés ver los logs de Telegram de forma aislada en su propia consola:
```powershell
cd backend
..\.venv\Scripts\python.exe manage.py run_telegram_bot
```

---

## 🧪 Pruebas Automatizadas

El proyecto cuenta con una suite integral de integración con **120 pruebas automatizadas** que validan la API, el orquestador LangGraph, Scryfall simulado, compras concurrentes con reserva de stock y el bot de Telegram:

```powershell
cd backend
uv run --with pytest python -m pytest tests -q
```
Resultado: `120 passed in ~27s`.
```
Esto descarga las reglas oficiales y las indexa. Puede tardar un rato la primera vez.

## Pruebas automáticas

Hay más de 100 pruebas que revisan el backend y el chat sin usar internet ni la API key (no tocan tu base de datos: si existe, prueban con una copia):

```powershell
cd backend
uv run --with pytest python -m pytest tests -q
```

Si todo está bien, al final dice algo como `105 passed` y ningún `failed`.

## Problemas comunes

- **La app no levanta y muestra un error de API key**: revisá que `backend\.env` exista y tenga tu `GROQ_API_KEY` (ojea que no haya espacios).
- **"429" al preguntar**: el plan gratis de Groq tiene límites por minuto; esperá unos segundos y volvé a preguntar.
- **No responde dudas de reglas**: falta correr `ingestar_reglas.py` (sección de arriba).
- **La primera consulta tarda**: los modelos de lenguaje se descargan la primera vez; las siguientes van rápido.