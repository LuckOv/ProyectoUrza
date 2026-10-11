# Permite correrlo también como archivo suelto (python ingesta/x.py), además de
# con python -m: agrega backend/ al path para que encuentre los paquetes.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

modelos = client.models.list()
print("Modelos disponibles en tu cuenta de Groq:")
for model in modelos.data:
    print(f"- {model.id}")