"""URZA — vista del jugador.

Correr desde la carpeta del proyecto (la misma donde está inventario.csv):
    streamlit run app_usuario.py
"""

import html
import uuid

import streamlit as st

from urza_core import responder

st.set_page_config(page_title="URZA", layout="centered", initial_sidebar_state="collapsed")

MARRON_FONDO = "#C2A178"
PERGAMINO = "#E7D6B4"
PERGAMINO_CLARO = "#F7EEDC"
TINTA = "#2E211A"
MARCO = "#4A3222"
MARRON_MEDIO = "#6B4A2E"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@500;600&family=Spectral:ital,wght@0,400;0,600;1,400&display=swap');

.stApp {{ background-color: {MARRON_FONDO}; }}
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], footer {{ display: none; }}
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {{
    height: 100vh;
    max-height: 100vh;
    overflow: hidden !important;
}}
.block-container {{
    padding-top: 1.5rem;
    padding-bottom: 1rem;
    height: 100vh;
    max-height: 100vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}}
/* Toda la cadena de divs que envuelve al área de mensajes se vuelve columna
   flexible, así el scroll ocupa exactamente lo que sobra después del título,
   el formulario y el checkbox. Sin números mágicos. */
.block-container div:has(.urza-scroll) {{
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
}}

.st-key-urza_panel,
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div > .urza-ancla) {{
    background: {PERGAMINO};
    border: 2px solid {MARCO};
    border-radius: 6px;
    padding: 20px 28px 10px;
    box-shadow: 0 12px 30px rgba(46, 33, 26, .30);
}}

