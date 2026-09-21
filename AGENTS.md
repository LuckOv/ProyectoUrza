# URZA — Contexto de sesión y especificación viva (SDD)

Este archivo le da contexto a cualquier agente/LLM que abra una sesión en el repo. Parte A = traspaso (qué hay, cómo se levanta, cómo funciona). Parte B = especificación viva estilo **Spec-Driven Development**: cada feature con historia de usuario, comportamiento esperado, criterios de aceptación y estado. Cuando se cambie de rumbo o se cierre una feature, actualizar la Parte B en el mismo commit.

---

## Parte A — Contexto del proyecto

### Qué es

URZA es el asistente virtual de una tienda de cartas de **Magic: The Gathering**. El usuario chatea con un agente LangGraph que consulta:

- **Stock local** (`backend/inventario.csv`).
- **Precios** en euros (CardMarket, vía API de Scryfall).
- **Ficha/datos de cartas** (tipo, colores, texto de reglas, legalidad — Scryfall).
- **Reglas del juego** (RAG sobre las Comprehensive Rules oficiales → "subagente juez").

Tiene cuentas de usuario y carrito (SQLite). El front es una SPA de React/Vite. Todo se habla en **español rioplatense**.

### Stack

- Python **3.13** con gestor de paquetes **uv** (`pyproject.toml` + `uv.lock`, venv en `.venv/`).
- Backend: **FastAPI** + **LangChain** + **LangGraph** (`StateGraph` + checkpointer `MemorySaver`).
- LLM: **ChatGroq**, modelo `qwen/qwen3.8-27b`, `temperature=0`, `max_tokens=500` (tope del plan free de Groq; sin eso da 429).
- RAG de reglas: **Chroma** (`backend/reglas_db/`), embeddings `paraphrase-multilingual-MiniLM-L12-v2`, rerank `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, juez = mismo ChatGroq.
- Frontend: **React 19 + Vite 8**.
- Datos: `backend/inventario.csv` (stock/precio local), API de **Scryfall** (precios/fichas), SQLite `backend/urza.db` (usuarios/sesiones/carrito).

### Cómo levantarlo

Credenciales en **`backend/.env`** (gitignoreado): `GROQ_API_KEY` (obligatoria) y `HF_TOKEN` (opcional, evita rate limits de HuggingFace). `load_dotenv()` (presente en `agent_sales.py` y `reglas.py`) busca el `.env` en el **directorio de trabajo**: arrancar siemPR desde `backend/`.

**Backend** (parado en `backend/`):
```powershell
..\.venv\Scripts\python.exe -m uvicorn api:app --reload --port 8000
```
- `GET /salud` → dice si el grafo se inicializó bien.
- `POST /chat` `{thread_id, texto}` → respuesta del agente + herramientas usadas + carta (si habló de una).
- `POST /registro`, `POST /login`, `POST /logout`, `GET /yo`, carrito (GET/POST/DELETE), `GET /carta?nombre=`.

**Frontend** (parado en `frontend/`): `npm run dev` (dev) / `npm run build` (producción).

**RAG de reglas**: si `backend/reglas_db/` no existe, ingestar desde `backend/`:
```powershell
uv run python ingestar_reglas.py            # baja las Comprehensive Rules y las indexa
uv run python ingestar_reglas.py --rebuild  # re-indexa desde cero
```

### Arquitectura (backend/)

| Archivo | Rol |
|---|---|
| `api.py` | API HTTP. Carga el grafo en forma lazy. `sesion_opcional`/`sesion_requerida` por header `Authorization: Bearer`. |
| `graph.py` | Grafo: nodo `Ventas` (`agent_ventas`) → `tools` (ToolNode) → vuelve a `Ventas`; `MemorySaver` con `thread_id` por pestaña. |
| `agent_sales.py` | Prompt del agente (reglas de herramientas + estilo) y wrapper `agente_ventas(messages)` que inyecta el SystemMessage. |
| `tools.py` | Herramientas del agente: `consultar_precio_cardmarket`, `consultar_stock_local`, `consultar_datos_carta`, `consultar_reglas_mtg`. |
| `cartas.py` | Para el frontend: `ficha`, `resolver_nombre` (normaliza nombres ES/mal escritos vía Scryfall, con caché), `stock_de`. Datos ≠ `tools.py` (eso es para razonar). |
| `tienda.py` | Usuarios, sesiones (token, 7 días) y carrito en SQLite (`urza.db`). Claves con PBKDF2 (200k iteraciones, sal por usuario). |
| `reglas.py` | Subagente juez: traduce la pregunta a inglés → `similarity_search` (k=15) → rerank (k=6) → ChatGroq juez que cita números de regla. Expansión léxica ES→EN. |
| `ingestar_reglas.py` | Descarga las Comprehensive Rules, las parte en chunks (1500 chars, overlap 200) con metadata `regla`/`titulo`/`seccion`, e indexa en Chroma. |
| `test_local.py` | Chat por consola para probar al agente sin front: `..\.venv\Scripts\python test_local.py`. |

### Frontend (`frontend/src/`)

`App.jsx` (chat + flujo), `api.js` (fetch), `Carta3D.jsx` (carta 3D con `public/marco.png` y fuentes), `Carrito.jsx`, `Sesion.jsx` (login/registro), `Bolitas.jsx` (fondo de partículas), `styles.css`. `Carta3D` se monta cuando la respuesta incluye `carta` (la `ficha` que devuelve el API). Verificación de stock del carrito al agregar por **cliente** en `api.py`.

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
- Comportamiento: `consultar_stock_local` lee `backend/inventario.csv`; el agente responde cantidad y edición/foil.
- Aceptación: "¿Tenés Cavern of Souls?" → devuelve stock real del CSV (x, edición). Sin inventario no afirma stock.

**FE-02 · Precio de cartas** — **[Implementado]**
- *Como* jugador, *quiero* saber el precio de una carta, *para* decidir la compra.
- Comportamiento: `consultar_precio_cardmarket` vía Scryfall (precio `eur`).
- Aceptación: "Precio de Llanowar Elves" → responde `€X` o dice que no hay precio registrado.

**FE-03 · Ficha 3D de carta en el chat** — **[Implementado]**
- *Como* jugador, *quiero* ver la carta mientras hablo, *para* reconocerla.
- Comportamiento: `chat` devuelve `carta` (ficha de `cartas.ficha`) y el front monta `Carta3D`.
- Aceptación: al pedir una carta por nombre, el mensaje incluye `herramientas` con `consultar_datos_carta` y el front muestra la ficha 3D.

**FE-04 · Cuentas y carrito** — **[Implementado]**
- *Como* jugador, *quiero* registrarme, entrar y armar un carrito, *para* reservar cartas.
- Comportamiento: registro/login (token 7 días), carrito persistido en `urza.db`, tope de unidades = stock real.
- Aceptación: sin cuenta no se agrega al carrito; sumar más de lo que hay da error 409 con el texto del tope.

**FE-05 · Juez de reglas con RAG** — **[Implementado]** (commit `d2aec80`)
- *Como* jugador, *quiero* resolver una jugada o interacción, *para* jugar bien sin discutir.
- Comportamiento: el agente detecta consulta de reglas → `consultar_reglas_mtg` (Chroma + rerank + LLM juez) → responde citando números de regla. El juez solo usa el contexto provisto.
- Aceptación: pregunta de timing (ej. "¿puedo responder con un instante antes de que la criatura muera?") → responde con base legal y `Bases consultadas: NNN, NNN`. Si no se ingirió el RAG, avisa que corran `ingestar_reglas.py` en vez de romper.

### Pendientes (por prioridad)

**FE-06 · Informar al vendedor** — **[Pendiente]**
- *Como* vendedor, *quiero* que URZA me avise cuando un jugador deja una consulta o intención de compra, *para* estar al tanto sin mirar la base.
- Estado de diseño: definición de "aviso" (email/panel/webhook) y qué dispara (compra concreta, consulta de carta fuera de stock...). Quedó sin implementar desde el MVP inicial.

**FE-07 · Agente de Lore** — **[Pendiente]**
- *Como* jugador, *quiero* preguntar por la historia/narrativa de MTG (planos, personajes, trasfondo de cartas), *para* conocer el lore.
- Nota de diseño: replicar el patrón del juez (FE-05) con otra fuente de conocimiento (RAG sobre lore) en vez de reglas.

**FE-08 · Alta de stock (solo vendedor)** — **[Pendiente]**
- *Como* vendedor, *quiero* agregar cartas al inventario desde el chat, *para* mantener el stock al día.
- Restricción de rol: **únicamente el vendedor**; el jugador **nunca** puede escribir stock.
- Preguntas abiertas a resolver al implementar: cómo se identifica al vendedor (rol/flag en `usuarios` de `urza.db`, o credencial dedicada) y dónde persistir (hoy es `inventario.csv`; opción: migrar a tabla SQLite).
- Aceptación: una sesión de vendedor agrega una carta y `consultar_stock_local` la refleja de inmediato; una sesión de jugador recibe rechazo/degradación a consulta.

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