"""Inventario, precios, descuentos y alertas de precio."""
from conftest import CLAVE, alta, id_de
import red


def inv(c):
    r = c.get("/vendedor/inventario", headers=CLAVE)
    assert r.status_code == 200, r.text
    return r.json()


def test_alta_y_precio_en_pesos(cliente):
    item = alta(cliente, "Heartfire Hero", cantidad=4, precio=2.5)
    assert item["precio_usd"] == 2.5
    assert item["precio_ars"] == 2500          # dólar manual 1000
    assert item["sku"].startswith("URZ-")
    assert item["colores"] == "R"
    assert item["estado_stock"] == "ok"


def test_alta_sin_precio_usa_scryfall(cliente):
    item = alta(cliente, "Heartfire Hero", precio=None)
    assert item["precio_usd"] == 1.4


def test_alta_repetida_suma_unidades(cliente):
    a = alta(cliente, "Get Lost", cantidad=2)
    b = alta(cliente, "Get Lost", cantidad=3)
    assert a["id"] == b["id"] and b["cantidad"] == 5
    assert len(inv(cliente)["items"]) == 1


def test_alta_carta_doble_cara_trae_imagen_y_colores(cliente):
    item = alta(cliente, "Unholy Annex // Ritual Chamber")
    assert item["imagen"] and item["colores"] == "B"


def test_alta_validaciones(cliente):
    for cuerpo, esperado in [
        ({"scryfall_id": id_de("Get Lost"), "grado": "PSA 11"}, 400),
        ({"scryfall_id": id_de("Get Lost"), "cantidad": 0}, 400),
        ({"scryfall_id": id_de("Get Lost"), "precio_usd": -1}, 400),
        ({"scryfall_id": "00000000-0000-0000-0000-000000000000"}, 400),
    ]:
        r = cliente.post("/vendedor/inventario", headers=CLAVE, json=cuerpo)
        assert r.status_code == esperado, (cuerpo, r.text)


def test_otro_grado_misma_impresion(cliente):
    base_item = alta(cliente, "Blind Seer", cantidad=1, precio=4)
    r = cliente.post(f"/vendedor/inventario/{base_item['id']}/variante", headers=CLAVE,
                     json={"grado": "PSA 9", "cantidad": 2, "precio_usd": 12})
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["id"] != base_item["id"] and v["grado"] == "PSA 9" and v["scryfall_id"] == base_item["scryfall_id"]
    # repetir suma
    r = cliente.post(f"/vendedor/inventario/{base_item['id']}/variante", headers=CLAVE, json={"grado": "PSA 9", "cantidad": 1})
    assert r.json()["cantidad"] == 3


def test_editar_validaciones(cliente):
    item = alta(cliente, "Get Lost")
    url = f"/vendedor/inventario/{item['id']}"
    assert cliente.patch(url, headers=CLAVE, json={"cantidad": -1}).status_code == 400
    assert cliente.patch(url, headers=CLAVE, json={"precio_usd": -5}).status_code == 400
    assert cliente.patch(url, headers=CLAVE, json={"grado": "PSA 99"}).status_code == 400
    assert cliente.patch("/vendedor/inventario/9999", headers=CLAVE, json={"cantidad": 1}).status_code == 400
    r = cliente.patch(url, headers=CLAVE, json={"cantidad": 0})
    assert r.json()["estado_stock"] == "sin"


def test_editar_grado_a_uno_que_ya_existe_no_duplica(cliente):
    a = alta(cliente, "Blind Seer", grado="Sin graduar", cantidad=1)
    b = alta(cliente, "Blind Seer", grado="PSA 9", cantidad=1)
    r = cliente.patch(f"/vendedor/inventario/{a['id']}", headers=CLAVE, json={"grado": "PSA 9"})
    filas = [i for i in inv(cliente)["items"] if i["scryfall_id"] == a["scryfall_id"] and i["grado"] == "PSA 9"]
    assert len(filas) == 1, f"quedaron {len(filas)} filas de la misma carta en PSA 9 (status {r.status_code})"


