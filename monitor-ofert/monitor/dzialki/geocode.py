"""Geokodowanie miejscowości przez Nominatim (OSM), z pamięcią w bazie. Limit 1 zapytanie/s."""
from __future__ import annotations

import time

import httpx

URL = "https://nominatim.openstreetmap.org/search"
UA = "monitor-ofert/1.0 (prywatny monitor ofert, niska czestotliwosc)"


class Geocoder:
    def __init__(self, db):
        self.db = db
        self.client = httpx.Client(timeout=20, headers={"User-Agent": UA})
        self._last = 0.0

    def geocode(self, query: str) -> tuple[float, float] | None:
        q = query.strip()
        if not q:
            return None
        cached = self.db.get_geocode(q)
        if cached:
            return None if cached[0] is None else (cached[0], cached[1])
        wait = self._last + 1.1 - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        r = self.client.get(URL, params={"q": q, "format": "json", "countrycodes": "pl", "limit": 1})
        r.raise_for_status()
        data = r.json()
        res = (float(data[0]["lat"]), float(data[0]["lon"])) if data else None
        self.db.put_geocode(q, *(res or (None, None)))
        return res

    def close(self):
        self.client.close()
