"""El chat de punta a punta, con un Groq falso que sigue un guion."""
from datetime import timedelta

from langchain_core.messages import AIMessage

from conftest import CLAVE, alta
import red
from tienda import base


def tool(_nombre, **args):
    return {"name": _nombre, "args": args}


def _hilo():
    """Un thread_id distinto por prueba (sin barras: va en la URL del carrito)."""
    import os
    import re
    return re.sub(r"[^A-Za-z0-9_-]", "-", os.environ.get("PYTEST_CURRENT_TEST", "h").split(" ")[0])


def chat(c, texto, hilo=None):
    r = c.post("/chat", json={"thread_id": hilo or _hilo(), "texto": texto})
    assert r.status_code == 200, r.text
    return r.json()


def proximo(dia):
    hoy = base.ahora().date()
    for n in range(1, 8):
        d = hoy + timedelta(days=n)
        if base.DIAS[d.weekday()] == dia:
            return d.isoformat()


def test_consulta_de_stock_muestra_carta(cliente, guion, llamadas):
    alta(cliente, "Heartfire Hero", cantidad=4, precio=1.5)
    guion += [tool("consultar_stock_local", nombre_carta="Heroe del fuego del corazon"), "Tenemos 4 a $1.500."]
    r = chat(cliente, "¿Tenés Héroe del fuego del corazón?")
    assert r["error"] == "" and r["texto"] == "Tenemos 4 a $1.500."
    assert r["agentes"] == ["Tibalt"]
    assert r["carta"]["nombre"] == "Heartfire Hero" and r["carta"]["en_stock"] == 4
    assert "Stock de 'Heartfire Hero': 4 unidades" in r["herramientas"][0]["resultado"]
    # el prompt del sistema trae la fecha de hoy y los horarios
    sistema = llamadas[0][0].content
    assert base.ahora().date().isoformat() in sistema and "domingo cerrado" in sistema


def test_compra_completa_por_chat(cliente, guion):
    a = alta(cliente, "Blind Seer", cantidad=2, precio=4)
    b = cliente.post(f"/vendedor/inventario/{a['id']}/variante", headers=CLAVE,
                     json={"grado": "PSA 10", "cantidad": 1, "precio_usd": 30}).json()
    guion += [tool("agregar_al_carrito", nombre_carta="Blind Seer", cantidad=1), "¿Cuál querés?"]
    r = chat(cliente, "Quiero comprar Blind Seer")
    assert "Hay 2 variantes" in r["herramientas"][0]["resultado"] and r["carrito"] == []
    guion += [tool("agregar_al_carrito", nombre_carta="Blind Seer", cantidad=1, variante_id=b["id"]), "Listo, ¿algo más?"]
    r = chat(cliente, "La PSA 10")
    assert len(r["carrito"]) == 1 and r["carrito"][0]["grado"] == "PSA 10"
    fecha = proximo("mar")
    guion += [tool("confirmar_compra", nombre="Ana", apellido="Pérez", fecha_retiro=fecha, hora_retiro="17:00"),
              "¡Listo! Pedido #1."]
    r = chat(cliente, "Soy Ana Pérez, paso el martes a las 5 de la tarde. Confirmo.")
    assert r["pedido"] and r["pedido"].startswith("Pedido #1 confirmado") and "17:00" in r["pedido"]
    assert r["carrito"] == []
    pedidos = cliente.get("/vendedor/pedidos", headers=CLAVE).json()["pedidos"]
    assert pedidos[0]["total"] == 30000 and pedidos[0]["origen"] == "chat"


def test_confirmar_en_domingo_explica(cliente, guion):
    a = alta(cliente, "Get Lost", cantidad=2, precio=2)
    cliente.post(f"/carrito/{_hilo()}", json={"inventario_id": a["id"]})
    guion += [tool("confirmar_compra", nombre="Ana", apellido="P", fecha_retiro=proximo("dom"), hora_retiro="12:00"), "Ese día cerramos."]
    r = chat(cliente, "Paso el domingo")
    assert r["pedido"] is None and "cerrada" in r["herramientas"][0]["resultado"]
    assert len(r["carrito"]) == 1


