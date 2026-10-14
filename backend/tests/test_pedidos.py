"""Carrito, retiros, pedidos por chat y a mano, estados y stock."""
import threading
from datetime import timedelta

from conftest import CLAVE, alta
from tienda import base, tienda


def proximo(dia_semana: str, hora="15:00"):
    """Próxima fecha (desde mañana) que cae en ese día."""
    hoy = base.ahora().date()
    for n in range(1, 8):
        d = hoy + timedelta(days=n)
        if base.DIAS[d.weekday()] == dia_semana:
            return d.isoformat(), hora


def stock(c, item_id):
    return next(i for i in c.get("/vendedor/inventario", headers=CLAVE).json()["items"] if i["id"] == item_id)["cantidad"]


def test_carrito_basico_y_topes(cliente):
    a = alta(cliente, "Get Lost", cantidad=2, precio=3)
    r = cliente.post("/carrito/t1", json={"inventario_id": a["id"], "cantidad": 2})
    assert r.status_code == 200 and r.json()["items"][0]["cantidad"] == 2
    r = cliente.post("/carrito/t1", json={"inventario_id": a["id"], "cantidad": 1})
    assert r.status_code == 409 and "Sólo quedan 2" in r.json()["detail"]
    assert cliente.post("/carrito/t1", json={"inventario_id": a["id"], "cantidad": 0}).status_code == 409
    assert cliente.post("/carrito/t1", json={"inventario_id": a["id"], "cantidad": -3}).status_code == 409
    assert cliente.post("/carrito/t1", json={"inventario_id": 999, "cantidad": 1}).status_code == 409
    # otra charla no ve ni puede borrar este carrito
    assert cliente.get("/carrito/t2").json()["items"] == []
    item_id = cliente.get("/carrito/t1").json()["items"][0]["id"]
    cliente.delete(f"/carrito/t2/{item_id}")
    assert len(cliente.get("/carrito/t1").json()["items"]) == 1
    assert cliente.delete(f"/carrito/t1/{item_id}").json()["items"] == []


def test_carrito_sin_stock_o_sin_precio(cliente):
    a = alta(cliente, "Get Lost", cantidad=1, precio=3)
    cliente.patch(f"/vendedor/inventario/{a['id']}", headers=CLAVE, json={"cantidad": 0})
    assert "No queda stock" in cliente.post("/carrito/t", json={"inventario_id": a["id"]}).json()["detail"]
    sp = alta(cliente, "Sin Precio", cantidad=1)
    assert "precio" in cliente.post("/carrito/t", json={"inventario_id": sp["id"]}).json()["detail"]


def test_validar_retiro():
    lunes = proximo("lun")
    domingo = proximo("dom")
    assert tienda.validar_retiro(*lunes) == lunes
    for f, h, texto in [
        (domingo[0], "15:00", "cerrada"),
        (lunes[0], "09:59", "abre de"),
        (lunes[0], "20:00", "abre de"),
        ("2020-01-01", "12:00", "ya pasaron"),
        ((base.ahora().date() + timedelta(days=90)).isoformat(), "12:00", "60 días"),
        ("31/12/2026", "12:00", "no es válida"),
        (lunes[0], "5 de la tarde", "no es válida"),
    ]:
        try:
            tienda.validar_retiro(f, h)
            raise AssertionError(f"debió fallar: {f} {h}")
        except ValueError as e:
            assert texto in str(e), (f, h, str(e))


def test_retiro_acepta_hora_con_segundos():
    lunes = proximo("lun")
    assert tienda.validar_retiro(lunes[0], "15:00:00") == lunes


def test_confirmar_pedido_reserva_stock(cliente):
    a = alta(cliente, "Get Lost", cantidad=3, precio=3)
    cliente.post("/carrito/t1", json={"inventario_id": a["id"], "cantidad": 2})
    p = tienda.confirmar_pedido("t1", "Ana", "Pérez", *proximo("mar"))
    assert p["estado"] == "pendiente" and p["total"] == 6000 and p["unidades"] == 2
    assert p["items"][0]["colores"] == "W" and p["items"][0]["set_codigo"] == "LCI"
    assert stock(cliente, a["id"]) == 1
    assert cliente.get("/carrito/t1").json()["items"] == []


