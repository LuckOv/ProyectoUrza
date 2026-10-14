"""Propuestas, dashboard, configuración, registro, seguridad y migraciones."""
import sqlite3
from datetime import timedelta

import pytest

from conftest import CLAVE, alta, id_de
import red
from tienda import base, propuestas, tienda


def proximo(dia):
    hoy = base.ahora().date()
    for n in range(1, 8):
        d = hoy + timedelta(days=n)
        if base.DIAS[d.weekday()] == dia:
            return d.isoformat()


PROP = {"nombre": "Ana", "apellido": "Pérez", "email": "ana@mail.com", "grado": "PSA 9",
        "cantidad": 1, "precio": 25000, "moneda": "ARS"}


# --- propuestas -----------------------------------------------------------------

def test_propuesta_validaciones(cliente):
    sid = id_de("Blind Seer")
    for cambio, texto in [
        ({"nombre": ""}, "nombre"), ({"apellido": " "}, "apellido"), ({"email": ""}, "mail"),
        ({"email": "ana@"}, "mail"), ({"email": "ana mail.com"}, "mail"), ({"precio": 0}, "precio"),
        ({"precio": -5}, "precio"), ({"grado": "PSA 11"}, "Grado"), ({"moneda": "EUR"}, "moneda"),
        ({"cantidad": 0}, "cantidad"), ({"scryfall_id": ""}, "Elegí"),
        ({"scryfall_id": "00000000-0000-0000-0000-000000000000"}, "Scryfall"),
    ]:
        r = cliente.post("/propuestas", json={**PROP, "scryfall_id": sid, **cambio})
        assert r.status_code == 400 and texto.lower() in r.json()["detail"].lower(), (cambio, r.text)


def test_propuesta_campos_enormes(cliente):
    r = cliente.post("/propuestas", json={**PROP, "scryfall_id": id_de("Blind Seer"), "nombre": "A" * 100000,
                                          "comentario": "x" * 500000})
    assert r.status_code == 400, "un formulario público no debería aceptar textos de 100.000 letras"


def test_propuesta_ciclo_completo(cliente):
    r = cliente.post("/propuestas", json={**PROP, "scryfall_id": id_de("Blind Seer"), "email": "  ANA@Mail.com ",
                                          "comentario": "foil"})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["estado"] == "nueva" and p["email"] == "ana@mail.com" and p["carta"] == "Blind Seer"
    assert p["set_nombre"] == "Invasion" and p["en_tienda"] == []
    lista = cliente.get("/vendedor/propuestas", headers=CLAVE).json()
    assert lista["nuevas"] == 1 and len(lista["propuestas"]) == 1
    assert len(cliente.get("/vendedor/propuestas", headers=CLAVE, params={"q": "ana@"}).json()["propuestas"]) == 1
    assert cliente.get("/vendedor/propuestas", headers=CLAVE, params={"estado": "aceptada"}).json()["propuestas"] == []
    url = f"/vendedor/propuestas/{p['id']}"
    assert cliente.patch(url, headers=CLAVE, json={"estado": "en_revision"}).json()["estado"] == "en_revision"
    assert cliente.patch(url, headers=CLAVE, json={"estado": "rara"}).status_code == 400
    assert cliente.patch(url, headers=CLAVE, json={"comentario": "le ofrecí 20 mil"}).json()["comentario_vendedor"] == "le ofrecí 20 mil"
    r = cliente.post(f"{url}/al-inventario", headers=CLAVE, json={"precio_usd": 15, "cantidad": 1})
    assert r.status_code == 200, r.text
    item = r.json()
    assert item["grado"] == "PSA 9" and item["precio_usd"] == 15 and item["cantidad"] == 1
    assert cliente.get("/vendedor/propuestas", headers=CLAVE).json()["propuestas"][0]["estado"] == "aceptada"
    assert cliente.get("/vendedor/propuestas", headers=CLAVE).json()["nuevas"] == 0


