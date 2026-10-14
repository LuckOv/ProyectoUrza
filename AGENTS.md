# URZA — Contexto de sesión y especificación viva (SDD)

Este archivo le da contexto a cualquier agente/LLM que abra una sesión en el repo. Parte A = traspaso (qué hay, cómo se levanta, cómo funciona). Parte B = especificación viva estilo **Spec-Driven Development**: cada feature con historia de usuario, comportamiento esperado, criterios de aceptación y estado. Cuando se cambie de rumbo o se cierre una feature, actualizar la Parte B en el mismo commit.

---

## Parte A — Contexto del proyecto

### Qué es

URZA es el asistente virtual de una tienda de cartas de **Magic: The Gathering**. El usuario chatea con un agente LangGraph que consulta:

- **Stock y precios de la tienda** (tabla `inventario` de SQLite, con variantes por set y grado; precios en US$ convertidos a pesos con el dólar configurado).
- **Precio de referencia del mercado** en euros (CardMarket, vía API de Scryfall).
- **Ficha/datos de cartas** (tipo, colores, texto de reglas, legalidad — Scryfall).
- **Reglas del juego** (RAG sobre las Comprehensive Rules oficiales → "subagente juez").
- **Lore / historia** (RAG sobre la MTG Wiki → "subagente erudito").

No hay cuentas de jugador: el carrito se ata a la conversación (`thread_id`) y la compra se cierra desde el propio chat, que pide nombre, apellido y día y hora de retiro. El vendedor administra todo desde **Mesa Central** (`frontend/vendedor.html`), protegido con una clave. El front son dos páginas React/Vite (tienda + panel). Todo se habla en **español rioplatense**.

### Stack