def test_borrar(cliente):
    a = alta(cliente, "Get Lost")
    b = alta(cliente, "Heartfire Hero")
    r = cliente.post("/vendedor/inventario/borrar", headers=CLAVE, json={"ids": [a["id"], 9999]})
    assert r.json() == {"borradas": 1}
    assert [i["id"] for i in inv(cliente)["items"]] == [b["id"]]


def test_descuentos(cliente):
    a = alta(cliente, "Get Lost", precio=10)
    b = alta(cliente, "Heartfire Hero", precio=10)
    assert cliente.put("/vendedor/descuentos/general", headers=CLAVE, json={"porcentaje": 10}).status_code == 200
    assert cliente.post("/vendedor/descuentos", headers=CLAVE, json={"ids": [a["id"]], "porcentaje": 25}).status_code == 200
    items = {i["id"]: i for i in inv(cliente)["items"]}
    assert items[a["id"]]["descuento"] == 25 and items[a["id"]]["precio_ars"] == 7500   # gana el mayor
    assert items[b["id"]]["descuento"] == 10 and items[b["id"]]["precio_ars"] == 9000
    assert cliente.put("/vendedor/descuentos/general", headers=CLAVE, json={"porcentaje": 95}).status_code == 400
    assert cliente.put("/vendedor/descuentos/general", headers=CLAVE, json={"porcentaje": -1}).status_code == 400
    lista = cliente.get("/vendedor/descuentos", headers=CLAVE).json()
    did = lista["cartas"][0]["id"]
    assert cliente.delete(f"/vendedor/descuentos/{did}", headers=CLAVE).json()["cartas"] == []


def test_descuento_a_carta_inexistente_no_da_500(cliente):
    r = cliente.post("/vendedor/descuentos", headers=CLAVE, json={"ids": [4242], "porcentaje": 10})
    assert r.status_code in (200, 400), r.text


def test_borrar_carta_con_descuento_y_en_carrito(cliente):
    a = alta(cliente, "Get Lost", precio=10)
    cliente.post("/vendedor/descuentos", headers=CLAVE, json={"ids": [a["id"]], "porcentaje": 20})
    cliente.post("/carrito/t1", json={"inventario_id": a["id"], "cantidad": 1})
    r = cliente.post("/vendedor/inventario/borrar", headers=CLAVE, json={"ids": [a["id"]]})
    assert r.status_code == 200
    assert cliente.get("/carrito/t1").json()["items"] == []
    assert cliente.get("/vendedor/descuentos", headers=CLAVE).json()["cartas"] == []


def test_catalogo_solo_con_stock_y_precio(cliente):
    a = alta(cliente, "Get Lost", cantidad=2, precio=3)
    b = alta(cliente, "Heartfire Hero", cantidad=1, precio=1)
    cliente.patch(f"/vendedor/inventario/{b['id']}", headers=CLAVE, json={"cantidad": 0})
    sp = alta(cliente, "Sin Precio", cantidad=5)          # Scryfall sin precio y el vendedor no puso
    assert sp["precio_usd"] is None
    ids = [i["id"] for i in cliente.get("/catalogo").json()["items"]]
    assert ids == [a["id"]]


def test_alerta_precio_lejos_del_mercado(cliente):
    cara = alta(cliente, "Heartfire Hero", precio=1111111)   # como la que cargó Cori
    normal = alta(cliente, "Get Lost", precio=2.5)
    items = {i["id"]: i for i in inv(cliente)["items"]}
    assert items[cara["id"]]["alerta_tipo"] == "precio"
    assert items[cara["id"]]["sugerido_usd"] == 1.4
    assert not items[normal["id"]]["alerta_precio"]
    # Dejarlo así
    r = cliente.post(f"/vendedor/inventario/{cara['id']}/mantener-precio", headers=CLAVE)
    assert r.status_code == 200 and not r.json()["alerta_precio"]
    # Cambiar el precio vuelve a evaluar
    r = cliente.patch(f"/vendedor/inventario/{cara['id']}", headers=CLAVE, json={"precio_usd": 999})
    assert r.json()["alerta_tipo"] == "precio"
    # Poner el sugerido la apaga
    r = cliente.patch(f"/vendedor/inventario/{cara['id']}", headers=CLAVE, json={"precio_usd": 1.4})
    assert not r.json()["alerta_precio"]