def test_falla_de_una_herramienta_no_traba_la_charla(cliente, guion):
    """Scryfall se cae en medio de una consulta: la charla tiene que poder seguir."""
    guion += [tool("consultar_precio_cardmarket", nombre_carta="Llanowar Elves"), "No pude consultar el precio."]
    red.RED["modo"] = "caida"
    r1 = chat(cliente, "Precio de Llanowar Elves")
    red.RED["modo"] = "ok"
    guion += ["¡Hola! ¿En qué te ayudo?"]
    r2 = chat(cliente, "hola")
    assert r2["error"] == "", f"la charla quedó trabada después de la falla: {r2['error'][:160]}"
    assert r2["texto"] == "¡Hola! ¿En qué te ayudo?"


def test_herramienta_con_scryfall_lento(cliente, guion):
    guion += [tool("consultar_precio_cardmarket", nombre_carta="Llanowar Elves"), "Ahora no puedo ver el precio."]
    red.RED["modo"] = "timeout"
    r = chat(cliente, "Precio de Llanowar Elves")
    assert r["error"] == "", r["error"][:200]


def test_groq_falla_y_la_siguiente_anda(cliente, guion):
    guion += [Exception("Error code: 429 - rate limit")]
    r = chat(cliente, "hola")
    assert "429" in r["error"]
    guion += ["Ahora sí."]
    r = chat(cliente, "hola de nuevo")
    assert r["error"] == "" and r["texto"] == "Ahora sí."


def test_groq_falla_despues_de_una_herramienta(cliente, guion):
    alta(cliente, "Get Lost", cantidad=2, precio=2)
    guion += [tool("consultar_stock_local", nombre_carta="Get Lost"), Exception("Error code: 429")]
    r = chat(cliente, "¿Tenés Get Lost?")
    assert r["error"]
    guion += ["Sí, tenemos 2."]
    r = chat(cliente, "¿Y entonces?")
    assert r["error"] == "", r["error"][:200]


def test_respuesta_con_razonamiento_qwen(cliente, guion):
    """Qwen3 puede mandar su razonamiento entre <think>…</think>: el jugador no tiene que verlo."""
    guion += ["<think>El usuario saluda, respondo corto.</think>\n\n¡Hola! ¿Qué carta buscás?"]
    r = chat(cliente, "hola")
    assert "<think>" not in r["texto"] and r["texto"] == "¡Hola! ¿Qué carta buscás?"


def test_mazo_devuelve_abanico(cliente, guion):
    alta(cliente, "Llanowar Elves", cantidad=5, precio=0.5)
    guion += [tool("sugerir_cartas_mazo", colores="verde", palabras_clave="elf"), "Te dejo las candidatas."]
    r = chat(cliente, "Armame un mazo verde de elfos")
    assert r["agentes"] == ["Saheeli"]
    nombres = [c["nombre"] for c in r["mazo"]]
    assert nombres[0] == "Llanowar Elves" and "Sin Precio" not in nombres
    assert "EN LA TIENDA: 5 u." in r["herramientas"][0]["resultado"]
    assert r["carta"] is None


def test_catalogo(cliente, guion):
    alta(cliente, "Get Lost", cantidad=2, precio=2)
    guion += [tool("listar_cartas_disponibles"), "Las cartas disponibles son…"]
    r = chat(cliente, "¿Qué cartas tenés?")
    assert r["catalogo"] is True and "1 cartas distintas" in r["herramientas"][0]["resultado"]


def test_propuesta_por_herramienta(cliente, guion):
    guion += [tool("iniciar_propuesta", carta="Blind Seer", grado="psa 9", precio=25000, nombre="Cori"), "Completá la planilla."]
    r = chat(cliente, "Tengo una Blind Seer PSA 9 a 25 mil")
    assert r["propuesta"]["grado"] == "PSA 9" and r["propuesta"]["nombre"] == "Cori"
    assert r["texto"] == "Completá la planilla." and r["carta"] is None


def test_propuesta_por_respaldo(cliente, guion):
    guion += ["No compramos cartas."]          # el modelo no llama a la herramienta
    r = chat(cliente, "Tengo una Blind Seer PSA 9 a $25.000")
    assert r["propuesta"]["carta"] == "Blind Seer" and "planilla" in r["texto"]


