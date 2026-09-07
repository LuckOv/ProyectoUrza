"""API HTTP de URZA.

Expone el agente para que lo consuma cualquier frontend. Va en backend/,
al lado de graph.py.

Levantar con:
    .\\.venv\\Scripts\\python.exe -m uvicorn api:app --reload --port 8000
(parado dentro de la carpeta backend)

Probar que anda:  http://localhost:8000/salud
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

app = FastAPI(title="URZA API")

# Cualquier puerto de localhost: Vite salta del 5173 al 5174 si el primero
# está ocupado, y con una lista fija el navegador bloquearía el pedido por
# CORS. En producción esto se reemplaza por el dominio real.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


class Consulta(BaseModel):
    thread_id: str
    texto: str


# El grafo se importa perezosamente: si falta la GROQ_API_KEY, el error sale
# como respuesta JSON y no impide que la API levante.
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
def chat(consulta: Consulta):
    try:
        grafo = _obtener_grafo()
    except Exception as e:
        return {"texto": "", "herramientas": [], "error": f"No pude iniciar el agente: {e}"}

    config = {"configurable": {"thread_id": consulta.thread_id}}

    try:
        estado = grafo.invoke({"messages": [HumanMessage(content=consulta.texto)]}, config=config)
    except Exception as e:
        return {"texto": "", "herramientas": [], "error": f"Falló la consulta al agente: {e}"}

    mensajes = estado.get("messages", [])
    if not mensajes:
        return {"texto": "", "herramientas": [], "error": "El agente no devolvió ningún mensaje."}

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
    for m in tramo:
        for llamada in getattr(m, "tool_calls", None) or []:
            args_por_id[llamada.get("id")] = (llamada.get("name", ""), llamada.get("args", {}))
        if getattr(m, "type", "") == "tool":
            nombre, args = args_por_id.get(
                getattr(m, "tool_call_id", None),
                (getattr(m, "name", "herramienta"), {}),
            )
            herramientas.append({
                "nombre": nombre,
                "argumentos": args,
                "resultado": str(m.content),
            })

    texto = str(tramo[-1].content).strip() if tramo else ""
    if not texto:
        texto = "No obtuve una respuesta del agente para esa consulta. Probá reformulándola."

    return {"texto": texto, "herramientas": herramientas, "error": ""}
