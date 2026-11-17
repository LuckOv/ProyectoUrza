# Guía de Comandos: Levantar URZA (Backend, Frontend y Servicios)

Este documento reúne todos los comandos necesarios para poner en marcha el proyecto localmente tanto en Windows (PowerShell) como en Linux/macOS.

---

## 🚀 Inicio Rápido (Servicios Principales)

Para utilizar URZA necesitás **dos terminales abiertas**: una para el Backend (Django) y otra para el Frontend (Vite).

### Terminal 1: Backend (Django en puerto 8000)

> [!IMPORTANT]
> El backend **siempre** debe ejecutarse parado dentro de la carpeta `backend/` para que encuentre la base SQLite `urza.db` y las variables de entorno de `.env`.

**En Windows (PowerShell):**
```powershell
cd backend
..\.venv\Scripts\python.exe manage.py runserver 8000
```

*(Alternativa usando `uv`:)*
```powershell
cd backend
uv run python manage.py runserver 8000
```

**En Linux / macOS:**
```bash
cd backend
../.venv/bin/python manage.py runserver 8000
```

* **Estado de la API:** [http://localhost:8000/salud](http://localhost:8000/salud) (debe devolver `{"ok": true}`)
* **Documentación interactiva (Swagger / OpenAPI):** [http://localhost:8000/docs](http://localhost:8000/docs)
* **Panel Django Admin:** [http://localhost:8000/admin/](http://localhost:8000/admin/) (Usuario: `admin` | Clave: `urza123`)
* **Bot de Telegram:** ¡Se inicia **automáticamente en segundo plano** al levantar el backend! En cuanto esté operativo, recibirás un mensaje de confirmación `🟢 URZA ONLINE` en tu Telegram personal.

---

### Terminal 2: Frontend (React 19 + Vite en puerto 5173)

**En cualquier sistema:**
```powershell
cd frontend
npm run dev
```

* **Tienda y Chat con Urza:** [http://localhost:5173/](http://localhost:5173/)
* **Panel del Vendedor (Mesa Central):** [http://localhost:5173/vendedor.html](http://localhost:5173/vendedor.html) (Clave por defecto: `urza`)
* **Acceso desde el celular o red local:** Abrí la dirección "Network" que imprime Vite en la terminal (ej. `http://192.168.1.X:5173/`).

---

## 🤖 Bot de Telegram (@UrzaTiendaBot)

### Inicio automático
Al tener `TELEGRAM_BOT_TOKEN` configurado en `backend/.env`, el bot arranca solo al iniciar el backend (Terminal 1). En cuanto esté conectado a Telegram:
1. Te enviará un mensaje automático a tu chat personal:
   > 🟢 **URZA ONLINE** (@UrzaTiendaBot)
   > *El asistente de la tienda y bot de Telegram ya está operativo y escuchando en tu PC local.*
2. Podés enviarle **/ping** en cualquier momento para comprobar que responde.
3. Si detenés el backend (Ctrl+C), te enviará:
   > 🔴 **URZA DESCONECTADO**

### Inicio manual en terminal separada (Opcional para depurar)
Si preferís ver los logs detallados del bot en su propia ventana:
```powershell
cd backend
..\.venv\Scripts\python.exe -u manage.py run_telegram_bot
```
```

*(O con `uv`:)*
```powershell
cd backend
uv run python manage.py run_telegram_bot
```

---

## 📦 Instalación y Configuración Inicial (Primera Vez)

Si clonás el repositorio o se reinstalan dependencias:

### 1. Entorno virtual y dependencias Python (con `uv`)
```powershell
uv sync
```

### 2. Dependencias del Frontend (Node / npm)
```powershell
cd frontend
npm install
cd ..
```

### 3. Archivo de credenciales (`backend/.env`)
Copiá el archivo de ejemplo y completá tus claves:
```powershell
copy backend\.env.example backend\.env
```
Asegurate de definir como mínimo:
```env
GROQ_API_KEY=tu_clave_de_groq
GEMINI_API_KEY=tu_clave_de_gemini
VENDEDOR_CLAVE=urza
```

---

## 📚 Ingesta de Bases RAG (Bases Vectoriales Chroma)

Las bases vectoriales son locales (no se suben a Git). Podés instalarlas desde el panel del vendedor (**Configuración → Bases del bot**) o manualmente por consola:

```powershell
# 1. Base de Reglas Completas (Ajani)
cd backend
uv run python -m ingesta.ingestar_reglas

# 2. Base de Teoría y Armado de Mazos (Saheeli)
cd backend
uv run python -m ingesta.ingestar_mazos

# 3. Base de Lore e Historia de MTG Wiki (Teferi)
cd backend
uv run python -m ingesta.ingestar_lore
```
*(Nota: Para reconstruir cualquiera desde cero, agregá `--rebuild` al final del comando).*

---

## 🧪 Pruebas Automáticas

Para correr la suite completa de pruebas unitarias y de integración (117 tests sin necesidad de internet ni gastar cuota de API):

```powershell
cd backend
uv run --with pytest python -m pytest tests -q
```