- Python **3.13** con gestor de paquetes **uv** (`pyproject.toml` + `uv.lock`, venv en `.venv/`).
- Backend: **FastAPI** + **LangChain** + **LangGraph** (`StateGraph` + checkpointer `MemorySaver`).
- LLM: **ChatGroq**, modelo `qwen/qwen3.8-27b`, `temperature=0`, `max_tokens=500` (tope del plan free de Groq; sin eso da 429).
- RAG de reglas: **Chroma** (`backend/reglas_db/`), embeddings `paraphrase-multilingual-MiniLM-L12-v2`, rerank `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, juez = mismo ChatGroq.
- RAG de lore: **Chroma** (`backend/lore_db/`, colección `lore_mtg`), mismos embeddings/rerank/ChatGroq reusados de `reglas.py`; corpus = intros de la **MTG Wiki** (`mtg.fandom.com`).
- Frontend: **React 19 + Vite 8**.
- Datos: SQLite `backend/urza.db` (inventario, carrito por charla, pedidos, movimientos, config, descuentos), API de **Scryfall** (fichas, imágenes, impresiones), **dolarapi.com** (cotización). `backend/inventario.csv` sólo se usa para la importación inicial.

### Cómo levantarlo

Credenciales en **`backend/.env`** (gitignoreado): `GROQ_API_KEY` (obligatoria), `VENDEDOR_CLAVE` (clave del panel; si falta, es `urza` y el panel lo avisa), `PRICECHARTING_TOKEN` (opcional, precios reales de graduadas) y `HF_TOKEN` (opcional, evita rate limits de HuggingFace). `load_dotenv()` (presente en `agentes/agent_sales.py` y `agentes/reglas.py`) busca el `.env` en el **directorio de trabajo**: arrancar siemPR desde `backend/`.

**Backend** (parado en `backend/`):
```powershell
..\.venv\Scripts\python.exe -m uvicorn api:app --reload --port 8000
```
- `GET /salud` → dice si el grafo se inicializó bien.
- `POST /chat` `{thread_id, texto}` → respuesta del agente + herramientas usadas + carta (si habló de una) + `carrito` actualizado + `pedido` (texto del comprobante si en ese turno se confirmó la compra).
- Carrito por charla: `GET/POST/DELETE /carrito/{thread_id}` (el POST recibe `{inventario_id, cantidad}`), `DELETE /carrito/{thread_id}/{item_id}`.
- `GET /carta?nombre=` → ficha para la carta 3D, con `variantes` (una por grado/set) y precio en pesos.
- `GET /catalogo` → todas las variantes a la venta (con stock y precio), para la lista con buscador del chat.
- `/chat` además devuelve `mazo` (cartas sugeridas para el abanico) y `catalogo` (true si hay que mostrar el botón "Ver todas las cartas").
- Panel del vendedor: todo bajo `/vendedor/*` con header `X-Vendedor-Clave` (ver `panel/vendedor.py` o `/docs`): inventario, Scryfall (autocompletar/impresiones), pedidos, `historial.csv`, dashboard, config y descuentos.

**Frontend** (parado en `frontend/`): `npm run dev` (dev) / `npm run build` (producción). Tienda en `http://localhost:5173/`, panel del vendedor en `http://localhost:5173/vendedor.html`.

**RAG de reglas**: si `backend/reglas_db/` no existe, ingestar desde `backend/`:
```powershell
uv run python -m ingesta.ingestar_reglas            # baja las Comprehensive Rules y las indexa
uv run python -m ingesta.ingestar_reglas --rebuild  # re-indexa desde cero
```

**RAG de lore**: si `backend/lore_db/` no existe, ingestar desde `backend/` (ETL en dos fases, **resumible** ante cortes de red):
```powershell
uv run python -m ingesta.ingestar_lore --solo-bajar   # red → snapshot en backend/lore/ (retoma si se corta)
uv run python -m ingesta.ingestar_lore --index        # offline → backend/lore_db/
uv run python -m ingesta.ingestar_lore                # ambas fases en corrida
uv run python -m ingesta.ingestar_lore --rebuild      # borra snapshot e índice y arranca de cero
```

### Bases del bot desde el panel

Configuración → **Bases del bot** (`frontend/src/vendedor/BasesBot.jsx`, `backend/panel/bot.py`): `GET /vendedor/bot` (estado: fragmentos de cada base contados directo del `chroma.sqlite3`, páginas del snapshot de lore, si está el modelo de rerank, librerías faltantes, y el trabajo en curso con las últimas líneas de salida), `POST /vendedor/bot/instalar {partes: ["reglas","modelos","lore"]}` y `POST /vendedor/bot/cancelar`. Corre las mismas ingestas como procesos aparte (`sys.executable -m ingesta...`, cwd `backend/`), de a una; reglas va con `--rebuild` si ya existía (si no, duplica) y lore con `--index` si la descarga ya está completa. Antes de rehacer una base suelta la que tenga abierta el servidor (`_vectorstore = None`); si Windows igual dice que el archivo está en uso, reiniciar el backend. Queda en el registro de actividad.

### Uso desde la red y por internet

El frontend le habla al backend en **la misma dirección de la página**, bajo `/api` (`src/*/api.js`, o `VITE_API` en `frontend/.env`), y Vite (`dev` y `preview`) hace de proxy de `/api` a `http://127.0.0.1:8000` (`vite.config.js`). Así el navegador usa una sola dirección: anda en localhost, por wifi (`server.host: true`, la dirección "Network") y por un **Cloudflare Quick Tunnel** (`cloudflared tunnel --url http://localhost:4173`, `allowedHosts: [".trycloudflare.com"]`). El backend no necesita `--host 0.0.0.0`. El CORS sigue aceptando localhost, redes privadas y `CORS_ORIGENES` por si se apunta el front directo al 8000.

Link público: el panel detecta el túnel por los encabezados `cf-connecting-ip`/`cf-ray` (`panel/vendedor.py`): con la clave de fábrica responde 403 (hay que definir `VENDEDOR_CLAVE`) y frena a 8 intentos fallidos de clave cada 10 minutos por IP (429). En la compu/wifi no hay freno (si no, cambiar la clave con el panel abierto te bloqueaba).

### Estado de datos hoy

- RAG de reglas y de lore: `backend/reglas_db/` y `backend/lore_db/` son locales (gitignoreados) y **cada compu del grupo tiene que generarlos** con la ingesta (ver arriba). La última ingesta de lore registrada: 5038 chunks en `lore_mtg`, snapshot `backend/lore/` con 5122 páginas (rondas `2026-09-24_r1` y `r2`). Si en una compu no están, Ajani y Teferi avisan qué comando correr en vez de romper.
- Stock, pedidos y configuración: `backend/urza.db` (gitignoreado; se crea solo). `backend/inventario.csv` se importa **una sola vez** en la vida de la base (marca `csv_importado` en `config`): si después se borra todo el inventario, reiniciar no lo vuelve a cargar.

### Arquitectura (backend/)

Organizado en carpetas (paquetes de Python). Se arranca siempre parado en `backend/`, así los imports (`from tienda import base`, `from agentes.graph import app_graph`) encuentran los paquetes y `load_dotenv()` encuentra el `.env`. Los datos (`urza.db`, `inventario.csv`, `reglas_db/`, `lore_db/`, `lore/`) siguen en `backend/`; los módulos los ubican con `Path(__file__).resolve().parent.parent`.

