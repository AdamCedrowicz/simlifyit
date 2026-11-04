import pytest

from monitor.core.geo import haversine_km, offset, parse_wkt_lonlat, polygon_metrics


def test_haversine():
    # Częstochowa – Katowice ok. 64 km
    assert haversine_km(50.8118, 19.1203, 50.2649, 19.0238) == pytest.approx(61, abs=4)


def test_pas_13_5_na_160():
    lat, lon = 50.95, 19.2
    pts = [offset(lat, lon, 0, 0), offset(lat, lon, 13.5, 0), offset(lat, lon, 13.5, 160), offset(lat, lon, 0, 160)]
    wkt = "SRID=4326;POLYGON((" + ",".join(f"{p[1]} {p[0]}" for p in pts + pts[:1]) + "))"
    m = polygon_metrics(parse_wkt_lonlat(wkt))
    assert m["area_m2"] == pytest.approx(2160, rel=0.01)
    assert m["width_m"] == pytest.approx(13.5, rel=0.03)
    # kolejność osi lat lon też działa
    wkt2 = "POLYGON((" + ",".join(f"{p[0]} {p[1]}" for p in pts + pts[:1]) + "))"
    assert polygon_metrics(parse_wkt_lonlat(wkt2))["area_m2"] == pytest.approx(2160, rel=0.01)
