"""Capa de servicio de URZA.

Vive en frontend/ y es el único punto donde el frontend conoce al backend.
La interfaz (Streamlit hoy, lo que venga mañana) le pasa un thread_id y un
texto, y recibe una Respuesta. Si algún día esto pasa a React + FastAPI,
responder() se expone como endpoint y la lógica del agente no se toca.

Estructura que espera:
    proyecto/
      backend/   agent_sales.py  graph.py  tools.py  inventario.csv  .env
      frontend/  app_usuario.py  urza_core.py
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.messages import HumanMessage

# El backend es una carpeta hermana, no un paquete instalado: lo agregamos
# al path para poder importar graph.py. Es la única línea de acoplamiento
# entre las dos carpetas; si mañana el backend pasa a ser un servicio HTTP,
# se borra esto y se cambia el invoke de abajo por un requests.post.
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


@dataclass
class PasoHerramienta:
    """Una llamada a herramienta que hizo el agente, con su resultado."""
    nombre: str
    argumentos: dict
    resultado: str


@dataclass
class Respuesta:
    texto: str = ""
    herramientas: list = field(default_factory=list)
    error: str = ""


# El grafo se importa perezosamente: así la UI puede levantar y mostrar un
# error prolijo si falta la GROQ_API_KEY, en vez de reventar en el import.
_grafo = None


def _obtener_grafo():
    global _grafo
    if _grafo is None:
        if not _BACKEND.is_dir():
            raise FileNotFoundError(f"No encuentro la carpeta backend en {_BACKEND}")
        from graph import app_graph
        _grafo = app_graph
    return _grafo


def responder(thread_id: str, texto: str) -> Respuesta:
    """Manda una consulta al agente y devuelve su respuesta final.

    El historial lo mantiene el checkpointer del grafo, indexado por thread_id,
    así que acá solo se envía el mensaje nuevo.
    """
    try:
        grafo = _obtener_grafo()
    except Exception as e:
        return Respuesta(error=f"No pude iniciar el agente: {e}")

    config = {"configurable": {"thread_id": thread_id}}

    try:
        estado = grafo.invoke({"messages": [HumanMessage(content=texto)]}, config=config)
    except Exception as e:
        return Respuesta(error=f"Falló la consulta al agente: {e}")

    mensajes = estado.get("messages", [])
    if not mensajes:
        return Respuesta(error="El agente no devolvió ningún mensaje.")

    # Nos quedamos con el tramo posterior al último mensaje del usuario:
    # ahí están las llamadas a herramientas y la respuesta final de este turno.
    corte = 0
    for i in range(len(mensajes) - 1, -1, -1):
        if getattr(mensajes[i], "type", "") == "human":
            corte = i
            break
    tramo = mensajes[corte + 1:]

    pasos = []
    args_por_id = {}
    for m in tramo:
        for llamada in getattr(m, "tool_calls", None) or []:
            args_por_id[llamada.get("id")] = (llamada.get("name", ""), llamada.get("args", {}))
        if getattr(m, "type", "") == "tool":
            nombre, args = args_por_id.get(
                getattr(m, "tool_call_id", None),
                (getattr(m, "name", "herramienta"), {}),
            )
            pasos.append(PasoHerramienta(nombre=nombre, argumentos=args, resultado=str(m.content)))

    final = str(tramo[-1].content).strip() if tramo else ""
    if not final:
        final = "No obtuve una respuesta del agente para esa consulta. Probá reformulándola."

    return Respuesta(texto=final, herramientas=pasos)
