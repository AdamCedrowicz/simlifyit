"""Identyfikacja działek przez ULDK GUGiK (https://uldk.gugik.gov.pl/)."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

import httpx

from monitor.core.geo import offset, parse_wkt_lonlat, polygon_metrics

log = logging.getLogger("monitor")
URL = "https://uldk.gugik.gov.pl/"
FIELDS = "id,voivodeship,county,commune,region,parcel,geom_wkt"


def parse_response(text: str) -> list[dict]:
    """Odpowiedź: 1. linia = status (0 lub liczba rekordów; -1 = błąd), dalej rekordy rozdzielone „|”."""
    lines = [l for l in text.strip().splitlines() if l.strip()]
    if not lines or lines[0].strip().startswith("-1"):
        return []
    out = []
    names = FIELDS.split(",")
    for line in lines[1:]:
        parts = line.split("|")
        # geom_wkt jest ostatnie; WKT nie zawiera „|”
        rec = dict(zip(names, parts))
        if rec.get("geom_wkt"):
            rec.update(polygon_metrics(parse_wkt_lonlat(rec["geom_wkt"])))
            del rec["geom_wkt"]
        out.append(rec)
    return out


class Uldk:
    def __init__(self, db=None, timeout: float = 30, parallel: int = 8):
        self.client = httpx.Client(timeout=timeout)
        self.db = db
        self.parallel = parallel
        self._xy_order = (db.get_meta("uldk_xy_order") if db else None) or "lonlat"

    def by_id(self, parcel_id: str) -> dict | None:
        r = self.client.get(URL, params={"request": "GetParcelById", "id": parcel_id,
                                         "result": FIELDS, "srid": "4326"})
        recs = parse_response(r.text)
        return recs[0] if recs else None

    def _xy(self, lat: float, lon: float, order: str) -> list[dict]:
        xy = f"{lon},{lat},4326" if order == "lonlat" else f"{lat},{lon},4326"
        r = self.client.get(URL, params={"request": "GetParcelByXY", "xy": xy, "result": FIELDS, "srid": "4326"})
        return parse_response(r.text)

    def by_xy(self, lat: float, lon: float) -> dict | None:
        recs = self._xy(lat, lon, self._xy_order)
        if not recs:  # zamieniona kolejność osi trafia poza Polskę – spróbuj drugiej i zapamiętaj
            other = "latlon" if self._xy_order == "lonlat" else "lonlat"
            recs = self._xy(lat, lon, other)
            if recs:
                self._xy_order = other
                if self.db:
                    self.db.set_meta("uldk_xy_order", other)
        return recs[0] if recs else None

    def candidates(self, lat: float, lon: float, radius_m: float = 150, step_m: float = 30) -> list[dict]:
        """Siatka punktów wokół lokalizacji, zapytania partiami równolegle, unikalne działki."""
        self.by_xy(lat, lon)  # ustala kolejność osi przed równoległymi zapytaniami
        pts = []
        n = int(radius_m // step_m)
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                if (i * step_m) ** 2 + (j * step_m) ** 2 <= radius_m ** 2:
                    pts.append(offset(lat, lon, i * step_m, j * step_m))
        found: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=self.parallel) as ex:
            for rec in ex.map(lambda p: self._safe_xy(*p), pts):
                if rec and rec.get("id"):
                    found.setdefault(rec["id"], rec)
        return list(found.values())

    def _safe_xy(self, lat, lon):
        try:
            return self._xy(lat, lon, self._xy_order)
        except httpx.HTTPError:
            return None

    def close(self):
        self.client.close()


def match_score(rec: dict, area_m2: float | None, width_m: float | None = None, length_m: float | None = None) -> float:
    """Pewność dopasowania 0–1 po powierzchni (i wymiarach, jeśli podane w ogłoszeniu)."""
    if not area_m2 or not rec.get("area_m2"):
        return 0.0
    s = max(0.0, 1 - abs(rec["area_m2"] - area_m2) / area_m2 * 4)  # 25% różnicy pola = 0
    for want, key in ((width_m, "width_m"), (length_m, "length_m")):
        if want and rec.get(key):
            s *= max(0.0, 1 - abs(rec[key] - want) / want * 2)
    return round(s, 2)


def rank_candidates(recs: list[dict], area_m2, width_m=None, length_m=None, top: int = 3) -> list[dict]:
    for r in recs:
        r["confidence"] = match_score(r, area_m2, width_m, length_m)
    return sorted([r for r in recs if r["confidence"] > 0], key=lambda r: -r["confidence"])[:top]


