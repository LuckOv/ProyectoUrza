"""ChatGroq falso para las pruebas.

- Responde según un GUION que arma cada prueba (texto o llamadas a herramientas).
- Valida el historial como la API real de Groq/OpenAI: si un mensaje del
  asistente pidió herramientas, cada pedido tiene que tener su respuesta
  (ToolMessage) justo después. Si no, levanta el mismo tipo de error que Groq.
- Registra lo que recibió en cada llamada, para poder revisarlo.
"""
import itertools

from langchain_core.messages import AIMessage

GUION = []          # cola de respuestas: str | dict(tool) | list[dict] | Exception
CEREBRO = None      # si no hay guion: función(mensajes) -> lo mismo que un paso del guion
LLAMADAS = []       # lo que recibió en cada invoke
_ids = itertools.count()


class BadRequestError(Exception):
    pass


def _validar(mensajes):
    pendientes = set()
    for m in mensajes:
        if m.type == "tool":
            if m.tool_call_id not in pendientes:
                raise BadRequestError(f"tool message sin pedido previo: {m.tool_call_id}")
            pendientes.discard(m.tool_call_id)
            continue
        if pendientes:
            raise BadRequestError(
                "Error code: 400 - 'tool_calls' must be followed by tool messages responding to each 'tool_call_id'"
            )
        if m.type == "ai":
            for tc in getattr(m, "tool_calls", None) or []:
                pendientes.add(tc["id"])
    if pendientes:
        raise BadRequestError("tool_calls sin responder al final del historial")


class ChatGroq:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def bind_tools(self, tools):
        return self

    def invoke(self, mensajes):
        mensajes = list(mensajes)
        _validar(mensajes)
        LLAMADAS.append(mensajes)
        if not GUION:
            if CEREBRO is None:
                return AIMessage("(sin guion)")
            paso = CEREBRO(mensajes)
        else:
            paso = GUION.pop(0)
        if isinstance(paso, Exception):
            raise paso
        if callable(paso):
            paso = paso(mensajes)
        if isinstance(paso, str):
            return AIMessage(paso)
        llamadas = paso if isinstance(paso, list) else [paso]
        return AIMessage("", tool_calls=[
            {"name": c["name"], "args": c.get("args", {}), "id": f"call_{next(_ids)}"} for c in llamadas
        ])