```
backend/
  api.py      → API HTTP (uvicorn api:app)
  agentes/    → grafo, prompt de Urza, herramientas, Ajani (reglas) y Teferi (lore)
  tienda/     → base de datos, Scryfall, inventario, carrito/pedidos, propuestas
  panel/      → endpoints del panel del vendedor
  ingesta/    → ETL de los RAG (python -m ingesta.ingestar_reglas / ingesta.ingestar_lore)
  scripts/    → test_local, check_models (python -m scripts.test_local)
```

| Archivo | Rol |
|---|---|
| `api.py` | API HTTP. Al arrancar: `base.preparar()` (crea/migra tablas), importa el CSV viejo si el inventario está vacío y completa imágenes/precios desde Scryfall en segundo plano. Carga el grafo en forma lazy. Incluye los routers de `vendedor.py`. |
| `tienda/base.py` | Conexión SQLite, esquema (versión en `PRAGMA user_version`), configuración dinámica (`horarios`, `dolar`, `stock_bajo`, `descuento_general`) y registro de `movimientos`. Hora fija de Argentina (UTC-3). |
| `tienda/inventario.py` | Inventario por variante (impresión + grado), SKU `URZ-0001`, precio en pesos = `precio_usd × dólar × (1 − descuento)`, dólar automático (dolarapi, refresco cada hora) o manual, descuentos general y por carta, alta desde Scryfall, importación del CSV viejo. |
| `panel/vendedor.py` | Endpoints `/vendedor/*` del panel, protegidos por `VENDEDOR_CLAVE`. Dashboard (rankings por color/carta/expansión, alertas de precio y stock), propuestas, export CSV del historial, config. |
| `tienda/propuestas.py` | Cartas que los clientes ofrecen a la tienda. Valida nombre/apellido/mail obligatorios (mail con formato), exige `scryfall_id` (edición exacta), estados `nueva`/`en_revision`/`aceptada`/`rechazada`, `al_inventario` (acepta y da de alta). Todo queda en `movimientos` (tipo `propuesta`). |
| `agentes/graph.py` | Grafo: nodo `Ventas` (`agent_ventas`) → `tools` (ToolNode) → vuelve a `Ventas`; `MemorySaver` con `thread_id` por pestaña. |
| `agentes/agent_sales.py` | Prompt de **Urza**, el orquestador, que reparte entre el equipo: **Tibalt** (vendedor: stock, precios, carrito, compra, catálogo, propuestas), **Ajani** (juez de reglas, `consultar_reglas_mtg`), **Teferi** (lore, `consultar_lore_mtg`) y **Saheeli** (armado de mazos, `sugerir_cartas_mazo`). `api.py` (`AGENTE_DE`) devuelve en `agentes` a quién consultó y el chat lo muestra ("Urza · consultó a Ajani, el juez"). Prompt (reglas de herramientas, reglas vs. lore, flujo de compra y estilo). Se arma en cada turno con la fecha de hoy y los horarios de la tienda (`system_prompt()`), así el agente convierte "el sábado a las 5" en fecha y hora concretas. |
| `agentes/tools.py` | Herramientas del agente: `consultar_precio_cardmarket`, `consultar_stock_local`, `consultar_datos_carta`, `consultar_reglas_mtg`, `consultar_lore_mtg`, `listar_cartas_disponibles` (catálogo), `sugerir_cartas_mazo` (armado de mazos, devuelve las cartas como *artifact* para el abanico), `iniciar_propuesta` (abre el formulario de propuesta en el chat, precargado con lo que dijo el cliente) y las de compra `agregar_al_carrito` (con `variante_id` opcional si hay varias), `ver_carrito`, `quitar_del_carrito`, `confirmar_compra(nombre, apellido, fecha_retiro, hora_retiro)` (reciben el `thread_id` por `RunnableConfig`, invisible para el modelo). |
| `tienda/cartas.py` | Todo lo de Scryfall: `ficha`, `buscar` (carta 3D + variantes de la tienda), `resolver_nombre` (normaliza nombres ES/mal escritos, con caché), `autocompletar`, `impresiones`, `impresion_por_id`, `total_pool_standard`, `colores_de` (identidad de color WUBRG), `precios_actuales` (precio de mercado en lote vía `POST /cards/collection`, 75 por pedido). |
| `tienda/tienda.py` | Carrito por `thread_id` y pedidos. `validar_retiro` controla día/hora contra los horarios configurados. `confirmar_pedido` (chat) y `crear_pedido_manual` (panel) reservan el stock en la misma transacción. Estados `pendiente` / `realizada` / `rechazada`: rechazar devuelve las cartas al stock y reactivar las vuelve a reservar. |
| `agentes/reglas.py` | **Ajani**, subagente juez (imports de torch/Chroma lazy; si faltan, `motivo_no_disponible` lo explica): traduce la pregunta a inglés → `similarity_search` (k=15) → rerank (k=6) → ChatGroq juez que cita números de regla. Expansión léxica ES→EN. |
| `agentes/lore.py` | **Teferi**, subagente erudito de lore: mismo pipeline que `reglas.py` pero con `lore_db/` (colección `lore_mtg`); reutiliza sus singletons (`_traducir`, `_juez_llm`, embeddings, rerank). Cita los artículos de origen. |
| `ingesta/ingestar_reglas.py` | Descarga las Comprehensive Rules, las parte en chunks (1500 chars, overlap 200) con metadata `regla`/`titulo`/`seccion`, e indexa en Chroma. |
| `ingesta/ingestar_lore.py` | ETL del lore **resumible**: baja la MTG Wiki (Fandom) con checkpoint en `backend/lore/` (`paginas.jsonl` append-only + `estado.json` + `ronda.json` con manifiesto por ronda), escaneando categorías raíz (BFS) y una lista curada de títulos; `--index` reconstruye `lore_db/` offline. |
| `scripts/test_local.py` | Chat por consola para probar al agente sin front: `..\.venv\Scripts\python -m scripts.test_local`. |

