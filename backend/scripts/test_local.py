# Permite correrlo también como archivo suelto (python ingesta/x.py), además de
# con python -m: agrega backend/ al path para que encuentre los paquetes.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from langchain_core.messages import HumanMessage
from agentes.graph import app_graph

print("\n" + "="*50)
print("🤖 Urza MVP (Agente de Ventas) - Entorno de Pruebas")
print("="*50)
print("Escribí 'salir' para terminar el chat.\n")

while True:
    user_input = input("👤 Jugador: ")
    
    if user_input.lower() in ['salir', 'exit', 'quit']:
        print("Cerrando sistema. ¡Éxitos en la corrección!")
        break
        
    inputs = {"messages": [HumanMessage(content=user_input)]}
    # Usamos un thread_id fijo para que el agente recuerde el contexto en esta sesión
    config = {"configurable": {"thread_id": "sesion_prueba_1"}}
    
    # Procesamos la respuesta a través de LangGraph
    for event in app_graph.stream(inputs, config=config, stream_mode="values"):
        mensaje_final = event["messages"][-1]
    
    print(f"🧙‍♂️ Urza: {mensaje_final.content}\n")