def test_propuesta_no_se_carga_dos_veces(cliente):
    p = cliente.post("/propuestas", json={**PROP, "scryfall_id": id_de("Blind Seer")}).json()
    url = f"/vendedor/propuestas/{p['id']}/al-inventario"
    cliente.post(url, headers=CLAVE, json={"precio_usd": 15})
    r = cliente.post(url, headers=CLAVE, json={"precio_usd": 15})
    inv = cliente.get("/vendedor/inventario", headers=CLAVE).json()["items"]
    assert r.status_code == 400 and inv[0]["cantidad"] == 1, "un doble clic cargó la carta dos veces"


def test_propuesta_borrar(cliente):
    p = cliente.post("/propuestas", json={**PROP, "scryfall_id": id_de("Blind Seer")}).json()
    assert cliente.delete(f"/vendedor/propuestas/{p['id']}", headers=CLAVE).json() == {"ok": True}
    assert cliente.get("/vendedor/propuestas", headers=CLAVE).json()["propuestas"] == []
    assert cliente.delete("/vendedor/propuestas/999", headers=CLAVE).status_code == 200


@pytest.mark.parametrize("texto,vende", [
    ("Quiero venderles una carta", True),
    ("Tengo una Blind Seer PSA 9 a $25.000", True),
    ("te vendo un Sheoldred en PSA 10 por 300 usd", True),
    ("me la comprás a 40 lucas?", True),
    ("Tengo 2 Llanowar Elves a 3000 cada una", True),
    ("¿Venden Cavern of Souls?", False),
    ("¿Vendés Heartfire Hero?", False),
    ("Quiero comprar Heartfire Hero", False),
    ("precio de llanowar elves", False),
    ("tengo una duda de reglas", False),
    ("Tengo un mazo de elfos, qué le agrego?", False),
    # preguntas de reglas que mencionan números: no son ventas
    ("Tengo 3 vidas y mi rival está a 5, ¿puedo atacar con todo?", False),
    ("Si tengo una criatura 2/2 y le hacen daño a 2 criaturas, ¿se muere?", False),
    ("Tengo dos tierras, ¿puedo bajar algo a 2 manás?", False),
])
def test_detecta_intencion_de_vender(texto, vende):
    assert propuestas.quiere_vender(texto) is vende


def test_datos_desde_texto():
    d = propuestas.datos_desde_texto("Tengo una Blind Seer PSA 9 a $25.000")
    assert (d["carta"], d["grado"], d["precio"], d["moneda"]) == ("Blind Seer", "PSA 9", 25000.0, "ARS")
    d = propuestas.datos_desde_texto("te vendo 3 Cavern of Souls por 50 usd")
    assert (d["carta"], d["cantidad"], d["precio"], d["moneda"]) == ("Cavern of Souls", 3, 50.0, "USD")
    d = propuestas.datos_desde_texto("me la comprás a 40 lucas?")
    assert d["precio"] == 40000


# --- dashboard ------------------------------------------------------------------

def _vender(c, item, cant, estado="realizada"):
    pid = c.post("/vendedor/pedidos", headers=CLAVE, json={
        "nombre": "A", "apellido": "B", "fecha_retiro": proximo("mar"), "hora_retiro": "12:00",
        "items": [{"inventario_id": item["id"], "cantidad": cant}]}).json()["id"]
    if estado != "pendiente":
        c.patch(f"/vendedor/pedidos/{pid}", headers=CLAVE, json={"estado": estado})
    return pid


def test_dashboard_vacio(cliente):
    d = cliente.get("/vendedor/dashboard", headers=CLAVE)
    assert d.status_code == 200, d.text
    d = d.json()
    assert d["unidades"] == 0 and d["rankings"] == {"cartas": [], "sets": [], "colores": []}
    assert len(d["ventas_dias"]) == 30 and d["standard"]["total"] == 3876