def test_confirmar_validaciones():
    for args, texto in [
        (("t-vacio", "Ana", "Pérez", *proximo("mar")), "vacío"),
        (("t", "", "Pérez", *proximo("mar")), "nombre"),
        (("t", "Ana", "  ", *proximo("mar")), "nombre"),
    ]:
        try:
            tienda.confirmar_pedido(*args)
            raise AssertionError(args)
        except ValueError as e:
            assert texto in str(e)


def test_no_se_vende_dos_veces_la_ultima_copia(cliente):
    """Dos charlas tienen la última copia en el carrito y confirman: sólo una puede."""
    a = alta(cliente, "Cavern of Souls", cantidad=1, precio=40)
    cliente.post("/carrito/A", json={"inventario_id": a["id"], "cantidad": 1})
    cliente.post("/carrito/B", json={"inventario_id": a["id"], "cantidad": 1})
    tienda.confirmar_pedido("A", "Ana", "Uno", *proximo("mar"))
    try:
        tienda.confirmar_pedido("B", "Beto", "Dos", *proximo("mar"))
        segundo_ok = True
    except ValueError:
        segundo_ok = False
    assert not segundo_ok
    assert stock(cliente, a["id"]) == 0


def test_pedido_manual_con_lineas_repetidas_no_sobrevende(cliente):
    a = alta(cliente, "Cavern of Souls", cantidad=2, precio=40)
    r = cliente.post("/vendedor/pedidos", headers=CLAVE, json={
        "nombre": "Ana", "apellido": "Pérez", "fecha_retiro": proximo("mar")[0], "hora_retiro": "12:00",
        "items": [{"inventario_id": a["id"], "cantidad": 2}, {"inventario_id": a["id"], "cantidad": 2}],
    })
    assert r.status_code == 409, f"vendió 4 de una carta con stock 2 (status {r.status_code})"
    assert stock(cliente, a["id"]) == 2


