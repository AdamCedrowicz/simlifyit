"""Geometria bez zależności: odległość, pole i wymiary działki z WKT (WGS84)."""
from __future__ import annotations

import math
import re

R = 6_371_000.0


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a)) / 1000


def parse_wkt_lonlat(wkt: str) -> list[list[tuple[float, float]]]:
    """Pierścienie zewnętrzne z POLYGON/MULTIPOLYGON jako listy (lon, lat). Kolejność osi rozpoznana po zakresie PL."""
    wkt = wkt.split(";", 1)[-1]
    rings = []
    for ring in re.findall(r"\(\(+([^()]+)\)", wkt):
        pts = []
        for pair in ring.split(","):
            a, b = map(float, pair.split()[:2])
            pts.append((a, b) if a < b else (b, a))  # w Polsce lon (14–24) < lat (49–55)
        rings.append(pts)
    return rings


def _to_local_m(pts, lat0, lon0):
    k = math.cos(math.radians(lat0))
    return [(math.radians(lon - lon0) * R * k, math.radians(lat - lat0) * R) for lon, lat in pts]


def centroid(pts) -> tuple[float, float]:
    """(lat, lon) – średnia wierzchołków, wystarczająca do odległości i siatki zapytań."""
    lon = sum(p[0] for p in pts) / len(pts)
    lat = sum(p[1] for p in pts) / len(pts)
    return lat, lon


def polygon_metrics(rings) -> dict:
    """Pole [m²], długość = największa odległość między wierzchołkami, szerokość = pole / długość."""
    all_pts = [p for r in rings for p in r]
    lat0, lon0 = centroid(all_pts)
    area = 0.0
    for ring in rings:
        xy = _to_local_m(ring, lat0, lon0)
        area += abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(xy, xy[1:] + xy[:1]))) / 2
    xy = _to_local_m(all_pts, lat0, lon0)
    length = max((math.dist(a, b) for i, a in enumerate(xy) for b in xy[i + 1:]), default=0.0)
    width = area / length if length else 0.0
    return {"area_m2": area, "length_m": length, "width_m": width, "lat": lat0, "lon": lon0}


def offset(lat, lon, dx_m, dy_m) -> tuple[float, float]:
    return (lat + math.degrees(dy_m / R), lon + math.degrees(dx_m / (R * math.cos(math.radians(lat)))))