def test_dashboard_rankings_y_ventas(cliente):
    hero = alta(cliente, "Heartfire Hero", cantidad=10, precio=1)
    elves = alta(cliente, "Llanowar Elves", cantidad=10, precio=1)
    lies = alta(cliente, "No More Lies", cantidad=10, precio=2)
    land = alta(cliente, "Three Tree City", cantidad=10, precio=30)
    _vender(cliente, hero, 5)
    _vender(cliente, elves, 2)
    _vender(cliente, lies, 1)
    _vender(cliente, land, 1)
    _vender(cliente, hero, 3, "pendiente")      # no cuenta como venta
    _vender(cliente, elves, 4, "rechazada")     # tampoco
    d = cliente.get("/vendedor/dashboard", headers=CLAVE).json()
    colores = {c["color"]: c["unidades"] for c in d["rankings"]["colores"]}
    assert colores == {"R": 5, "G": 2, "M": 1, "C": 1}
    assert d["rankings"]["cartas"][0] == {"nombre": "Heartfire Hero", "unidades": 5, "total": 5000}
    assert d["rankings"]["sets"][0]["set"] == "Bloomburrow" and d["rankings"]["sets"][0]["unidades"] == 6
    hoy = base.ahora().date().isoformat()
    dia = next(x for x in d["ventas_dias"] if x["fecha"] == hoy)
    assert dia["unidades"] == 9 and dia["pedidos"] == 4
    assert d["stock"]["reservado"] == 3 and d["stock"]["vendido_30"] == 9
    assert d["pedidos_abiertos"] == 1
    # una venta que se vuelve a pendiente deja de contar
    pid = _vender(cliente, hero, 1)
    cliente.patch(f"/vendedor/pedidos/{pid}", headers=CLAVE, json={"estado": "pendiente"})
    d2 = cliente.get("/vendedor/dashboard", headers=CLAVE).json()
    assert d2["stock"]["vendido_30"] == 9
    # alerta de stock: Heartfire Hero salió 9 de 10 en la semana (5+3+1)
    assert any(s["nombre"] == "Heartfire Hero" for s in d2["alertas"]["stock"])


def test_dashboard_periodos(cliente):
    alta(cliente, "Get Lost", cantidad=5, precio=1)
    for dias in (30, 90, 0, -1, 1):
        assert cliente.get("/vendedor/dashboard", headers=CLAVE, params={"dias": dias}).status_code == 200


def test_dashboard_sin_red(cliente):
    alta(cliente, "Get Lost", cantidad=5, precio=1)
    red.RED["modo"] = "caida"
    r = cliente.get("/vendedor/dashboard", headers=CLAVE)
    assert r.status_code == 200 and r.json()["standard"]["total"] is None


# --- configuración ---------------------------------------------------------------

def test_config_horarios(cliente):
    h = base.config("horarios")
    h["sab"] = {"abre": "10:00", "cierra": "14:00"}
    r = cliente.put("/vendedor/config", headers=CLAVE, json={"horarios": h})
    assert r.status_code == 200 and "sábado de 10:00 a 14:00" in r.json()["horarios_texto"]
    for malo in ({"abre": "14:00", "cierra": "10:00"}, {"abre": "9", "cierra": "18:00"}, {"abre": "25:00", "cierra": "26:00"}):
        r = cliente.put("/vendedor/config", headers=CLAVE, json={"horarios": {**h, "lun": malo}})
        assert r.status_code == 400, (malo, r.text)


def test_config_varios(cliente):
    assert cliente.put("/vendedor/config", headers=CLAVE, json={"stock_bajo": -1}).status_code == 400
    assert cliente.put("/vendedor/config", headers=CLAVE, json={"stock_bajo": 5}).json()["stock_bajo"] == 5
    assert cliente.put("/vendedor/config", headers=CLAVE, json={"alerta_precio": 2}).status_code == 400
    assert cliente.put("/vendedor/config", headers=CLAVE, json={"alerta_precio": 50}).json()["alerta_precio"] == 50
    assert cliente.put("/vendedor/config", headers=CLAVE, json={"multiplicadores": {"PSA 10": 0}}).status_code == 400
    assert cliente.put("/vendedor/config", headers=CLAVE, json={"multiplicadores": {"PSA 10": 4}}).json()["multiplicadores"]["PSA 10"] == 4
    assert cliente.put("/vendedor/config", headers=CLAVE, json={"multiplicadores": {"PSA 10": "mucho"}}).status_code == 400