### Frontend (`frontend/src/`)

`tienda/` (página del chat, entra por `tienda/main.jsx` desde `index.html`), `vendedor/` (panel, entra por `vendedor/main.jsx` desde `vendedor.html`) y `compartido/` (`formato.js`, lo usan las dos).

Tienda (`index.html` → `src/tienda/`): `App.jsx` (chat + flujo), `api.js` (fetch), `Carta3D.jsx` (carta 3D con selector de variante y precio en pesos), `Carrito.jsx` (cajón con "Finalizar compra", que manda el pedido de cierre al chat), `Bolitas.jsx`, `Abanico.jsx` (mazo en abanico que se achica al ancho del chat, sin scroll lateral), `Catalogo.jsx` (lista con buscador y filtros: color, M/C, grado/PSA, expansión, precio mín/máx, orden, con descuento), `FormPropuesta.jsx` (ofrecer una carta: autocompletado de Scryfall → edición → grado/cantidad/precio en $ o US$ → nombre, apellido y mail obligatorios), `../compartido/formato.js` (pesos/dólares), `styles.css`. El tope de stock del carrito se verifica en `tienda.agregar` (lo usan tanto el endpoint como la herramienta del agente).

Panel del vendedor (`vendedor.html` → `src/vendedor/`): `Panel.jsx` (entrada con clave en `sessionStorage`, pestañas en el hash de la URL), `Inventario.jsx` (grilla, filtros, selección, edición, borrado), `AgregarCarta.jsx` (autocompletado de Scryfall → impresión → grado/cantidad/precio), `Pedidos.jsx` (calendario mensual por fecha de retiro, panel del día, nuevo pedido, editar, sacar), `Propuestas.jsx` (lista de propuestas con filtros por estado, buscador, nota interna, aceptar y cargar al inventario, rechazar; globito con las nuevas en la pestaña), `Dashboard.jsx` + `PanelesVentas.jsx` (torta de colores, lista de cartas, barras de expansiones, alertas) + `GraficoVentas.jsx`, `Historial.jsx` (tabla "Protocolo" con comentario editable y export CSV), `Configuracion.jsx` (horarios, dólar, stock bajo, panel de descuentos), `comunes.jsx`, `api.js`, `vendedor.css` (misma estética cuero/pergamino que la tienda).

### Reglas del repo

- Gitignoreado: `credentials.json`, `.env`, `.venv/`, `__pycache__/`, `*.pyc`, `key.txt`, `urza.db`, `backend/reglas/`, `backend/reglas_db/`, `backend/lore/`, `backend/lore_db/` (regenerables), `node_modules/`.
- Nunca commitear claves. `backend/.env` es local.
- El agente **nunca inventa** datos de cartas/reglas/lore: solo de herramientas.
- Respuestas cortas (2-3 oraciones), español rioplatense.
- Los datos de reglas salen de `consultar_reglas_mtg` y se transmiten tal cual (la palabra del juez).
- Los datos de lore salen de `consultar_lore_mtg` y se transmiten tal cual (la palabra del erudito).

