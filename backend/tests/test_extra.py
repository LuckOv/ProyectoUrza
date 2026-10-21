"""Casos de borde de los arreglos: doble clic, dólar vencido, charlas ya trabadas, conexiones."""
import gc
import threading
import time
import warnings
from datetime import timedelta

from langchain_core.messages import AIMessage, HumanMessage

from conftest import CLAVE, alta, id_de
import red
from tienda import base, tienda


def proximo(dia):
    hoy = base.ahora().date()
    for n in range(1, 8):
        d = hoy + timedelta(days=n)
        if base.DIAS[d.weekday()] == dia:
            return d.isoformat()


def test_doble_clic_en_confirmar_no_duplica_el_pedido(cliente):
    a = alta(cliente, "Get Lost", cantidad=5, precio=2)
    cliente.post("/carrito/dc", json={"inventario_id": a["id"], "cantidad": 2})
    ok, err = [], []

    def confirmar():
        try:
            ok.append(tienda.confirmar_pedido("dc", "Ana", "P", proximo("mar"), "12:00"))
        except ValueError as e:
            err.append(str(e))

    hilos = [threading.Thread(target=confirmar) for _ in range(5)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert len(ok) == 1 and all("vacío" in e for e in err), (len(ok), err)
    inv = cliente.get("/vendedor/inventario", headers=CLAVE).json()["items"]
    assert inv[0]["cantidad"] == 3


def test_confirmar_con_dolar_automatico_vencido_no_se_cuelga(cliente):
    """El dólar en automático se refresca (y se guarda) al calcular precios: no puede trabar la confirmación."""
    a = alta(cliente, "Get Lost", cantidad=5, precio=2)
    base.guardar_config("dolar", {"modo": "auto", "casa": "blue", "valor": 1000.0,
                                  "actualizado": (base.ahora() - timedelta(hours=3)).isoformat()})
    cliente.post("/carrito/dv", json={"inventario_id": a["id"], "cantidad": 1})
    from tienda import inventario
    inventario._ultimo_intento["cuando"] = 0.0
    t0 = time.time()
    p = tienda.confirmar_pedido("dv", "Ana", "P", proximo("mar"), "12:00")
    assert time.time() - t0 < 3, "la confirmación tardó: se trabó esperando la base"
    assert p["total"] == 3000          # 2 US$ × dólar nuevo 1500
    # y con dolarapi caído también confirma, con el último valor
    base.guardar_config("dolar", {"modo": "auto", "casa": "blue", "valor": 1200.0,
                                  "actualizado": (base.ahora() - timedelta(hours=3)).isoformat()})
    inventario._ultimo_intento["cuando"] = 0.0
    red.RED["modo"] = "caida"
    cliente.post("/carrito/dv", json={"inventario_id": a["id"], "cantidad": 1})
    t0 = time.time()
    p = tienda.confirmar_pedido("dv", "Ana", "P", proximo("mar"), "12:00")
    assert time.time() - t0 < 3 and p["total"] == 2400


def test_charla_que_ya_venia_trabada_se_recupera(cliente, guion):
    """Una charla que quedó trabada con la versión anterior (pedido de herramienta sin respuesta) vuelve a andar."""
    import api
    grafo = api._obtener_grafo()
    config = {"configurable": {"thread_id": "trabada"}}
    grafo.update_state(config, {"messages": [
        HumanMessage("Precio de Llanowar Elves"),
        AIMessage("", tool_calls=[{"name": "consultar_precio_cardmarket", "args": {"nombre_carta": "x"}, "id": "viejo1"}]),
    ]}, as_node="Ventas")
    guion += ["¡Hola de nuevo!"]
    r = cliente.post("/chat", json={"thread_id": "trabada", "texto": "hola"}).json()
    assert r["error"] == "" and r["texto"] == "¡Hola de nuevo!", r


def test_historial_recortado_es_valido_con_herramientas(cliente, guion, llamadas):
    alta(cliente, "Get Lost", cantidad=5, precio=2)
    for i in range(25):
        guion += [{"name": "consultar_stock_local", "args": {"nombre_carta": "Get Lost"}}, f"tenemos {i}"]
        r = cliente.post("/chat", json={"thread_id": "larga", "texto": f"¿tenés Get Lost? {i}"}).json()
        assert r["error"] == "", r["error"]
    ultima = llamadas[-1]
    assert len(ultima) <= 31 and ultima[1].type == "human"   # sistema + desde un mensaje del jugador


def test_texto_vacio_o_gigante(cliente):
    assert cliente.post("/chat", json={"thread_id": "x", "texto": ""}).status_code == 422
    assert cliente.post("/chat", json={"thread_id": "", "texto": "hola"}).status_code == 422
    assert cliente.post("/chat", json={"thread_id": "x", "texto": "a" * 5000}).status_code == 422


def test_no_quedan_conexiones_abiertas(cliente):
    a = alta(cliente, "Get Lost", cantidad=5, precio=2)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", ResourceWarning)
        for _ in range(20):
            cliente.get("/vendedor/inventario", headers=CLAVE)
            cliente.post("/carrito/rw", json={"inventario_id": a["id"], "cantidad": 1})
            cliente.delete("/carrito/rw")
        gc.collect()
    abiertas = [x for x in w if issubclass(x.category, ResourceWarning) and "sqlite" in str(x.message).lower()]
    assert not abiertas, f"{len(abiertas)} conexiones a la base quedaron sin cerrar"


def test_editar_grado_sin_duplicar_y_mensaje(cliente):
    a = alta(cliente, "Blind Seer", cantidad=1)
    alta(cliente, "Blind Seer", grado="PSA 9", cantidad=1)
    r = cliente.patch(f"/vendedor/inventario/{a['id']}", headers=CLAVE, json={"grado": "PSA 9"})
    assert r.status_code == 400 and "Ya tenés Blind Seer" in r.json()["detail"]
    r = cliente.patch(f"/vendedor/inventario/{a['id']}", headers=CLAVE, json={"grado": "PSA 8"})
    assert r.status_code == 200 and r.json()["grado"] == "PSA 8"


def test_propuesta_aceptada_sin_cargar_se_puede_cargar_despues(cliente):
    p = cliente.post("/propuestas", json={"nombre": "A", "apellido": "B", "email": "a@b.com", "grado": "Sin graduar",
                                          "cantidad": 2, "precio": 10, "scryfall_id": id_de("Get Lost")}).json()
    cliente.patch(f"/vendedor/propuestas/{p['id']}", headers=CLAVE, json={"estado": "aceptada"})
    r = cliente.post(f"/vendedor/propuestas/{p['id']}/al-inventario", headers=CLAVE, json={"precio_usd": 3})
    assert r.status_code == 200 and r.json()["cantidad"] == 2
    lista = cliente.get("/vendedor/propuestas", headers=CLAVE).json()["propuestas"]
    assert lista[0]["cargada"] == 1


def test_propuesta_si_falla_el_alta_no_queda_marcada(cliente):
    p = cliente.post("/propuestas", json={"nombre": "A", "apellido": "B", "email": "a@b.com", "grado": "Sin graduar",
                                          "cantidad": 1, "precio": 10, "scryfall_id": id_de("Get Lost")}).json()
    red.RED["modo"] = "caida"      # el alta necesita Scryfall
    r = cliente.post(f"/vendedor/propuestas/{p['id']}/al-inventario", headers=CLAVE, json={"precio_usd": 3})
    assert r.status_code == 400
    red.RED["modo"] = "ok"
    r = cliente.post(f"/vendedor/propuestas/{p['id']}/al-inventario", headers=CLAVE, json={"precio_usd": 3})
    assert r.status_code == 200, r.text


def test_pedido_manual_con_carta_sin_precio(cliente):
    sp = alta(cliente, "Sin Precio", cantidad=3)
    r = cliente.post("/vendedor/pedidos", headers=CLAVE, json={
        "nombre": "A", "apellido": "B", "fecha_retiro": proximo("mar"), "hora_retiro": "12:00",
        "items": [{"inventario_id": sp["id"], "cantidad": 1}]})
    assert r.status_code == 409 and "precio" in r.json()["detail"]
    assert cliente.get("/vendedor/inventario", headers=CLAVE).json()["items"][0]["cantidad"] == 3


def test_csv_viejo_guardado_desde_excel(cliente):
    """Excel guarda el CSV con BOM: igual tiene que importarse."""
    from tienda import inventario
    base.guardar_config("csv_importado", False)
    base.CSV_VIEJO.write_bytes("﻿Carta,Edición,Cantidad\r\nGet Lost,The Lost Caverns of Ixalan (LCI),2\r\n".encode("utf-8"))
    try:
        assert inventario.importar_csv_viejo() == 1
        fila = inventario.listar()[0]
        assert fila["nombre"] == "Get Lost" and fila["set_codigo"] == "LCI" and fila["cantidad"] == 2
    finally:
        base.CSV_VIEJO.unlink()


def test_mail_raro_en_propuesta(cliente):
    for mail in ("a@b.com?cc=otro@x.com", "a@b.c", "a b@c.com", "a@b..com"):
        r = cliente.post("/propuestas", json={"nombre": "A", "apellido": "B", "email": mail, "grado": "Sin graduar",
                                              "cantidad": 1, "precio": 10, "scryfall_id": id_de("Get Lost")})
        assert r.status_code == 400, mail


def test_claves_malas_no_bloquean(cliente):
    """Si cambiás la clave con el panel abierto, la pestaña vieja manda muchas claves malas: no te bloquea."""
    for _ in range(20):
        assert cliente.get("/vendedor/inventario", headers={"X-Vendedor-Clave": "vieja"}).status_code == 401
    assert cliente.post("/vendedor/entrar", json={"clave": "clave-test"}).status_code == 200