def test_config_dolar(cliente):
    r = cliente.put("/vendedor/config", headers=CLAVE, json={"dolar": {"modo": "manual", "valor": 1234}})
    assert r.json()["dolar"]["valor"] == 1234
    assert cliente.put("/vendedor/config", headers=CLAVE, json={"dolar": {"modo": "manual", "valor": 0}}).status_code == 400
    assert cliente.put("/vendedor/config", headers=CLAVE, json={"dolar": {"modo": "otro"}}).status_code == 400
    assert cliente.put("/vendedor/config", headers=CLAVE, json={"dolar": {"modo": "auto", "casa": "euro"}}).status_code == 400
    r = cliente.put("/vendedor/config", headers=CLAVE, json={"dolar": {"modo": "auto", "casa": "bolsa"}})
    assert r.json()["dolar"]["valor"] == 1500
    red.RED["modo"] = "caida"
    r = cliente.put("/vendedor/config", headers=CLAVE, json={"dolar": {"modo": "auto", "casa": "blue"}})
    assert r.status_code == 400 and "dolarapi" in r.json()["detail"]
    assert cliente.post("/vendedor/config/dolar/actualizar", headers=CLAVE).status_code == 502
    # sin red, los precios siguen con el último valor
    assert cliente.get("/vendedor/inventario", headers=CLAVE).json()["dolar"] == 1500


def test_actividad_paginada(cliente):
    for i in range(7):
        base.registrar_movimiento("config", f"cosa {i}")
    r = cliente.get("/vendedor/actividad", headers=CLAVE, params={"limite": 3}).json()
    assert len(r["movimientos"]) == 3 and r["hay_mas"]
    ultimo = r["movimientos"][-1]["id"]
    r2 = cliente.get("/vendedor/actividad", headers=CLAVE, params={"limite": 3, "antes_de": ultimo}).json()
    assert all(m["id"] < ultimo for m in r2["movimientos"])
    assert cliente.get("/vendedor/actividad", headers=CLAVE, params={"q": "cosa 3"}).json()["movimientos"][0]["titulo"] == "cosa 3"
    assert cliente.get("/vendedor/actividad", headers=CLAVE, params={"tipo": "venta,reserva"}).json()["movimientos"] == []


# --- seguridad ------------------------------------------------------------------

def test_todo_el_panel_pide_clave(cliente):
    import api
    from fastapi.routing import APIRoute
    abiertos = []
    for ruta in api.app.routes:
        if not isinstance(ruta, APIRoute) or not ruta.path.startswith("/vendedor") or ruta.path == "/vendedor/entrar":
            continue
        url = ruta.path.replace("{item_id}", "1").replace("{pedido_id}", "1").replace("{pid}", "1").replace("{descuento_id}", "1")
        for metodo in ruta.methods:
            for cabecera in ({}, {"X-Vendedor-Clave": "mala"}):
                r = cliente.request(metodo, url, headers=cabecera, json={})
                if r.status_code != 401:
                    abiertos.append((metodo, url, cabecera, r.status_code))
    assert not abiertos, abiertos


def test_entrar(cliente):
    assert cliente.post("/vendedor/entrar", json={"clave": "mala"}).status_code == 401
    r = cliente.post("/vendedor/entrar", json={"clave": "clave-test"})
    assert r.status_code == 200 and r.json()["clave_por_defecto"] is False


def test_endpoints_publicos(cliente):
    assert cliente.get("/carta", params={"nombre": "no existe"}).status_code == 404
    r = cliente.get("/carta", params={"nombre": "elfos de llanowar"})
    assert r.status_code == 200 and r.json()["nombre"] == "Llanowar Elves"
    assert cliente.get("/cartas/autocompletar", params={"q": "l"}).json()["nombres"] == []
    assert "Get Lost" in cliente.get("/cartas/autocompletar", params={"q": "get"}).json()["nombres"]
    assert cliente.get("/cartas/impresiones", params={"nombre": "Blind Seer"}).json()["impresiones"][0]["set_codigo"] == "INV"