### Pruebas (`backend/tests/`)

```powershell
cd backend
uv run --with pytest python -m pytest tests -q
```
~107 pruebas de integración contra la API real (FastAPI `TestClient`), sin red ni API key: copian el backend a una carpeta temporal con una base nueva por prueba, simulan Scryfall y dolarapi (`tests/falsos/red.py`, incluye fallas: sin red, timeout, 429, JSON roto) y reemplazan Groq por uno falso que sigue un guion (`tests/falsos/langchain_groq.py`) y **valida el historial como la API real** (un pedido de herramienta sin respuesta = error 400). Cubren inventario, alertas de precio, descuentos, carrito, retiros, pedidos (incluida la confirmación en paralelo de la última copia), propuestas, dashboard, configuración, que todo `/vendedor/*` pida clave, migraciones, una copia de `backend/urza.db` si existe, y el chat de punta a punta (compra completa, mazo, propuesta, reglas, fallas de Scryfall y de Groq, historial largo).

Garantías que cubren las pruebas (no romper):
- **Stock**: `_crear_pedido` corre dentro de `tienda._transaccion()` (`BEGIN IMMEDIATE`): dos confirmaciones a la vez no reservan la misma copia; las líneas repetidas de un pedido se suman; el carrito se relee dentro de la transacción (un doble clic no duplica el pedido). El dólar se refresca **antes** de abrir la transacción (refrescarlo adentro escribe desde otra conexión y se traba).
- **Chat**: el `ToolNode` tiene `handle_tool_errors` (una herramienta que falla vuelve como mensaje, no corta el turno); `agent_sales._reparar` completa pedidos de herramienta sin respuesta y `_recortar` manda a Groq sólo los últimos `MAX_MENSAJES` (30) empezando en un mensaje del jugador; `sin_razonamiento` saca los `<think>…</think>` de Qwen3. `/chat` limita `texto` a 2000 caracteres.
- **Planilla de venta**: el respaldo de `api.py` no actúa si en el turno se usaron reglas, lore, mazos, carrito o compra; "tengo X a N" sólo cuenta como venta si N parece un precio.
- `base.conectar()` cierra la conexión al salir del `with` (antes quedaban abiertas hasta el recolector).
- Un pedido (chat o manual) no puede incluir cartas sin precio. El mail de las propuestas sólo acepta caracteres comunes (misma regla en `FormPropuesta.jsx`). `inventario.csv` se lee como `utf-8-sig` (Excel le pone BOM).
- Frontend: el catálogo se pide una vez al abrirse; en Configuración cada "Guardar" actualiza sólo su sección; `Confirmar` muestra el error si la acción falla.

### Deuda técnica / pendientes operativos

- Los modelos de HuggingFace se descargan la primera vez (lento; sin `HF_TOKEN` aparece warning).
- `POST /propuestas` es público (cualquiera puede mandar propuestas): tiene validación y topes de largo, pero no límite de cantidad por IP.
- `frontend/node_modules` fue trackeado por error en commits viejos; se corrigió para dejar de seguirlo (historial queda pesado si se clona).

---

## Parte B — Especificación viva

Convención: cada feature con criterios de aceptación medibles y estado `[Implementado]` / `[En curso]` / `[Pendiente]`.

### Implementadas

**FE-01 · Consultar stock local** — **[Implementado]**
- *Como* jugador, *quiero* preguntar si hay una carta, *para* saber si puedo comprarla.
- Comportamiento: `consultar_stock_local` lee la tabla `inventario` y lista cada variante (set, grado, precio en pesos con descuento, unidades).
- Aceptación: "¿Tenés Cavern of Souls?" → devuelve el stock real de la base. Sin inventario no afirma stock.

**FE-02 · Precio de cartas** — **[Implementado]**
- *Como* jugador, *quiero* saber el precio de una carta, *para* decidir la compra.
- Comportamiento: `consultar_precio_cardmarket` vía Scryfall (precio `eur`).
- Aceptación: "Precio de Llanowar Elves" → responde `€X` o dice que no hay precio registrado.

**FE-03 · Ficha 3D de carta en el chat** — **[Implementado]**
- *Como* jugador, *quiero* ver la carta mientras hablo, *para* reconocerla.
- Comportamiento: `chat` devuelve `carta` (ficha de `cartas.ficha`) y el front monta `Carta3D`.
- Aceptación: al pedir una carta por nombre, el mensaje incluye `herramientas` con `consultar_datos_carta` y el front muestra la ficha 3D.

