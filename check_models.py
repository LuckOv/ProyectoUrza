import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

modelos = client.models.list()
print("Modelos disponibles en tu cuenta de Groq:")
for model in modelos.data:
    print(f"- {model.id}")