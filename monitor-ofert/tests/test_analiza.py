from monitor.core.offer import Offer
from monitor.dzialki.analiza import analyze, fingerprint, is_fractional, score_price_per_ha_przel


def test_udzial():
    assert is_fractional("Licytacja udziału 1/2 w nieruchomości gruntowej")
    assert is_fractional("Sprzedaż 1/4 części działki rolnej")
    assert is_fractional("współwłasność w częściach ułamkowych")
    assert not is_fractional("Działka rolna 0,5 ha wraz z udziałem w drodze dojazdowej")
    assert not is_fractional("Działka nr 123/4, obręb Jacków")


def test_cena_za_ha_przel():
    assert score_price_per_ha_przel(50_000) == 100
    assert score_price_per_ha_przel(80_000) == 75
    assert score_price_per_ha_przel(400_000) == 0


def test_zla_oferta_z_kontekstu():
    o = Offer("t", "u", "Łąka", description="ŁV 0,27 ha, N 0,22 ha", price=12_800)
    analyze(o, "III", True, {})
    e = o.extra
    assert 0.04 <= e["ha_przel"] <= 0.05
    assert 250_000 <= e["zl_ha_przel"] <= 330_000
    assert e["scores"]["krus"] < 15
    assert "(założony)" in e["ha_przel_zrodlo"]


def test_dobra_oferta_i_flagi():
    o = Offer("t", "u", "Grunt orny", description="RIVa 1,2 ha. Linia energetyczna przez działkę.", price=50_000)
    o.extra["parcel"] = {"width_m": 14.0}
    analyze(o, "III", False, {})
    f = " ".join(o.extra["flags"])
    assert "KOWR" in f and "wąski pas" in f and "linia energetyczna" in f
    assert "premii zalesieniowej" not in f  # za wąska
    assert o.extra["zl_ha_przel"] == round(50_000 / (1.2 * 0.9))


def test_fingerprint():
    a = Offer("komornik", "u1", "x", signature="Km 12/25")
    b = Offer("adradar", "u2", "y", signature="KM 12/25")
    assert fingerprint(a) == fingerprint(b)