**FE-04 · Compra por chat con retiro en el local** — **[Implementado]** (reemplaza a las cuentas de usuario)
- *Como* jugador, *quiero* armar mi compra charlando con Urza y dejar mis datos al final, *para* pasar a retirarla sin crear una cuenta.
- Comportamiento: no hay usuarios. El carrito se ata al `thread_id` de la charla. Cuando el jugador dice que quiere comprar, el agente llama a `agregar_al_carrito` (si hay varias variantes con stock, pregunta cuál) y pregunta si suma algo más o da por finalizada la compra. Al finalizar pide **nombre y apellido** y **qué día y a qué hora quiere retirar**, resume y, con la confirmación, llama a `confirmar_compra` con fecha (AAAA-MM-DD) y hora (HH:MM): se valida contra los horarios configurados, se crea el pedido `pendiente`, se reserva el stock y se vacía el carrito. El botón de la carta 3D y "Finalizar compra" del cajón usan el mismo carrito.
- Aceptación: pedir más copias que el stock → el agente avisa el tope (y el endpoint da 409); un domingo cerrado o una hora fuera de rango → la herramienta devuelve el motivo y el agente pide otro horario; `confirmar_compra` nunca se llama sin nombre, apellido, día y hora dichos por el jugador; tras confirmar, el pedido aparece en el calendario del panel y el stock baja.

**FE-05 · Juez de reglas con RAG** — **[Implementado]** (commit `d2aec80`)
- *Como* jugador, *quiero* resolver una jugada o interacción, *para* jugar bien sin discutir.
- Comportamiento: el agente detecta consulta de reglas → `consultar_reglas_mtg` (Chroma + rerank + LLM juez) → responde citando números de regla. El juez solo usa el contexto provisto.
- Aceptación: pregunta de timing (ej. "¿puedo responder con un instante antes de que la criatura muera?") → responde con base legal y `Bases consultadas: NNN, NNN`. Si no se ingirió el RAG, avisa que corran `uv run python -m ingesta.ingestar_reglas` en vez de romper.

**FE-07 · Agente de Lore** — **[Implementado]**
- *Como* jugador, *quiero* preguntar por la historia/narrativa de MTG (planos, personajes, trasfondo de cartas), *para* conocer el lore.
- Comportamiento: el agente detecta consulta de lore → `consultar_lore_mtg` (subagente erudito en `lore.py`, espejo del juez FE-05: traduce ES→EN, `similarity_search` k=15, rerank k=6, ChatGroq) → responde citando los artículos de origen. Corpus = intros de la MTG Wiki (`ingestar_lore.py`, ETL resumible en `backend/lore/`).
- Aceptación: "¿Quién fue Urza?" → respuesta con fuentes y `Fuentes consultadas: ...`; pregunta de reglas NO se desvía a lore (va a `consultar_reglas_mtg`); si no se ingirió `lore_db/`, avisa que corran `uv run python -m ingesta.ingestar_lore` en vez de romper.
- FE-08 (alta de stock del vendedor) ya está resuelto desde el panel Mesa Central (FE-11).

### Pendientes (por prioridad)

**FE-06 · Informar al vendedor** — **[Pendiente]**
- *Como* vendedor, *quiero* que URZA me avise cuando un jugador deja una consulta o intención de compra, *para* estar al tanto sin mirar la base.
- Base disponible: los pedidos confirmados ya aparecen en el panel (calendario, dashboard e historial). Falta el aviso activo (email/notificación).
- Estado de diseño: definición de "aviso" (email/panel/webhook) y qué dispara (compra concreta, consulta de carta fuera de stock...). Quedó sin implementar desde el MVP inicial.

**FE-08 · Alta de stock (solo vendedor)** — **[Implementado desde el panel]** · pendiente: hacerlo también por chat
- *Como* vendedor, *quiero* agregar cartas al inventario, *para* mantener el stock al día.
- Restricción de rol: **únicamente el vendedor** (clave `VENDEDOR_CLAVE`, header `X-Vendedor-Clave`); el jugador **nunca** puede escribir stock (el chat no tiene herramientas de escritura de inventario).
- Implementado: Mesa Central → Inventario → "Agregar carta" (Scryfall). Persistencia en la tabla `inventario`.
- Aceptación: el vendedor agrega una carta y `consultar_stock_local` la refleja de inmediato; sin clave, `/vendedor/*` responde 401.

