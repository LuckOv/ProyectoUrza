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

No hay cuentas de jugador: el carrito se ata a la conversación (`thread_id`) y la compra se cierra desde el propio chat, que pide nombre, apellido y día y hora de retiro. El vendedor administra todo desde **Mesa Central** (`frontend/vendedor.html`), protegido con una clave. El front son dos páginas React/Vite (tienda + panel). Todo se habla en **español rioplatense**.

### Stack

- Python **3.13** con gestor de paquetes **uv** (`pyproject.toml` + `uv.lock`, venv en `.venv/`).
- Backend: **FastAPI** + **LangChain** + **LangGraph** (`StateGraph` + checkpointer `MemorySaver`).
- LLM: **ChatGroq**, modelo `qwen/qwen3.8-27b`, `temperature=0`, `max_tokens=500` (tope del plan free de Groq; sin eso da 429).
- RAG de reglas: **Chroma** (`backend/reglas_db/`), embeddings `paraphrase-multilingual-MiniLM-L12-v2`, rerank `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, juez = mismo ChatGroq.
- Frontend: **React 19 + Vite 8**.
- Datos: SQLite `backend/urza.db` (inventario, carrito por charla, pedidos, movimientos, config, descuentos), API de **Scryfall** (fichas, imágenes, impresiones), **dolarapi.com** (cotización). `backend/inventario.csv` sólo se usa para la importación inicial.

### Cómo levantarlo

Credenciales en **`backend/.env`** (gitignoreado): `GROQ_API_KEY` (obligatoria), `VENDEDOR_CLAVE` (clave del panel; si falta, es `urza` y el panel lo avisa) y `HF_TOKEN` (opcional, evita rate limits de HuggingFace). `load_dotenv()` (presente en `agent_sales.py` y `reglas.py`) busca el `.env` en el **directorio de trabajo**: arrancar siemPR desde `backend/`.

**Backend** (parado en `backend/`):
```powershell
..\.venv\Scripts\python.exe -m uvicorn api:app --reload --port 8000
```
- `GET /salud` → dice si el grafo se inicializó bien.
- `POST /chat` `{thread_id, texto}` → respuesta del agente + herramientas usadas + carta (si habló de una) + `carrito` actualizado + `pedido` (texto del comprobante si en ese turno se confirmó la compra).
- Carrito por charla: `GET/POST/DELETE /carrito/{thread_id}` (el POST recibe `{inventario_id, cantidad}`), `DELETE /carrito/{thread_id}/{item_id}`.
- `GET /carta?nombre=` → ficha para la carta 3D, con `variantes` y precio en pesos.
- Panel del vendedor: todo bajo `/vendedor/*` con header `X-Vendedor-Clave` (ver `vendedor.py` o `/docs`): inventario, Scryfall (autocompletar/impresiones), pedidos, `historial.csv`, dashboard, config y descuentos.

**Frontend** (parado en `frontend/`): `npm run dev` (dev) / `npm run build` (producción). Tienda en `http://localhost:5173/`, panel del vendedor en `http://localhost:5173/vendedor.html`.

**RAG de reglas**: si `backend/reglas_db/` no existe, ingestar desde `backend/`:
```powershell
uv run python ingestar_reglas.py            # baja las Comprehensive Rules y las indexa
uv run python ingestar_reglas.py --rebuild  # re-indexa desde cero
```

### Arquitectura (backend/)

| Archivo | Rol |
|---|---|
| `api.py` | API HTTP. Al arrancar: `base.preparar()` (crea/migra tablas), importa el CSV viejo si el inventario está vacío y completa imágenes/precios desde Scryfall en segundo plano. Carga el grafo en forma lazy. Incluye los routers de `vendedor.py`. |
| `base.py` | Conexión SQLite, esquema (versión en `PRAGMA user_version`), configuración dinámica (`horarios`, `dolar`, `stock_bajo`, `descuento_general`) y registro de `movimientos`. Hora fija de Argentina (UTC-3). |
| `inventario.py` | Inventario por variante (impresión + grado), SKU `URZ-0001`, precio en pesos = `precio_usd × dólar × (1 − descuento)`, dólar automático (dolarapi, refresco cada hora) o manual, descuentos general y por carta, alta desde Scryfall, importación del CSV viejo. |
| `vendedor.py` | Endpoints `/vendedor/*` del panel, protegidos por `VENDEDOR_CLAVE`. Dashboard, export CSV del historial, config. |
| `graph.py` | Grafo: nodo `Ventas` (`agent_ventas`) → `tools` (ToolNode) → vuelve a `Ventas`; `MemorySaver` con `thread_id` por pestaña. |
| `agent_sales.py` | Prompt del agente (reglas de herramientas + flujo de compra + estilo). Se arma en cada turno con la fecha de hoy y los horarios de la tienda (`system_prompt()`), así el agente convierte "el sábado a las 5" en fecha y hora concretas. |
| `tools.py` | Herramientas del agente: `consultar_precio_cardmarket`, `consultar_stock_local`, `consultar_datos_carta`, `consultar_reglas_mtg` y las de compra `agregar_al_carrito` (con `variante_id` opcional si hay varias), `ver_carrito`, `quitar_del_carrito`, `confirmar_compra(nombre, apellido, fecha_retiro, hora_retiro)` (reciben el `thread_id` por `RunnableConfig`, invisible para el modelo). |
| `cartas.py` | Todo lo de Scryfall: `ficha`, `buscar` (carta 3D + variantes de la tienda), `resolver_nombre` (normaliza nombres ES/mal escritos, con caché), `autocompletar`, `impresiones`, `impresion_por_id`, `total_pool_standard`. |
| `tienda.py` | Carrito por `thread_id` y pedidos. `validar_retiro` controla día/hora contra los horarios configurados. `confirmar_pedido` (chat) y `crear_pedido_manual` (panel) reservan el stock en la misma transacción. Estados `pendiente` / `realizada` / `rechazada`: rechazar devuelve las cartas al stock y reactivar las vuelve a reservar. |
| `reglas.py` | Subagente juez: traduce la pregunta a inglés → `similarity_search` (k=15) → rerank (k=6) → ChatGroq juez que cita números de regla. Expansión léxica ES→EN. |
| `ingestar_reglas.py` | Descarga las Comprehensive Rules, las parte en chunks (1500 chars, overlap 200) con metadata `regla`/`titulo`/`seccion`, e indexa en Chroma. |
| `test_local.py` | Chat por consola para probar al agente sin front: `..\.venv\Scripts\python test_local.py`. |

### Frontend (`frontend/src/`)

Tienda (`index.html`): `App.jsx` (chat + flujo), `api.js` (fetch), `Carta3D.jsx` (carta 3D con selector de variante y precio en pesos), `Carrito.jsx` (cajón con "Finalizar compra", que manda el pedido de cierre al chat), `Bolitas.jsx`, `formato.js` (pesos/dólares, compartido), `styles.css`. El tope de stock del carrito se verifica en `tienda.agregar` (lo usan tanto el endpoint como la herramienta del agente).

Panel del vendedor (`vendedor.html` → `src/vendedor/`): `Panel.jsx` (entrada con clave en `sessionStorage`, pestañas en el hash de la URL), `Inventario.jsx` (grilla, filtros, selección, edición, borrado), `AgregarCarta.jsx` (autocompletado de Scryfall → impresión → grado/cantidad/precio), `Pedidos.jsx` (calendario mensual por fecha de retiro, panel del día, nuevo pedido, editar, sacar), `Dashboard.jsx`, `Historial.jsx` (tabla "Protocolo" con comentario editable y export CSV), `Configuracion.jsx` (horarios, dólar, stock bajo, panel de descuentos), `comunes.jsx`, `api.js`, `vendedor.css` (misma estética cuero/pergamino que la tienda).

### Reglas del repo

- Gitignoreado: `credentials.json`, `.env`, `.venv/`, `__pycache__/`, `*.pyc`, `key.txt`, `urza.db`, `backend/reglas/`, `backend/reglas_db/` (regenerable), `node_modules/`.
- Nunca commitear claves. `backend/.env` es local.
- El agente **nunca inventa** datos de cartas/reglas: solo de herramientas.
- Respuestas cortas (2-3 oraciones), español rioplatense.
- Los datos de reglas salen de `consultar_reglas_mtg` y se transmiten tal cual (la palabra del juez).

### Deuda técnica / pendientes operativos

- `main` está 1 commit adelante de `origin/main` (falta `git push`).
- Los modelos de HuggingFace se descargan la primera vez (lento; sin `HF_TOKEN` aparece warning).
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
- Aceptación: pregunta de timing (ej. "¿puedo responder con un instante antes de que la criatura muera?") → responde con base legal y `Bases consultadas: NNN, NNN`. Si no se ingirió el RAG, avisa que corran `ingestar_reglas.py` en vez de romper.

### Pendientes (por prioridad)

**FE-06 · Informar al vendedor** — **[Pendiente]**
- *Como* vendedor, *quiero* que URZA me avise cuando un jugador deja una consulta o intención de compra, *para* estar al tanto sin mirar la base.
- Base disponible: los pedidos confirmados ya aparecen en el panel (calendario, dashboard e historial). Falta el aviso activo (email/notificación).
- Estado de diseño: definición de "aviso" (email/panel/webhook) y qué dispara (compra concreta, consulta de carta fuera de stock...). Quedó sin implementar desde el MVP inicial.

**FE-07 · Agente de Lore** — **[Pendiente]**
- *Como* jugador, *quiero* preguntar por la historia/narrativa de MTG (planos, personajes, trasfondo de cartas), *para* conocer el lore.
- Nota de diseño: replicar el patrón del juez (FE-05) con otra fuente de conocimiento (RAG sobre lore) en vez de reglas.

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

**FE-09 · Armador de mazos** — **[Pendiente]**
- *Como* jugador, *quiero* recomendaciones para construir un mazo, *para* armar mi lista.
- Comportamiento: combina recomendaciones de **Scryfall** (búsqueda por color/tipo/sinergia) con **stock local** (`consultar_stock_local`) para priorizar lo que la tienda tiene.
- Aceptación: pedido de un arquetipo (ej. "mazo de Cabaleros de X color") → devuelve cartas candidatas indicando cuáles hay en la tienda.

**FE-10 · Reconocimiento de fotos de cartas** — **[Pendiente · última prioridad]**
- Doble uso según el rol autenticado, con objetivos distintos:
  - *Como* **jugador**, quiero enviar o sacar una foto de una carta y que me diga si hay stock, *para* saber si puedo comprarla (solo consulta).
  - *Como* **vendedor**, quiero enviar o sacar una foto de una carta y que la cargue al stock, *para* mantener el inventario al día (da de alta).
- Comportamiento: la visión reconoce la carta en la imagen → se verifica con `resolver_nombre` (`cartas.py`) → según rol: consulta stock **o** alta de stock (misma regla de seguridad que FE-08; el jugador jamás escribe).
- Aceptación: foto de carta → nombre oficial correcto; jugador → respuesta de stock sin escritura; vendedor → carta agregada y visible en `consultar_stock_local`.
- Nota de diseño (abierta): modelo de visión/OCR para identificar la carta (ej. reconocer por el arte vía Scryfall, o modelo multimodal vía API).