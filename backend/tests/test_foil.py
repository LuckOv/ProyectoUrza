"""Acabado de la carta (foil) según Scryfall, para el brillo de la carta 3D."""
import red
from conftest import alta


def _acabados(nombre, i, valores, monkeypatch):
    carta = red.TODAS[nombre][i]
    monkeypatch.setitem(carta, "finishes", valores)


def test_normal_si_existe_sin_foil(cliente, monkeypatch):
    _acabados("Blind Seer", 0, ["nonfoil", "foil"], monkeypatch)
    alta(cliente, "Blind Seer", 0, precio=4.0)
    v = cliente.get("/carta", params={"nombre": "Blind Seer"}).json()["variantes"]
    assert v[0]["acabado"] == "normal"


def test_foil_si_solo_existe_en_foil(cliente, monkeypatch):
    _acabados("Blind Seer", 0, ["foil"], monkeypatch)
    _acabados("Blind Seer", 1, ["etched"], monkeypatch)
    alta(cliente, "Blind Seer", 0, precio=4.0)
    alta(cliente, "Blind Seer", 1, precio=3.0)
    variantes = cliente.get("/carta", params={"nombre": "Blind Seer"}).json()["variantes"]
    por_set = {v["set_codigo"]: v["acabado"] for v in variantes}
    assert por_set == {"INV": "foil", "PLS": "etched"}


def test_sin_dato_o_sin_red_es_normal(cliente, monkeypatch):
    alta(cliente, "Llanowar Elves", 0, precio=0.5)            # sin "finishes" en el falso
    assert cliente.get("/carta", params={"nombre": "Llanowar Elves"}).json()["variantes"][0]["acabado"] == "normal"
    from tienda import cartas
    cartas._acabados.clear(); cartas._cache.clear()
    red.RED["modo"] = "caida"
    assert cartas.acabados_de([red.TODAS["Get Lost"][0]["id"]]) == {red.TODAS["Get Lost"][0]["id"]: "normal"}
    red.RED["modo"] = "ok"


def test_carta_que_no_esta_en_la_tienda_trae_su_acabado(cliente, monkeypatch):
    _acabados("Cavern of Souls", 0, ["foil"], monkeypatch)
    assert cliente.get("/carta", params={"nombre": "Cavern of Souls"}).json()["acabado"] == "foil"


def test_agregar_carta_marca_las_impresiones_solo_foil(cliente, monkeypatch):
    """En la grilla de impresiones del panel se ve cuáles van a brillar."""
    _acabados("Blind Seer", 0, ["foil"], monkeypatch)
    _acabados("Blind Seer", 1, ["etched"], monkeypatch)
    _acabados("Blind Seer", 2, ["nonfoil", "foil"], monkeypatch)
    from conftest import CLAVE
    imps = cliente.get("/vendedor/scryfall/impresiones", headers=CLAVE, params={"nombre": "Blind Seer"}).json()["impresiones"]
    assert sorted(i["acabado"] for i in imps) == ["etched", "foil", "normal"]