**FE-11 · Panel del vendedor (Mesa Central)** — **[Implementado]**
- *Como* vendedor, *quiero* un panel con inventario, pedidos, dashboard, historial y configuración, *para* manejar la tienda sin tocar la base.
- Inventario: grilla con imagen, set · rareza, precio en pesos, grado (Sin graduar / PSA 1-10), stock y estado (en stock / bajo / sin stock); búsqueda por carta, set o SKU; filtros; selección para editar o borrar; alta desde Scryfall con autocompletado y elección de impresión.
- Pedidos: calendario mensual por fecha de retiro (días cerrados rayados), panel del día con detalle y acciones (entregado / rechazar / volver a pendiente), nuevo pedido manual, editar, sacar pedidos.
- Dashboard: unidades, valor del inventario, pedidos abiertos, cartas sin stock, actividad reciente, resumen del stock (disponible / reservado / vendido 30 días), próximos retiros y cobertura del pool de Standard (cartas legales con stock / total de Scryfall).
- Historial ("Protocolo"): fecha y hora de retiro, fecha y hora de pedido, nombre, unidades, detalle, comentario del vendedor (editable en la fila); filtros por texto, estado y rango de fechas; export CSV (`;`, UTF-8 con BOM para Excel).
- Configuración: horarios por día (los usa el chat para validar retiros), dólar automático (dolarapi: blue/oficial/tarjeta/MEP/…) o manual, umbral de stock bajo y panel de descuentos (general + por carta; se aplica el mayor).

**FE-09 · Armador de mazos** — **[Implementado como herramienta]** (sin subagente: `sugerir_cartas_mazo` en `tools.py`)
- *Como* jugador, *quiero* recomendaciones para construir un mazo, *para* armar mi lista.
- Comportamiento: combina recomendaciones de **Scryfall** (búsqueda por color/tipo/sinergia) con **stock local** (`consultar_stock_local`) para priorizar lo que la tienda tiene.
- Aceptación: pedido de un arquetipo (ej. "mazo de Cabaleros de X color") → devuelve cartas candidatas indicando cuáles hay en la tienda.
- Implementado: la herramienta arma la búsqueda de Scryfall (`cartas.consulta_mazo`: colores en español o letras → `id<=`, formato → `f:`, tipo → `t:`, palabras clave en inglés → `t:/o:`), ordena por popularidad (EDHREC) y pone primero las que hay en stock. El chat las muestra en un **abanico** (`Abanico.jsx`): al pasar el cursor sube la carta y muestra sólo el nombre.

**FE-12 · Catálogo y variantes en el chat** — **[Implementado]**
- "¿Qué cartas tenés?" → `listar_cartas_disponibles` → el agente responde "Las cartas disponibles son…" y aparece el botón **Ver todas las cartas** (`Catalogo.jsx`: lista simple con buscador, de `GET /catalogo`).
- Si una carta está en varias versiones (mismo nombre, distinto PSA o set), la carta 3D muestra **todas**, una al lado de la otra, cada una con su grado, precio y botón para agregar.
- Panel: Inventario → **Otro PSA** agrega la misma impresión con otro grado (`POST /vendedor/inventario/{id}/variante`), sin volver a Scryfall.

**FE-14 · Precio sugerido por grado y ventas del mes** — **[Implementado]**
- Scryfall sólo da el precio sin graduar. Al cargar una PSA (Agregar carta / Otro PSA) el precio se sugiere con `GET /vendedor/precio-sugerido`: si hay `PRICECHARTING_TOKEN` en `backend/.env` usa PriceCharting (API paga; PSA 10/9/8/7, precios en centavos), si no, el **multiplicador por grado** de Configuración sobre el precio de Scryfall. El vendedor siempre puede cambiarlo.
- Dashboard: **Ventas del último mes** (`GraficoVentas.jsx`), barras por día ($) o por carta (unidades), con tooltip y vista de tabla. Fecha de venta = cuándo se marcó "realizada" (movimiento `venta`).

**FE-13 · Registro de actividad** — **[Implementado]**
- Todo cambio queda en `movimientos`: pedidos (alta por chat o a mano), cambios de estado en cualquier sentido (incluido volver a pendiente), comentarios agregados/editados/borrados, retiros reprogramados, altas/ajustes/bajas de stock, nuevos grados, horarios, dólar, stock bajo y descuentos.
- Se ve al final de **Configuración → Registro de actividad** (`RegistroActividad.jsx`, `GET /vendedor/actividad?q=&tipo=&antes_de=`), con buscador, filtro por grupo y "Cargar más". Ya no está en el Dashboard.

