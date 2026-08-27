import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage
from tools import lista_tools

load_dotenv()

llm = ChatGroq(model="qwen/qwen3.8-27b", temperature=0)
agente_ventas_base = llm.bind_tools(lista_tools)

# Prompt del sistema para guiar la conducta del agente y el uso de herramientas
SYSTEM_PROMPT = SystemMessage(content="""
Eres el Agente de Ventas de la tienda de Magic: The Gathering, liderado por Urza.
Tu objetivo es ayudar a los jugadores a consultar stock e información de precios.

REGLAS PARA EL USO DE HERRAMIENTAS:
1. Para consultar el stock local o el precio en CardMarket, usa SIEMPRE solo el nombre en inglés de la carta.
2. NUNCA incluyas la edición, set o código entre paréntesis en el argumento del nombre (Ejemplo CORRECTO: 'Heartfire Hero', Ejemplo INCORRECTO: 'Heartfire Hero (BLB)').
3. Si el usuario confirma o dice 'sí' a una pregunta anterior, recupera el nombre de la carta del historial de la conversación.
""")

def agente_ventas(messages):
    # Inyectamos el prompt del sistema al principio de la lista de mensajes
    messages_con_sistema = [SYSTEM_PROMPT] + messages
    return agente_ventas_base.invoke(messages_con_sistema)