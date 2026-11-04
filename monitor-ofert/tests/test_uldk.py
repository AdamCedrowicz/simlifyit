import pytest

from monitor.core.geo import offset
from monitor.dzialki.uldk import parse_response, rank_candidates


def _rec(w, l, pid):
    lat, lon = 50.95, 19.2
    pts = [offset(lat, lon, 0, 0), offset(lat, lon, w, 0), offset(lat, lon, w, l), offset(lat, lon, 0, l)]
    wkt = "SRID=4326;POLYGON((" + ",".join(f"{p[1]} {p[0]}" for p in pts + pts[:1]) + "))"
    return f"{pid}|śląskie|częstochowski|Kłomnice|Kłomnice|123|{wkt}"


def test_parse_response():
    recs = parse_response("1\n" + _rec(13.5, 160, "240406_2.0001.123"))
    assert recs[0]["id"] == "240406_2.0001.123"
    assert recs[0]["area_m2"] == pytest.approx(2160, rel=0.01)


def test_parse_error():
    assert parse_response("-1 brak wyników") == []


def test_rank_candidates_po_polu_i_szerokosci():
    recs = parse_response("3\n" + "\n".join([_rec(13.5, 156, "a"), _rec(30, 70, "b"), _rec(50, 200, "c")]))
    top = rank_candidates(recs, 2100, width_m=13.5)
    assert top[0]["id"] == "a"
    assert all(r["id"] != "c" for r in top)