def test_carta_con_variantes(cliente):
    a = alta(cliente, "Blind Seer", cantidad=1, precio=4)
    cliente.post(f"/vendedor/inventario/{a['id']}/variante", headers=CLAVE, json={"grado": "PSA 10", "cantidad": 1, "precio_usd": 30})
    r = cliente.get("/carta", params={"nombre": "Blind Seer"}).json()
    assert {v["grado"] for v in r["variantes"]} == {"Sin graduar", "PSA 10"}
    assert r["precio_ars"] == 4000 and r["en_stock"] == 2


# --- migraciones -----------------------------------------------------------------

def test_migracion_desde_base_vieja(cliente):
    """Una base de la versión 1 (con usuarios) se migra sin perder el inventario."""
    base.BASE.unlink()
    con = sqlite3.connect(base.BASE)
    con.executescript("""
        CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nombre TEXT);
        CREATE TABLE inventario (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, set_codigo TEXT,
            set_nombre TEXT, numero TEXT, rareza TEXT, imagen TEXT, scryfall_id TEXT,
            grado TEXT NOT NULL DEFAULT 'Sin graduar', precio_usd REAL, cantidad INTEGER NOT NULL DEFAULT 0,
            legal_standard INTEGER NOT NULL DEFAULT 0, creado TEXT NOT NULL, actualizado TEXT NOT NULL);
        INSERT INTO inventario (nombre, cantidad, creado, actualizado) VALUES ('Get Lost', 3, 'x', 'x');
        PRAGMA user_version = 1;
    """)
    con.commit()
    con.close()
    base.preparar()
    base.preparar()   # dos veces no rompe
    con = sqlite3.connect(base.BASE)
    tablas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    cols = {r[1] for r in con.execute("PRAGMA table_info(inventario)")}
    assert "usuarios" not in tablas and {"propuestas", "pedidos", "carrito"} <= tablas
    assert {"colores", "precio_mercado_usd", "precio_aceptado_usd"} <= cols
    assert con.execute("SELECT cantidad FROM inventario").fetchone()[0] == 3
    con.close()   # en Windows no se puede borrar la base con una conexión abierta


def test_base_real_carga(cliente):
    """Una COPIA de la base real (backend/urza.db) migra y todos los listados responden.

    La base real no se toca: se copia a la carpeta temporal de las pruebas.
    """
    import shutil
    from conftest import ORIGEN
    real = ORIGEN / "urza.db"
    if not real.exists():
        pytest.skip("no hay backend/urza.db para probar")
    shutil.copy(real, base.BASE)
    base.preparar()
    for url in ("/vendedor/inventario", "/vendedor/dashboard", "/vendedor/pedidos", "/vendedor/propuestas",
                "/vendedor/config", "/vendedor/actividad", "/vendedor/descuentos", "/vendedor/alertas-precio"):
        r = cliente.get(url, headers=CLAVE)
        assert r.status_code == 200, (url, r.text[:300])
    assert cliente.get("/catalogo").status_code == 200


def test_csv_viejo_no_se_reimporta(cliente):
    """Si el vendedor borra todo el inventario, reiniciar no tiene que resucitar el CSV viejo."""
    from tienda import inventario
    base.CSV_VIEJO.write_text("Carta,Edición,Cantidad\nGet Lost,The Lost Caverns of Ixalan (LCI),2\n", encoding="utf-8")
    try:
        assert inventario.importar_csv_viejo() == 1
        ids = [i["id"] for i in inventario.listar()]
        inventario.borrar(ids)
        assert inventario.importar_csv_viejo() == 0, "el CSV se volvió a importar después de vaciar el inventario"
    finally:
        base.CSV_VIEJO.unlink()
