"""Red falsa: reemplaza requests.get / requests.post por Scryfall y dolarapi simulados.

RED["modo"] cambia el comportamiento para probar fallas:
  "ok"         respuestas normales
  "caida"      ConnectionError (sin internet)
  "timeout"    Timeout
  "429"        Scryfall limita el pedido
  "json_roto"  status 200 con cuerpo que no es JSON
"""
import hashlib
import re
import urllib.parse

import requests

RED = {"modo": "ok", "pedidos": [], "dolar": 1500.0}
IMG = "http://localhost:8000/img/"

CARTAS = {
    "Blind Seer": [("INV", "Invasion", "235", "rare", 4.10, False), ("PLS", "Planeshift", "101", "rare", 3.2, False),
                   ("PRM", "Promo", "7", "rare", 9.9, False)],
    "Three Tree City": [("BLB", "Bloomburrow", "260", "mythic", 32.5, True)],
    "Heartfire Hero": [("BLB", "Bloomburrow", "138", "uncommon", 1.4, True)],
    "Llanowar Elves": [("FDN", "Foundations", "227", "common", 0.3, True), ("DOM", "Dominaria", "168", "common", 0.4, False)],
    "Get Lost": [("LCI", "The Lost Caverns of Ixalan", "14", "rare", 2.4, True)],
    "Cavern of Souls": [("LCI", "The Lost Caverns of Ixalan", "269", "mythic", 38.0, False)],
    "No More Lies": [("MKM", "Murders at Karlov Manor", "221", "uncommon", 0.5, True)],
    "Unholy Annex // Ritual Chamber": [("DSK", "Duskmourn: House of Horror", "118", "rare", 2.1, True)],
    "Sin Precio": [("TST", "Test Set", "1", "common", None, True)],
}
COLORES = {"Blind Seer": ["U"], "Three Tree City": [], "Heartfire Hero": ["R"], "Llanowar Elves": ["G"],
           "Get Lost": ["W"], "Cavern of Souls": [], "No More Lies": ["W", "U"], "Unholy Annex // Ritual Chamber": None,
           "Sin Precio": ["G"]}
CARAS = {"Unholy Annex // Ritual Chamber": [{"colors": ["B"], "image_uris": {"normal": IMG + "annex.png", "small": IMG + "annex.png"}},
                                            {"colors": [], "image_uris": {"normal": IMG + "chamber.png"}}]}
ES = {"elfos de llanowar": "Llanowar Elves", "heroe del fuego del corazon": "Heartfire Hero"}


def _id(n, s, num):
    h = hashlib.md5(f"{n}{s}{num}".encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def _carta(n, p):
    s, sn, num, r, usd, std = p
    c = {"object": "card", "id": _id(n, s, num), "name": n, "set": s.lower(), "set_name": sn, "collector_number": num,
         "rarity": r, "released_at": "2024-01-01",
         "prices": {"usd": f"{usd:.2f}" if usd is not None else None, "eur": f"{usd * 0.9:.2f}" if usd else None},
         "legalities": {"standard": "legal" if std else "not_legal", "modern": "legal"},
         "type_line": "Creature — Elf Druid", "oracle_text": "{T}: Add {G}.", "mana_cost": "{G}", "cmc": 1,
         "power": "1", "toughness": "1", "scryfall_uri": "https://scryfall.com/x"}
    if n in CARAS:
        c["card_faces"] = CARAS[n]
        c.pop("type_line")
    else:
        c["colors"] = COLORES.get(n, [])
        c["image_uris"] = {"normal": IMG + c["id"] + ".png", "small": IMG + c["id"] + "s.png"}
    return c


TODAS = {n: [_carta(n, p) for p in ps] for n, ps in CARTAS.items()}
POR_ID = {c["id"]: c for cs in TODAS.values() for c in cs}


def _plano(t):
    return re.sub(r"[^a-z0-9 ]", "", (t or "").lower())


def _exacta(q):
    return next((n for n in TODAS if n.lower() == q.lower()), None)


def _difusa(q):
    for n in TODAS:
        if _plano(q) and _plano(q) in _plano(n):
            return n
    return None


class Resp:
    def __init__(self, status, datos=None, crudo=None):
        self.status_code = status
        self._datos = datos
        self._crudo = crudo

    def json(self):
        if self._crudo is not None:
            raise requests.exceptions.JSONDecodeError("no es json", self._crudo, 0)
        return self._datos

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


def _scryfall(url, cuerpo=None):
    u = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(u.query)
    path = u.path
    if path.endswith("/cards/collection"):
        datos = [POR_ID[i["id"]] for i in cuerpo["identifiers"] if i["id"] in POR_ID]
        return Resp(200, {"data": [dict(c, prices=dict(c["prices"], usd=_mov(c))) for c in datos]})
    if path.endswith("/autocomplete"):
        q = _plano(qs["q"][0])
        return Resp(200, {"data": [n for n in TODAS if q in _plano(n)]})
    if path.endswith("/named"):
        if "exact" in qs:
            n = _exacta(qs["exact"][0])
        else:
            n = _difusa(qs["fuzzy"][0])
        return Resp(200, TODAS[n][0]) if n else Resp(404, {"object": "error"})
    if path.endswith("/search"):
        q = qs["q"][0]
        if q.strip() == "f:standard":
            return Resp(200, {"total_cards": 3876, "data": []})
        if "f:" in q:
            return Resp(200, {"data": [cs[0] for n, cs in TODAS.items() if n != "Sin Precio"]})
        m = re.match(r'!"(.+?)"(?:\s+set:(\w+))?', q)
        if m:
            n = _exacta(m.group(1))
            if not n or "lang:es" in q:
                return Resp(404, {"object": "error"})
            d = TODAS[n]
            if m.group(2):
                d = [c for c in d if c["set"] == m.group(2)]
            return Resp(200, {"data": d}) if d else Resp(404, {})
        if "include_multilingual" in url:
            n = ES.get(_plano(q))
            return Resp(200, {"data": [TODAS[n][0]]}) if n else Resp(404, {})
        return Resp(404, {})
    m = re.match(r".*/cards/([0-9a-f-]{36})$", path)
    if m:
        c = POR_ID.get(m.group(1))
        return Resp(200, c) if c else Resp(404, {"object": "error"})
    return Resp(404, {})


MOVIDAS = {}   # nombre -> factor de precio de mercado (para simular que el mercado se movió)


def _mov(c):
    usd = c["prices"]["usd"]
    if usd is None:
        return None
    return f"{float(usd) * MOVIDAS.get(c['name'], 1.0):.2f}"


def _responder(url, cuerpo=None):
    RED["pedidos"].append(url)
    modo = RED["modo"]
    if modo == "caida":
        raise requests.ConnectionError("sin red (simulado)")
    if modo == "timeout":
        raise requests.Timeout("timeout (simulado)")
    if modo == "429":
        return Resp(429, {"object": "error", "status": 429})
    if modo == "json_roto":
        return Resp(200, crudo="<html>error</html>")
    if "dolarapi.com" in url:
        return Resp(200, {"venta": RED["dolar"], "compra": RED["dolar"] - 20})
    if "scryfall.com" in url:
        return _scryfall(url, cuerpo)
    raise requests.ConnectionError(f"dominio no simulado: {url}")


def get(url, params=None, headers=None, timeout=None, **kw):
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    return _responder(url)


def post(url, json=None, headers=None, timeout=None, **kw):
    return _responder(url, json)


def instalar():
    requests.get = get
    requests.post = post
