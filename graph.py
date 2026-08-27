from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from agent_sales import agente_ventas  # Importamos la nueva función/wrapper
from tools import lista_tools

# 1. Definimos el Estado (la memoria del grafo)
class State(TypedDict):
    messages: Annotated[list, add_messages]

# 2. Inicializamos el grafo
grafo_urza = StateGraph(State)

# 3. Nodo principal: Acá va el nuevo código que inyecta el System Prompt
def nodo_ventas(state: State):
    respuesta = agente_ventas(state["messages"])
    return {"messages": [respuesta]}

# 4. Nodo secundario: Ejecución de las herramientas
nodo_tools = ToolNode(tools=lista_tools)

# 5. Agregamos los nodos al grafo
grafo_urza.add_node("Ventas", nodo_ventas)
grafo_urza.add_node("tools", nodo_tools)

# 6. Definimos las rutas (Edges)
grafo_urza.add_edge(START, "Ventas")
grafo_urza.add_conditional_edges("Ventas", tools_condition)
grafo_urza.add_edge("tools", "Ventas")

# 7. Compilamos el grafo con memoria a corto plazo
from langgraph.checkpoint.memory import MemorySaver
memoria = MemorySaver()
app_graph = grafo_urza.compile(checkpointer=memoria)