def test_alerta_graduadas_umbral_doble(cliente):
    # Mercado 1.4 × multiplicador PSA 10 (3.0) = 4.2. 40% arriba no avisa (umbral 60%), 70% sí.
    a = alta(cliente, "Heartfire Hero", grado="PSA 10", precio=5.88)
    b = alta(cliente, "Get Lost", grado="PSA 10", precio=2.4 * 3 * 1.7)
    items = {i["id"]: i for i in inv(cliente)["items"]}
    assert items[a["id"]]["mercado_estimado"] and not items[a["id"]]["alerta_precio"]
    assert items[b["id"]]["alerta_tipo"] == "precio"


def test_alerta_mercado_se_movio(cliente):
    a = alta(cliente, "Cavern of Souls", precio=40)
    red.MOVIDAS["Cavern of Souls"] = 0.5
    assert cliente.post("/vendedor/mercado/actualizar", headers=CLAVE).json()["actualizadas"] == 1
    i = {x["id"]: x for x in inv(cliente)["items"]}[a["id"]]
    # el precio (40) ahora está 110% arriba del mercado (19): manda el aviso de precio
    assert i["alerta_tipo"] == "precio" and i["sugerido_usd"] == 19.0
    assert i["mercado_cambio_pct"] == -50.0
    alertas = cliente.get("/vendedor/alertas-precio", headers=CLAVE).json()
    assert [x["id"] for x in alertas["items"]] == [a["id"]]


def test_refresco_de_mercado_sin_red_no_rompe(cliente):
    alta(cliente, "Get Lost")
    red.RED["modo"] = "caida"
    r = cliente.post("/vendedor/mercado/actualizar", headers=CLAVE)
    assert r.status_code == 200 and r.json()["actualizadas"] == 0
    assert cliente.get("/vendedor/inventario", headers=CLAVE).status_code == 200


def test_precio_sugerido(cliente):
    a = alta(cliente, "Heartfire Hero")
    r = cliente.get("/vendedor/precio-sugerido", headers=CLAVE, params={"grado": "PSA 9", "item_id": a["id"]}).json()
    assert r["fuente"] == "multiplicador" and r["precio_usd"] == round(1.4 * 1.8, 2)
    r = cliente.get("/vendedor/precio-sugerido", headers=CLAVE,
                    params={"grado": "Sin graduar", "scryfall_id": id_de("Get Lost")}).json()
    assert r["fuente"] == "scryfall" and r["precio_usd"] == 2.4
    r = cliente.get("/vendedor/precio-sugerido", headers=CLAVE, params={"grado": "PSA 9", "scryfall_id": id_de("Sin Precio")}).json()
    assert r["precio_usd"] is None


def test_scryfall_endpoints_vendedor(cliente):
    r = cliente.get("/vendedor/scryfall/autocompletar", headers=CLAVE, params={"q": "llan"}).json()
    assert "Llanowar Elves" in r["nombres"]
    r = cliente.get("/vendedor/scryfall/impresiones", headers=CLAVE, params={"nombre": "Llanowar Elves"})
    assert r.status_code == 200 and len(r.json()["impresiones"]) == 2
    assert cliente.get("/vendedor/scryfall/impresiones", headers=CLAVE, params={"nombre": "Nada"}).status_code == 404
    red.RED["modo"] = "json_roto"
    r = cliente.get("/vendedor/scryfall/autocompletar", headers=CLAVE, params={"q": "llan"})
    assert r.status_code == 200, "una respuesta rara de Scryfall no debería dar error 500"