def test_confirmaciones_en_paralelo(cliente):
    a = alta(cliente, "Cavern of Souls", cantidad=1, precio=40)
    for i in range(8):
        cliente.post(f"/carrito/p{i}", json={"inventario_id": a["id"], "cantidad": 1})
    ok, errores, raros = [], [], []

    def confirmar(i):
        try:
            ok.append(tienda.confirmar_pedido(f"p{i}", "X", str(i), *proximo("mar")))
        except ValueError as e:
            errores.append(str(e))
        except Exception as e:   # database is locked, etc.
            raros.append(repr(e))

    hilos = [threading.Thread(target=confirmar, args=(i,)) for i in range(8)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert not raros, raros
    assert len(ok) == 1, f"se confirmaron {len(ok)} pedidos de 1 sola copia"
    assert stock(cliente, a["id"]) == 0


def test_estados_y_stock(cliente):
    a = alta(cliente, "Get Lost", cantidad=3, precio=3)
    r = cliente.post("/vendedor/pedidos", headers=CLAVE, json={
        "nombre": "Ana", "apellido": "Pérez", "fecha_retiro": proximo("dom")[0], "hora_retiro": "12:00",
        "items": [{"inventario_id": a["id"], "cantidad": 2}], "comentario": "llamó por teléfono"})
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    assert stock(cliente, a["id"]) == 1
    url = f"/vendedor/pedidos/{pid}"
    assert cliente.patch(url, headers=CLAVE, json={"estado": "rechazada"}).json()["estado"] == "rechazada"
    assert stock(cliente, a["id"]) == 3
    assert cliente.patch(url, headers=CLAVE, json={"estado": "pendiente"}).status_code == 200
    assert stock(cliente, a["id"]) == 1
    assert cliente.patch(url, headers=CLAVE, json={"estado": "realizada"}).status_code == 200
    assert stock(cliente, a["id"]) == 1
    assert cliente.patch(url, headers=CLAVE, json={"estado": "volando"}).status_code == 409
    # rechazar, vender lo que quedó y querer reactivar: no alcanza
    cliente.patch(url, headers=CLAVE, json={"estado": "rechazada"})
    cliente.patch(f"/vendedor/inventario/{a['id']}", headers=CLAVE, json={"cantidad": 1})
    r = cliente.patch(url, headers=CLAVE, json={"estado": "pendiente"})
    assert r.status_code == 409 and "No hay stock" in r.json()["detail"]
    assert stock(cliente, a["id"]) == 1


def test_comentario_y_reprogramar_quedan_en_actividad(cliente):
    a = alta(cliente, "Get Lost", cantidad=3, precio=3)
    pid = cliente.post("/vendedor/pedidos", headers=CLAVE, json={
        "nombre": "Ana", "apellido": "Pérez", "fecha_retiro": proximo("mar")[0], "hora_retiro": "12:00",
        "items": [{"inventario_id": a["id"], "cantidad": 1}]}).json()["id"]
    url = f"/vendedor/pedidos/{pid}"
    cliente.patch(url, headers=CLAVE, json={"comentario": "paga en efectivo"})
    cliente.patch(url, headers=CLAVE, json={"comentario": "paga con transferencia"})
    cliente.patch(url, headers=CLAVE, json={"comentario": ""})
    cliente.patch(url, headers=CLAVE, json={"hora_retiro": "13:30"})
    assert cliente.patch(url, headers=CLAVE, json={"hora_retiro": "13hs"}).status_code == 409
    titulos = [m["titulo"] for m in cliente.get("/vendedor/actividad", headers=CLAVE).json()["movimientos"]]
    for t in ("Comentario agregado", "Comentario editado", "Comentario borrado", "retiro reprogramado"):
        assert any(t in x for x in titulos), (t, titulos)


def test_borrar_pedidos_devuelve_stock_solo_si_pendiente(cliente):
    a = alta(cliente, "Get Lost", cantidad=4, precio=3)
    datos = {"nombre": "A", "apellido": "B", "fecha_retiro": proximo("mar")[0], "hora_retiro": "12:00",
             "items": [{"inventario_id": a["id"], "cantidad": 1}]}
    p1 = cliente.post("/vendedor/pedidos", headers=CLAVE, json=datos).json()["id"]
    p2 = cliente.post("/vendedor/pedidos", headers=CLAVE, json=datos).json()["id"]
    cliente.patch(f"/vendedor/pedidos/{p2}", headers=CLAVE, json={"estado": "realizada"})
    assert stock(cliente, a["id"]) == 2
    assert cliente.post("/vendedor/pedidos/borrar", headers=CLAVE, json={"ids": [p1, p2, 999]}).json()["borrados"] == 2
    assert stock(cliente, a["id"]) == 3


def test_pedido_sobrevive_si_se_borra_la_carta(cliente):
    a = alta(cliente, "Get Lost", cantidad=2, precio=3)
    pid = cliente.post("/vendedor/pedidos", headers=CLAVE, json={
        "nombre": "A", "apellido": "B", "fecha_retiro": proximo("mar")[0], "hora_retiro": "12:00",
        "items": [{"inventario_id": a["id"], "cantidad": 1}]}).json()["id"]
    cliente.post("/vendedor/inventario/borrar", headers=CLAVE, json={"ids": [a["id"]]})
    r = cliente.patch(f"/vendedor/pedidos/{pid}", headers=CLAVE, json={"estado": "rechazada"})
    assert r.status_code == 200, r.text
    assert cliente.get("/vendedor/pedidos", headers=CLAVE).json()["pedidos"][0]["items"][0]["nombre"] == "Get Lost"


def test_filtros_pedidos_y_csv(cliente):
    a = alta(cliente, "Get Lost", cantidad=4, precio=3)
    fecha = proximo("mar")[0]
    for nombre in ("Ana", "Beto"):
        cliente.post("/vendedor/pedidos", headers=CLAVE, json={
            "nombre": nombre, "apellido": "Pérez", "fecha_retiro": fecha, "hora_retiro": "12:00",
            "items": [{"inventario_id": a["id"], "cantidad": 1}], "comentario": "con ; punto y coma"})
    assert len(cliente.get("/vendedor/pedidos", headers=CLAVE, params={"q": "beto"}).json()["pedidos"]) == 1
    assert len(cliente.get("/vendedor/pedidos", headers=CLAVE, params={"q": "#1"}).json()["pedidos"]) >= 1
    assert len(cliente.get("/vendedor/pedidos", headers=CLAVE, params={"desde": fecha, "hasta": fecha}).json()["pedidos"]) == 2
    r = cliente.get("/vendedor/historial.csv", headers=CLAVE)
    assert r.status_code == 200 and r.text.startswith("﻿Pedido;")
    import csv, io
    filas = list(csv.reader(io.StringIO(r.text.lstrip("﻿")), delimiter=";"))
    assert len(filas) == 3 and filas[1][-1] == "con ; punto y coma"