.urza-titulo {{
    font-family: 'Cinzel', Georgia, serif;
    font-size: 1.9rem;
    font-weight: 600;
    letter-spacing: .10em;
    color: #3B2717;
    margin: 0;
    line-height: 1.1;
}}
.urza-bajada {{
    font-family: 'Spectral', Georgia, serif;
    font-style: italic;
    font-size: .9rem;
    color: #6B5335;
    margin: 4px 0 14px;
}}
.urza-regla {{ border: 0; border-top: 1px solid #B79E77; margin: 0 0 14px; }}

.urza-scroll {{
    display: flex;
    flex-direction: column-reverse;
    flex: 1 1 auto;
    min-height: 80px;
    overflow-y: auto;
    padding: 2px 8px 2px 2px;
}}
.urza-scroll::-webkit-scrollbar {{ width: 8px; }}
.urza-scroll::-webkit-scrollbar-thumb {{ background: #B08F63; border-radius: 4px; }}
.urza-scroll::-webkit-scrollbar-track {{ background: transparent; }}

.urza-msg {{
    font-family: 'Spectral', Georgia, serif;
    font-size: .97rem;
    line-height: 1.6;
    max-width: 84%;
    padding: 10px 15px;
    margin: 5px 0;
    border-radius: 4px;
    white-space: pre-wrap;
    word-wrap: break-word;
}}
.urza-msg.jugador {{ margin-left: auto; background: {MARRON_MEDIO}; color: #F4E7CE; }}
.urza-msg.urza {{ margin-right: auto; background: {PERGAMINO_CLARO}; color: {TINTA}; border: 1px solid #D8C4A0; }}
.urza-msg.falla {{ margin-right: auto; background: #F3DED6; color: #6B2415; border: 1px solid #C99B8B; }}

.urza-traza {{
    font-family: 'Spectral', Georgia, serif;
    font-size: .78rem;
    font-style: italic;
    color: #7A6446;
    border-top: 1px solid #DCCBAA;
    margin-top: 8px;
    padding-top: 6px;
}}

.urza-vacio {{
    font-family: 'Spectral', Georgia, serif;
    font-style: italic;
    color: #7A6446;
    text-align: center;
    margin: auto;
    padding: 0 20px;
    font-size: .95rem;
}}

.urza-puntos::after {{ content: '.'; animation: urzapuntos 1.2s steps(4, end) infinite; }}
@keyframes urzapuntos {{ 0% {{ content: '.'; }} 33% {{ content: '..'; }} 66% {{ content: '...'; }} }}
@media (prefers-reduced-motion: reduce) {{ .urza-puntos::after {{ animation: none; content: '...'; }} }}

[data-testid="stForm"] {{ border: 0; padding: 0; }}
[data-testid="stTextInputRootElement"],
[data-testid="stForm"] div[data-baseweb="input"] {{
    background-color: {PERGAMINO_CLARO} !important;
    border: 1px solid {MARRON_MEDIO} !important;
    border-radius: 3px;
}}
[data-testid="stTextInputRootElement"]:focus-within,
[data-testid="stForm"] div[data-baseweb="input"]:focus-within {{ box-shadow: 0 0 0 2px #8C6A3F; }}
[data-testid="stTextInputField"],
[data-testid="stForm"] input {{
    background-color: transparent !important;
    color: {TINTA} !important;
    font-family: 'Spectral', Georgia, serif;
    font-size: 1rem;
}}
[data-testid="stTextInputField"]::placeholder,
[data-testid="stForm"] input::placeholder {{ color: #9C8564 !important; }}
[data-testid="stForm"] button {{
    background-color: {MARCO};
    color: #F1E4CA;
    border: 1px solid {TINTA};
    border-radius: 3px;
    font-family: 'Cinzel', Georgia, serif;
    letter-spacing: .05em;
}}
[data-testid="stForm"] button:hover {{ background-color: #5E4029; color: #FFF6E4; border-color: {TINTA}; }}
[data-testid="stForm"] button p {{ font-weight: 500; }}

.stButton button {{
    background: transparent;
    border: 1px solid #A98A5F;
    color: #4A3222;
    border-radius: 3px;
    font-family: 'Spectral', Georgia, serif;
    font-size: .82rem;
}}
.stButton button:hover {{ background: #D9C6A2; border-color: {MARCO}; color: {TINTA}; }}

[data-testid="stCheckbox"] label p, [data-testid="stCheckbox"] label span {{
    font-family: 'Spectral', Georgia, serif; font-size: .82rem; color: #6B5335;
}}

@media (max-width: 640px) {{
    .st-key-urza_panel {{ padding: 18px 16px 8px; }}
    .urza-titulo {{ font-size: 1.7rem; }}
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# --- estado de la sesión -----------------------------------------------------
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "historial" not in st.session_state:
    st.session_state.historial = []          # [{"rol", "texto", "traza"}]
if "pendiente" not in st.session_state:
    st.session_state.pendiente = None


def encolar(texto: str):
    st.session_state.pendiente = texto
    st.rerun()


# --- armado del HTML de la conversación --------------------------------------
def burbuja(rol: str, texto: str, traza: str = "") -> str:
    clase = {"jugador": "jugador", "urza": "urza", "falla": "falla"}[rol]
    cuerpo = html.escape(texto)
    extra = f'<div class="urza-traza">{html.escape(traza)}</div>' if traza else ""
    return f'<div class="urza-msg {clase}">{cuerpo}{extra}</div>'


def conversacion_html(mostrar_traza: bool) -> str:
    piezas = []
    for m in st.session_state.historial:
        traza = m.get("traza", "") if mostrar_traza else ""
        piezas.append(burbuja(m["rol"], m["texto"], traza))

    if st.session_state.pendiente:
        piezas.append(burbuja("jugador", st.session_state.pendiente))
        piezas.append('<div class="urza-msg urza"><span class="urza-puntos">Urza está buscando</span></div>')

    apertura = '<div class="urza-scroll">'

    if not piezas:
        return (apertura + '<div class="urza-vacio">'
                'Preguntá por una carta y te digo si está en la tienda y a cuánto.'
                '</div></div>')

    # column-reverse: invertimos el orden para que el último quede abajo y a la vista.
    return apertura + "".join(reversed(piezas)) + "</div>"


# --- interfaz ----------------------------------------------------------------
try:
    panel = st.container(border=True, key="urza_panel")
except TypeError:                      # Streamlit < 1.43 no acepta key acá
    panel = st.container(border=True)

hay_sugerencias = not st.session_state.historial and not st.session_state.pendiente

with panel:
    mostrar_traza = st.session_state.get("ver_traza", False)
    st.markdown(
        '<span class="urza-ancla"></span>'
        '<h1 class="urza-titulo">URZA</h1>'
        '<p class="urza-bajada">Tienda y consultas de Magic: The Gathering</p>'
        '<hr class="urza-regla">'
        + conversacion_html(mostrar_traza),
        unsafe_allow_html=True,
    )

    with st.form("consulta", clear_on_submit=True, border=False):
        col_texto, col_boton = st.columns([5, 1.4])
        entrada = col_texto.text_input(
            "Consulta",
            placeholder="¿Tenés Heartfire Hero?",
            label_visibility="collapsed",
        )
        enviado = col_boton.form_submit_button("Preguntar", use_container_width=True)

    if hay_sugerencias:
        sugerencias = ["¿Tenés Cavern of Souls?", "Precio de Llanowar Elves", "¿Queda Twinflame Tyrant?"]
        for columna, texto in zip(st.columns(3), sugerencias):
            if columna.button(texto, key=f"sug_{texto}", use_container_width=True):
                encolar(texto)

    st.checkbox("Mostrar qué herramientas usó", key="ver_traza")

if enviado and entrada.strip() and not st.session_state.pendiente:
    encolar(entrada.strip())


# --- procesamiento del turno pendiente ---------------------------------------
if st.session_state.pendiente:
    consulta = st.session_state.pendiente
    resultado = responder(st.session_state.thread_id, consulta)

    st.session_state.historial.append({"rol": "jugador", "texto": consulta, "traza": ""})

    if resultado.error:
        st.session_state.historial.append({"rol": "falla", "texto": resultado.error, "traza": ""})
    else:
        traza = " · ".join(
            f"{p.nombre}({', '.join(str(v) for v in p.argumentos.values())})"
            for p in resultado.herramientas
        )
        st.session_state.historial.append({"rol": "urza", "texto": resultado.texto, "traza": traza})

    st.session_state.pendiente = None
    st.rerun()
