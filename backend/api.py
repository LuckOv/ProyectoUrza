r"""API HTTP de URZA.

Va en backend/, al lado de graph.py.

Levantar con:
    ..\.venv\Scripts\python.exe -m uvicorn api:app --reload --port 8000
(parado dentro de la carpeta backend)

Probar que anda:          http://localhost:8000/salud
Ver todos los endpoints:  http://localhost:8000/docs

No hay cuentas de usuario. El carrito se identifica con el thread_id de la
charla (uno por pestaña), el mismo que usa el grafo para su memoria. La
compra se cierra desde el chat: el agente pide nombre, apellido y día y hora
de retiro, y registra el pedido.

El panel del vendedor (Mesa Central) usa los endpoints de vendedor.py, todos
bajo /vendedor y protegidos con la clave VENDEDOR_CLAVE del .env.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from tienda import base
from tienda import cartas
from tienda import inventario
from tienda import propuestas
from tienda import tienda
from panel import vendedor

app = FastAPI(title="URZA API")

# Crea o migra las tablas; la primera vez importa el inventario.csv viejo y
# completa imágenes y precios desde Scryfall sin frenar el arranque.
base.preparar()
inventario.importar_csv_viejo()
inventario.completar_en_segundo_plano()

# Cualquier puerto de localhost: Vite salta del 5173 al 5174 si el primero
# está ocupado, y con una lista fija el navegador bloquearía el pedido por
# CORS. En producción esto se reemplaza por el dominio real.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vendedor.router)
app.include_router(vendedor.protegido)


# --- modelos de entrada ------------------------------------------------------

class Consulta(BaseModel):
    thread_id: str
    texto: str


class ItemCarrito(BaseModel):
    inventario_id: int      # la variante exacta (set + grado) que se agrega
    cantidad: int = 1


# --- carrito -----------------------------------------------------------------
# El frontend usa estos endpoints para el botón "Agregar al carrito" de la
# carta y para el cajón. El agente toca el mismo carrito con sus herramientas.

@app.get("/carrito/{thread_id}")
def ver_carrito(thread_id: str):
    return {"items": tienda.ver_carrito(thread_id)}


@app.post("/carrito/{thread_id}")
def agregar_al_carrito(thread_id: str, item: ItemCarrito):
    try:
        items = tienda.agregar(thread_id, item.inventario_id, item.cantidad)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"items": items}


@app.delete("/carrito/{thread_id}/{item_id}")
def quitar_del_carrito(thread_id: str, item_id: int):
    return {"items": tienda.quitar(thread_id, item_id)}


@app.delete("/carrito/{thread_id}")
def vaciar_carrito(thread_id: str):
    return {"items": tienda.vaciar(thread_id)}


# --- cartas ------------------------------------------------------------------

class NuevaPropuesta(BaseModel):
    thread_id: str | None = None
    nombre: str
    apellido: str
    email: str
    scryfall_id: str
    grado: str = "Sin graduar"
    cantidad: int = 1
    precio: float
    moneda: str = "ARS"
    comentario: str = ""


@app.post("/propuestas")
def nueva_propuesta(datos: NuevaPropuesta):
    """El cliente le ofrece una carta a la tienda. Nombre, apellido y mail son obligatorios."""
    try:
        return propuestas.crear(
            datos.thread_id, datos.nombre, datos.apellido, datos.email, datos.scryfall_id,
            datos.grado, datos.cantidad, datos.precio, datos.moneda, datos.comentario,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/cartas/autocompletar")
def cartas_autocompletar(q: str):
    """Todas las cartas que existen (Scryfall), para elegir la que se propone."""
    return {"nombres": cartas.autocompletar(q), "grados": inventario.GRADOS}


@app.get("/cartas/impresiones")
def cartas_impresiones(nombre: str):
    return {"impresiones": cartas.impresiones(nombre)}


@app.get("/catalogo")
def catalogo():
    """Todas las cartas a la venta (con stock y precio), para la lista con buscador."""
    return {"items": inventario.catalogo()}


@app.get("/carta")
def carta(nombre: str):
    encontrada = cartas.buscar(nombre)
    if not encontrada:
        raise HTTPException(status_code=404, detail=f"No encontré la carta '{nombre}'.")
    return encontrada


# --- chat --------------------------------------------------------------------

_grafo = None

# Herramientas cuyo argumento nombre_carta NO debe disparar la carta 3D:
# si el jugador saca una carta del carrito, no tiene sentido volver a mostrarla.
_SIN_CARTA = {"quitar_del_carrito"}

# Qué planeswalker del equipo de Urza está detrás de cada herramienta.
AGENTE_DE = {
    "consultar_reglas_mtg": "Ajani",
    "consultar_lore_mtg": "Teferi",
    "sugerir_cartas_mazo": "Saheeli",
}   # el resto (stock, precios, carrito, compra, catálogo, propuestas) es Tibalt


def _obtener_grafo():
    global _grafo
    if _grafo is None:
        from agentes.graph import app_graph
        _grafo = app_graph
    return _grafo


@app.get("/salud")
def salud():
    """Chequeo rápido: dice si el agente pudo inicializarse."""
    try:
        _obtener_grafo()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/chat")
def chat(consulta: Consulta):
    vacia = {
        "texto": "", "herramientas": [], "carta": None,
        "carrito": tienda.ver_carrito(consulta.thread_id), "pedido": None,
        "mazo": None, "catalogo": False, "propuesta": None, "agentes": [],
    }

    try:
        grafo = _obtener_grafo()
    except Exception as e:
        return {**vacia, "error": f"No pude iniciar el agente: {e}"}

    config = {"configurable": {"thread_id": consulta.thread_id}}

    try:
        estado = grafo.invoke({"messages": [HumanMessage(content=consulta.texto)]}, config=config)
    except Exception as e:
        return {**vacia, "error": f"Falló la consulta al agente: {e}"}

    mensajes = estado.get("messages", [])
    if not mensajes:
        return {**vacia, "error": "El agente no devolvió ningún mensaje."}

    # Tramo posterior al último mensaje del usuario: ahí están las llamadas a
    # herramientas de este turno y la respuesta final.
    corte = 0
    for i in range(len(mensajes) - 1, -1, -1):
        if getattr(mensajes[i], "type", "") == "human":
            corte = i
            break
    tramo = mensajes[corte + 1:]

    herramientas = []
    args_por_id = {}
    ultimo_nombre = None
    pedido = None
    mazo = None
    catalogo_pedido = False
    propuesta = None
    agentes = []

    for m in tramo:
        for llamada in getattr(m, "tool_calls", None) or []:
            args_por_id[llamada.get("id")] = (llamada.get("name", ""), llamada.get("args", {}))
        if getattr(m, "type", "") == "tool":
            nombre, args = args_por_id.get(
                getattr(m, "tool_call_id", None),
                (getattr(m, "name", "herramienta"), {}),
            )
            resultado = str(m.content)
            herramientas.append({"nombre": nombre, "argumentos": args, "resultado": resultado})
            # De qué carta habló el agente. Sale de los argumentos con que
            # llamó a la herramienta, así no hay que adivinarlo del texto.
            if nombre not in _SIN_CARTA and isinstance(args, dict) and args.get("nombre_carta"):
                ultimo_nombre = args["nombre_carta"]
            # Si en este turno se cerró la compra, el front muestra el comprobante.
            if nombre == "confirmar_compra" and resultado.startswith("Pedido #"):
                pedido = resultado
            # Sugerencias de mazo: la herramienta devuelve las cartas como
            # "artifact" (datos aparte del texto) para dibujar el abanico.
            if nombre == "sugerir_cartas_mazo" and getattr(m, "artifact", None):
                mazo = [{"nombre": c["nombre"], "imagen": c.get("imagen")} for c in m.artifact]
            if nombre == "listar_cartas_disponibles":
                catalogo_pedido = True
            if nombre == "iniciar_propuesta" and getattr(m, "artifact", None) is not None:
                propuesta = m.artifact
            quien = AGENTE_DE.get(nombre, "Tibalt")
            if quien not in agentes:
                agentes.append(quien)

    texto = str(tramo[-1].content).strip() if tramo else ""

    # El jugador quiere venderle una carta a la tienda pero el modelo no abrió
    # el formulario: se abre igual, precargado con lo que se pudo leer del mensaje.
    if propuesta is None and propuestas.quiere_vender(consulta.texto):
        propuesta = propuestas.datos_desde_texto(consulta.texto)
        texto = propuestas.TEXTO_FORMULARIO
        if "Tibalt" not in agentes:
            agentes.append("Tibalt")

    if not texto:
        texto = "No obtuve una respuesta del agente para esa consulta. Probá reformulándola."

    return {
        "texto": texto,
        "herramientas": herramientas,
        # Si se abrió la planilla para vender, no se muestra la carta 3D de la
        # tienda: confunde (parece que se la estás comprando).
        "carta": cartas.buscar(ultimo_nombre) if ultimo_nombre and propuesta is None else None,
        # El agente pudo haber tocado el carrito: se devuelve cómo quedó
        # para que el front actualice el ícono sin otro pedido.
        "carrito": tienda.ver_carrito(consulta.thread_id),
        "pedido": pedido,
        "mazo": mazo,
        "catalogo": catalogo_pedido,
        "propuesta": propuesta,
        "agentes": agentes,
        "error": "",
    }
