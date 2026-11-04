"""Przebieg modułu działek z podstawionymi źródłami, geokoderem i ULDK (bez sieci)."""
import pytest

import monitor.core.run as run_mod
import monitor.dzialki.module as dm
from monitor.core.offer import Offer
from monitor.core.run import RunOptions

COORDS = {"Kłomnice, Polska": (50.92, 19.36), "Mykanów, Polska": (50.91, 19.10), "Gdańsk, Polska": (54.35, 18.65)}


class FakeGeo:
    def __init__(self, db):
        pass

    def geocode(self, q):
        return COORDS.get(q)


class FakeUldk:
    def __init__(self, db, parallel=8):
        pass

    def by_id(self, pid):
        return None

    def close(self):
        pass


def offers_round(n):
    base = [
        Offer("komornik", "k1", "Działka rolna", location="Kłomnice", signature="Km 10/25",
              description="RIVa 1,0 ha", start_price=45_000, auction_date="2026-12-01"),
        Offer("komornik", "k2", "Udział 1/2 w działce rolnej", location="Mykanów", price=5_000),
        Offer("komornik", "k3", "Grunt orny", location="Gdańsk", description="RIII 1 ha", price=10_000),
    ]
    adradar = [Offer("adradar", "a1", "Licytacja: grunt Kłomnice", location="Kłomnice", signature="KM 10/25",
                     start_price=45_000)]
    if n >= 2:
        adradar.append(Offer("adradar", "a2", "Łąka", location="Mykanów", description="ŁV 0,27 ha, N 0,22 ha",
                             price=12_800))
    return {"komornik": base, "adradar": adradar}


@pytest.fixture
def env(tmp_path, monkeypatch):
    sent, state = [], {"round": 1}
    monkeypatch.setattr(dm, "DATA_DIR", tmp_path)
    monkeypatch.setattr(dm, "Geocoder", FakeGeo)
    monkeypatch.setattr(dm, "Uldk", FakeUldk)
    monkeypatch.setattr(dm, "load_yaml", lambda name: {
        "zrodla_dzialki.yaml": {"zrodla": [{"name": "komornik", "type": "x"}, {"name": "adradar", "type": "x"},
                                           {"name": "krz", "type": "manual", "manual_url": "https://krz.ms.gov.pl/"}],
                                "gminy": ["Kłomnice", "Mykanów"]},
        "okregi_podatkowe.yaml": {"domyslny": "III"}}[name])
    monkeypatch.setattr(dm, "get_fetcher", lambda kind: lambda cfg, ctx: offers_round(state["round"])[cfg["name"]])
    monkeypatch.setattr(run_mod, "send_mail", lambda s, b, t=None: sent.append((s, b)))
    monkeypatch.delenv("REF_PARCEL_ID", raising=False)
    return sent, state


def test_dzialki(env, monkeypatch):
    sent, state = env
    monkeypatch.setattr(dm.DB, "get_meta", lambda self, k: "1" if k.startswith("baseline") else None)
    dm.run(RunOptions())
    assert len(sent) == 1
    subj, body = sent[0]
    assert subj.startswith("Działki: 1 nowych ofert (najlepsza: 50 000 zł/ha przel.)")
    assert "Działka rolna" in body and "także w: adradar" in body
    assert "Udział" not in body and "Gdańsk" not in body       # odrzucone
    assert "krz" in body                                         # do ręcznego przeglądu
    state["round"] = 2
    dm.run(RunOptions())
    assert len(sent) == 2 and "Łąka" in sent[1][1] and "Działka rolna" not in sent[1][1]
    dm.run(RunOptions())
    assert len(sent) == 2                                        # nic nowego = brak maila


def test_pierwszy_przebieg_bez_maila(env):
    sent, _ = env
    dm.run(RunOptions())
    assert sent == []