**FE-15 · Equipo de agentes con nombre** — **[Implementado]**
- Urza orquesta; Tibalt vende, Ajani hace de juez, Teferi cuenta el lore y Saheeli arma mazos. El chat muestra debajo de cada respuesta a quién consultó Urza.

**FE-16 · Propuestas de venta de clientes** — **[Implementado]**
- *Como* jugador, *quiero* ofrecerle una carta a la tienda ("tengo X en PSA 9 a $Y"), *para* vendérsela.
- El agente llama `iniciar_propuesta` y aparece el formulario: la carta **se elige de la lista de todas las cartas existentes** (Scryfall) y la edición exacta; si el cliente la nombró, el agente le pide que la busque en la lista para mayor precisión. **Nombre, apellido y mail son obligatorios** (validados en el front y en `propuestas._validar`); el agente nunca dice que se envió hasta que se manda el formulario (`POST /propuestas`).
- La planilla aparece **siempre**, aunque el modelo no llame a la herramienta: `api.py` usa `propuestas.quiere_vender(texto)` (reglas fijas: "vendo", "quiero venderles", "tengo X PSA 9 a $Y", "me la comprás"… y nunca "¿venden X?") y la precarga con `propuestas.datos_desde_texto` (carta, PSA, precio, moneda, cantidad). Cuando se abre la planilla no se muestra la carta 3D de la tienda. Además, el chat tiene el botón **Ofrecer una carta a la tienda** (y la sugerencia "Quiero venderles una carta") que la abre al toque sin pasar por el agente.
- Panel → pestaña **Propuestas** (`GET/PATCH/DELETE /vendedor/propuestas`, `POST /vendedor/propuestas/{id}/al-inventario`). Una propuesta se carga al inventario **una sola vez** (columna `cargada`); una aceptada "sin cargar" se puede cargar después.

**FE-17 · Dashboard de movimientos y alertas** — **[Implementado]**
- Movimientos de cartas por período (30 / 90 días / todo): **color más vendido** (torta), **cartas más vendidas** (lista), **expansiones más vendidas** (barras). Los colores se guardan en `pedido_items.colores` (ventas viejas sin color salen como "Sin dato").
- **Alertas de inventario**: cambios bruscos de precio de mercado (umbral `alerta_precio` en Configuración, 30% por defecto), aviso global si la mediana del mercado se movió, y stock que cayó ≥50% en 7 días.
- Inventario → **Precios a revisar** arriba de todo, con dos avisos: (1) **tu precio lejos del mercado de hoy** (`vs_mercado_pct`; para graduadas el mercado se estima con Scryfall × multiplicador y el umbral es el doble), útil cuando cargás una carta carísima o regalada; (2) **el mercado se movió** desde que pusiste el precio. Botones "Poner US$ X" y **"Dejarlo así"** (`POST /vendedor/inventario/{id}/mantener-precio`, guarda `precio_aceptado_usd`: no se avisa más hasta que cambies ese precio).
- Detalle del aviso (2): compara el precio de mercado de Scryfall de hoy (`precio_mercado_usd`, refresco cada 6 h o con "Actualizar precios de mercado") contra el que había cuando el vendedor puso su precio (`mercado_referencia_usd`) y sugiere ajustar en la misma proporción (botón "Poner US$ X"). Funciona igual para PSA.

**FE-10 · Reconocimiento de fotos de cartas** — **[Pendiente · última prioridad]**
- Doble uso según el rol autenticado, con objetivos distintos:
  - *Como* **jugador**, quiero enviar o sacar una foto de una carta y que me diga si hay stock, *para* saber si puedo comprarla (solo consulta).
  - *Como* **vendedor**, quiero enviar o sacar una foto de una carta y que la cargue al stock, *para* mantener el inventario al día (da de alta).
- Comportamiento: la visión reconoce la carta en la imagen → se verifica con `resolver_nombre` (`cartas.py`) → según rol: consulta stock **o** alta de stock (misma regla de seguridad que FE-08; el jugador jamás escribe).
- Aceptación: foto de carta → nombre oficial correcto; jugador → respuesta de stock sin escritura; vendedor → carta agregada y visible en `consultar_stock_local`.
- Nota de diseño (abierta): modelo de visión/OCR para identificar la carta (ej. reconocer por el arte vía Scryfall, o modelo multimodal vía API).