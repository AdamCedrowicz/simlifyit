import pytest

from monitor.dzialki.przeliczniki import Uzytek, factor, ha_przeliczeniowe, parse_uzytki


def test_factor_orne_iii_okreg():
    assert factor("R", "IVa", "III") == 0.90
    assert factor("S", "IV", "III") == 0.90  # sad IV jak IVa
    assert factor("Ł", "V", "III") == 0.15
    assert factor("Ls", "", "III") == 0.0
    assert factor("N", "", "I") == 0.0
    assert factor("Lzr", "", "IV") == 0.20


def test_przyklad_zlej_oferty():
    # łąka ŁV 0,27 ha + nieużytek 0,22 ha → ok. 0,04–0,05 ha przel.
    u = [Uzytek("Ł", "V", 0.27), Uzytek("N", "", 0.22)]
    assert ha_przeliczeniowe(u, "III") == pytest.approx(0.0405)
    assert ha_przeliczeniowe(u, "I") == pytest.approx(0.054)


def test_parse_uzytki():
    t = "Działka: RIVa 0,5 ha, RV – 0,2 ha, ŁIV 1200 m2, Ls 0,3 ha, N 0,05 ha. Cena 30 000 zł."
    u = parse_uzytki(t)
    assert [(x.symbol, x.klasa) for x in u] == [("R", "IVa"), ("R", "V"), ("Ł", "IV"), ("Ls", ""), ("N", "")]
    assert u[2].area_ha == pytest.approx(0.12)


def test_parse_uzytki_bez_klas():
    assert parse_uzytki("Piękna działka 0,5 ha przy lesie, cena 30 000 zł") == []