def test_respaldo_no_pisa_una_respuesta_de_reglas(cliente, guion):
    guion += [tool("consultar_reglas_mtg", pregunta="..."), "Ajani dice que sí, podés atacar."]
    r = chat(cliente, "Tengo 3 vidas y mi rival está a 5, ¿puedo atacar con todo?")
    assert r["propuesta"] is None and r["texto"] == "Ajani dice que sí, podés atacar."
    assert r["agentes"] == ["Ajani"]


def test_reglas_sin_base_avisa_comando_correcto(cliente, guion):
    guion += [tool("consultar_reglas_mtg", pregunta="¿Puedo responder?"), "..."]
    r = chat(cliente, "¿Puedo responder con un instante?")
    res = r["herramientas"][0]["resultado"]
    assert "ingesta.ingestar_reglas" in res, res
    guion += [tool("consultar_lore_mtg", pregunta="¿Quién es Urza?"), "..."]
    r = chat(cliente, "¿Quién es Urza?")
    assert "ingesta.ingestar_lore" in r["herramientas"][0]["resultado"]
    assert r["agentes"] == ["Teferi"]


def test_quitar_y_ver_carrito(cliente, guion):
    a = alta(cliente, "Get Lost", cantidad=2, precio=2)
    cliente.post(f"/carrito/{_hilo()}", json={"inventario_id": a["id"], "cantidad": 2})
    guion += [tool("ver_carrito"), "Llevás 2."]
    r = chat(cliente, "¿Qué llevo?")
    assert "Total: $4.000" in r["herramientas"][0]["resultado"]
    guion += [tool("quitar_del_carrito", nombre_carta="get lost"), "Listo."]
    r = chat(cliente, "Sacá el Get Lost")
    assert r["carrito"] == [] and r["carta"] is None


def test_argumentos_raros_del_modelo(cliente, guion):
    """El modelo a veces manda tipos raros: no tiene que romper la charla."""
    alta(cliente, "Get Lost", cantidad=2, precio=2)
    guion += [tool("agregar_al_carrito", nombre_carta="Get Lost", cantidad="dos"), "Perdón, ¿cuántas?"]
    r = chat(cliente, "Quiero dos Get Lost")
    assert r["error"] == "", r["error"][:200]
    guion += [tool("agregar_al_carrito", nombre_carta="Get Lost", cantidad=-2), "No se pudo."]
    r = chat(cliente, "Quiero menos dos")
    assert r["error"] == "" and r["carrito"] == []
    guion += [tool("agregar_al_carrito", nombre_carta="Get Lost", cantidad=1, variante_id=9999), "No existe."]
    r = chat(cliente, "La variante 9999")
    assert r["error"] == "" and "No existe la variante" in r["herramientas"][0]["resultado"]
    guion += [tool("confirmar_compra", nombre="Ana", apellido="P", fecha_retiro="el martes", hora_retiro="5pm"), "Decime la fecha."]
    r = chat(cliente, "el martes a las 5pm")
    assert r["error"] == "" and "no es válida" in r["herramientas"][0]["resultado"]


def test_historial_largo_se_recorta(cliente, guion, llamadas):
    """En una charla muy larga no se le manda todo el historial a Groq (el plan gratis tiene tope de tokens)."""
    for i in range(40):
        guion.append(f"respuesta {i}")
        chat(cliente, f"mensaje {i} " + "bla " * 50)
    enviados = len(llamadas[-1])
    assert enviados <= 30, f"en el turno 40 se mandaron {enviados} mensajes a Groq"
    assert llamadas[-1][0].type == "system"


def test_dos_herramientas_en_un_turno(cliente, guion):
    alta(cliente, "Get Lost", cantidad=2, precio=2)
    alta(cliente, "Heartfire Hero", cantidad=2, precio=1)
    guion += [[tool("consultar_stock_local", nombre_carta="Get Lost"), tool("consultar_stock_local", nombre_carta="Heartfire Hero")],
              "Tenemos las dos."]
    r = chat(cliente, "¿Tenés Get Lost y Heartfire Hero?")
    assert len(r["herramientas"]) == 2 and r["carta"]["nombre"] == "Heartfire Hero"
