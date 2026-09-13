r"""API HTTP de URZA.

Va en backend/, al lado de graph.py.

Levantar con:
    ..\.venv\Scripts\python.exe -m uvicorn api:app --reload --port 8000
(parado dentro de la carpeta backend)

Probar que anda:          http://localhost:8000/salud
Ver todos los endpoints:  http://localhost:8000/docs
"""

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

import cartas
import tienda

app = FastAPI(title="URZA API")
tienda.preparar()

# Cualquier puerto de localhost: Vite salta del 5173 al 5174 si el primero
# está ocupado, y con una lista fija el navegador bloquearía el pedido por
# CORS. En producción esto se reemplaza por el dominio real.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- modelos de entrada ------------------------------------------------------

class Credenciales(BaseModel):
    usuario: str
    clave: str


class Consulta(BaseModel):
    thread_id: str
    texto: str


class ItemCarrito(BaseModel):
    nombre: str
    edicion: str | None = None
    precio: float | None = None
    imagen: str | None = None
    cantidad: int = 1


# --- autenticación -----------------------------------------------------------

def _token(authorization):
    if not authorization or not authorization.lower().startswith("bearer "):
        return ""
    return authorization[7:].strip()


def sesion_opcional(authorization: str | None = Header(default=None)):
    """Para endpoints que funcionan con o sin usuario, como el chat."""
    return tienda.quien_es(_token(authorization))


def sesion_requerida(authorization: str | None = Header(default=None)):
    """Para todo lo que toca el carrito: sin usuario no se pasa."""
    usuario = tienda.quien_es(_token(authorization))
    if not usuario:
        raise HTTPException(status_code=401, detail="Necesitás iniciar sesión para esto.")
    return usuario


@app.post("/registro")
def registro(datos: Credenciales):
    try:
        usuario = tienda.registrar(datos.usuario, datos.clave)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"token": tienda.abrir_sesion(usuario["id"]), "usuario": usuario["usuario"]}


@app.post("/login")
def login(datos: Credenciales):
    try:
        usuario = tienda.verificar(datos.usuario, datos.clave)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return {"token": tienda.abrir_sesion(usuario["id"]), "usuario": usuario["usuario"]}


@app.post("/logout")
def logout(authorization: str | None = Header(default=None)):
    tienda.cerrar_sesion(_token(authorization))
    return {"ok": True}


@app.get("/yo")
def yo(usuario=Depends(sesion_requerida)):
    return {"usuario": usuario["usuario"]}


# --- carrito -----------------------------------------------------------------

@app.get("/carrito")
def ver_carrito(usuario=Depends(sesion_requerida)):
    return {"items": tienda.ver_carrito(usuario["id"])}


@app.post("/carrito")
def agregar_al_carrito(item: ItemCarrito, usuario=Depends(sesion_requerida)):
    # El tope lo pone el inventario, no el botón: alguien podría pegarle al
    # endpoint directo y pedir cien copias de algo que tenemos dos veces.
    disponibles, _ = cartas.stock_de(item.nombre)
    if disponibles is None:
        raise HTTPException(status_code=404, detail=f"'{item.nombre}' no figura en el inventario.")
    if disponibles == 0:
        raise HTTPException(status_code=409, detail=f"No queda stock de '{item.nombre}'.")

    ya_lleva = sum(
        i["cantidad"] for i in tienda.ver_carrito(usuario["id"])
        if i["nombre"].lower() == item.nombre.lower()
    )
    if ya_lleva + item.cantidad > disponibles:
        raise HTTPException(
            status_code=409,
            detail=f"Sólo quedan {disponibles} de '{item.nombre}' y ya tenés {ya_lleva} en el carrito.",
        )

    items = tienda.agregar(
        usuario["id"], item.nombre, item.edicion, item.precio, item.imagen, item.cantidad
    )
    return {"items": items}


@app.delete("/carrito/{item_id}")
def quitar_del_carrito(item_id: int, usuario=Depends(sesion_requerida)):
    return {"items": tienda.quitar(usuario["id"], item_id)}


@app.delete("/carrito")
def vaciar_carrito(usuario=Depends(sesion_requerida)):
    return {"items": tienda.vaciar(usuario["id"])}


# --- cartas ------------------------------------------------------------------

@app.get("/carta")
def carta(nombre: str):
    encontrada = cartas.buscar(nombre)
    if not encontrada:
        raise HTTPException(status_code=404, detail=f"No encontré la carta '{nombre}'.")
    return encontrada


# --- chat --------------------------------------------------------------------

_grafo = None


def _obtener_grafo():
    global _grafo
    if _grafo is None:
        from graph import app_graph
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
def chat(consulta: Consulta, usuario=Depends(sesion_opcional)):
    vacia = {"texto": "", "herramientas": [], "carta": None, "usuario": None}

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

    for m in tramo:
        for llamada in getattr(m, "tool_calls", None) or []:
            args_por_id[llamada.get("id")] = (llamada.get("name", ""), llamada.get("args", {}))
        if getattr(m, "type", "") == "tool":
            nombre, args = args_por_id.get(
                getattr(m, "tool_call_id", None),
                (getattr(m, "name", "herramienta"), {}),
            )
            herramientas.append({"nombre": nombre, "argumentos": args, "resultado": str(m.content)})
            # De qué carta habló el agente. Sale de los argumentos con que
            # llamó a la herramienta, así no hay que adivinarlo del texto.
            if isinstance(args, dict) and args.get("nombre_carta"):
                ultimo_nombre = args["nombre_carta"]

    texto = str(tramo[-1].content).strip() if tramo else ""
    if not texto:
        texto = "No obtuve una respuesta del agente para esa consulta. Probá reformulándola."

    return {
        "texto": texto,
        "herramientas": herramientas,
        "carta": cartas.buscar(ultimo_nombre) if ultimo_nombre else None,
        "usuario": usuario["usuario"] if usuario else None,
        "error": "",
    }
