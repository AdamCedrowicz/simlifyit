"""Moduł działek: pobranie → odsiew → identyfikacja (ULDK) → wyliczenia → ocena → raport."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from monitor.core.config import DATA_DIR, load_config, load_yaml
from monitor.core.db import DB
from monitor.core.geo import haversine_km
from monitor.core.http import Http
from monitor.core.offer import Offer
from monitor.core.run import (RunOptions, RunResult, SourceStatus, alert_failures, deliver,
                              track_source, write_summary)
from monitor.core.textparse import parse_area_m2, parse_parcel_id, parse_price, parse_signature
from monitor.dzialki.analiza import analyze, fingerprint, is_fractional
from monitor.dzialki.geocode import Geocoder
from monitor.dzialki.raport import build_report
from monitor.dzialki.uldk import Uldk, rank_candidates
from monitor.sources import Ctx, get_fetcher
from monitor.sources.common import get_page, page_text

log = logging.getLogger("monitor")
MODULE = "dzialki"


def reference_point(cfg: dict, db: DB, uldk: Uldk | None) -> tuple[float, float]:
    """Środek działki odniesienia z ULDK (zapamiętany w bazie); bez niej przybliżony środek Jackowa z config.yaml."""
    ref = cfg["punkt_odniesienia"]
    pid = os.environ.get("REF_PARCEL_ID") or ref.get("parcel_id") or ""
    cached = db.get_meta(f"ref:{pid}") if pid else None
    if cached:
        lat, lon = map(float, cached.split(","))
        return lat, lon
    if pid and uldk:
        try:
            rec = uldk.by_id(pid)
            if rec:
                db.set_meta(f"ref:{pid}", f"{rec['lat']},{rec['lon']}")
                return rec["lat"], rec["lon"]
        except Exception as e:  # noqa: BLE001
            log.warning("ULDK: nie udało się pobrać działki odniesienia: %s", e)
    return ref["lat"], ref["lon"]


class Okregi:
    def __init__(self, data: dict):
        self.default = data.get("domyslny", "III")
        self.map = {self._n(k): v for k, v in (data.get("gminy") or {}).items()}

    @staticmethod
    def _n(s: str) -> str:
        return re.sub(r"\s+", " ", s.lower().replace("gmina", "").replace("gm.", "")).strip()

    def lookup(self, *names: str) -> tuple[str, bool]:
        for n in names:
            if n and self._n(n) in self.map:
                return self.map[self._n(n)], False
        return self.default, True


def find_locality(o: Offer, gminy: list[str]) -> str:
    for g in gminy:
        if re.search(rf"\b{re.escape(g)}\b", o.text, re.I):
            return g
    return ""


def enrich_details(o: Offer, cfg: dict, ctx: Ctx):
    html = get_page(o.url, cfg, ctx, f"{cfg['name']}-detail")
    text = page_text(html)
    o.description = text
    o.area_m2 = o.area_m2 or parse_area_m2(text)
    o.price = o.price or parse_price(text)
    o.signature = o.signature or parse_signature(text)
    m = re.search(r"(?:sum\w* oszacowania|warto\w* oszacowania|wartość (?:rynkowa|z operatu))\D{0,30}([\d  .,]+)\s*zł", text, re.I)
    if m:
        o.estimate = parse_price(m.group(1) + " zł")
    m = re.search(r"cen\w* wywoławcz\w*\D{0,30}([\d  .,]+)\s*zł", text, re.I)
    if m:
        o.start_price = parse_price(m.group(1) + " zł")


def locate(o: Offer, uldk: Uldk | None, geo: Geocoder | None, gminy: list[str], cfg: dict):
    """Ustala współrzędne i (jeśli się da) identyfikator działki."""
    e = o.extra
    pid = parse_parcel_id(o.text)
    if pid and uldk:
        rec = uldk.by_id(pid)
        if rec:
            e["parcel"] = rec
            o.lat, o.lon = rec["lat"], rec["lon"]
            return
    if o.lat is not None and uldk and o.area_m2:
        cands = rank_candidates(uldk.candidates(o.lat, o.lon, cfg.get("uldk_promien_m", 150)), o.area_m2)
        if cands:
            e["candidates"] = [{"id": c["id"], "confidence": c["confidence"]} for c in cands]
            if cands[0]["confidence"] >= 0.8:
                e["parcel"] = cands[0]
        return
    if o.lat is not None:
        return
    place = o.location if e.get("location_from") != "config" else ""
    place = place or find_locality(o, gminy)
    if geo and place:
        res = geo.geocode(f"{place}, Polska")
        if res:
            o.lat, o.lon = res
            e["distance_approx"] = True
            return
    if geo and o.location:  # tylko powiat/województwo z konfiguracji źródła
        res = geo.geocode(f"{o.location}, Polska")
        if res:
            o.lat, o.lon = res
            e["distance_approx"] = True
            e["location_coarse"] = True


def process(o: Offer, ctx_tools: dict, cfg: dict) -> str | None:
    """Zwraca powód odrzucenia albo None. Odrzucamy tylko udział ułamkowy i odległość > promień."""
    d = cfg["dzialki"]
    if is_fractional(o.title + " " + o.description):
        return "udział ułamkowy"
    try:
        locate(o, ctx_tools["uldk"], ctx_tools["geo"], ctx_tools["gminy"], d)
    except Exception as ex:  # noqa: BLE001  identyfikacja jest dodatkiem: oferta zostaje
        o.extra.setdefault("flags", []).append(f"identyfikacja nieudana ({type(ex).__name__})")
    ref = ctx_tools["ref"]
    if o.lat is not None:
        dist = haversine_km(ref[0], ref[1], o.lat, o.lon)
        o.extra["distance_km"] = round(dist, 1)
        # przy lokalizacji z poziomu powiatu nie odrzucamy: środek powiatu to za mało
        if dist > d["promien_km"] and not o.extra.get("location_coarse"):
            return f"odległość {dist:.0f} km"
    else:
        o.extra.setdefault("flags", []).append("lokalizacja nieznana")
    commune = (o.extra.get("parcel") or {}).get("commune", "")
    okreg, assumed = ctx_tools["okregi"].lookup(commune, find_locality(o, ctx_tools["gminy"]))
    analyze(o, okreg, assumed, d)
    return None


def run(opts: RunOptions, browser=None) -> RunResult:
    cfg = load_config()
    d = cfg["dzialki"]
    src_cfg = load_yaml("zrodla_dzialki.yaml")
    db = DB(DATA_DIR / "monitor.db")
    http = Http(timeout=30, delay_ms=400)
    probe_dir = None
    if opts.probe:
        probe_dir = Path("probe/dzialki")
        probe_dir.mkdir(parents=True, exist_ok=True)
    ctx = Ctx(http, browser, probe_dir)
    uldk = Uldk(db, parallel=d.get("uldk_rownolegle", 8))
    tools = {"uldk": uldk, "geo": Geocoder(db), "gminy": src_cfg.get("gminy", []),
             "okregi": Okregi(load_yaml("okregi_podatkowe.yaml"))}
    tools["ref"] = reference_point(d, db, uldk)
    result = RunResult()
    sources = src_cfg.get("zrodla", [])
    if opts.only_source:
        sources = [s for s in sources if opts.only_source.lower() in s["name"].lower()]
    manual = [(s["name"], s.get("manual_url") or (s.get("urls") or [""])[0])
              for s in sources if s.get("type") == "manual" or not s.get("enabled", True)]
    offers: dict[str, Offer] = {}
    for s in sources:
        if s.get("type") == "manual" or (not s.get("enabled", True) and not opts.probe):
            continue
        try:
            got = get_fetcher(s["type"])(s, ctx)
            st = SourceStatus(s["name"], True, len(got))
        except Exception as e:  # noqa: BLE001
            got, st = [], SourceStatus(s["name"], False, error=f"{type(e).__name__}: {e}")
        result.add(st)
        track_source(db, MODULE, st, opts.dry_run)
        details_left = s.get("max_details", 20)
        for o in got:
            if o.key in offers or db.is_seen(MODULE, o.key):
                continue
            if s.get("fetch_details") and details_left > 0:
                details_left -= 1
                try:
                    enrich_details(o, s, ctx)
                except Exception as e:  # noqa: BLE001
                    log.debug("szczegóły %s: %s", o.url, e)
            offers[o.key] = o
    if not opts.dry_run:
        db.commit()

    kept, to_mark, by_fp = [], [], {}
    first_run = db.get_meta(f"baseline:{MODULE}") is None
    for o in offers.values():
        if first_run and not opts.dry_run and not opts.only_source:  # punkt wyjścia: bez ULDK i geokodowania, oszczędza minuty
            to_mark.append((o.key, {"title": o.title}))
            continue
        reason = process(o, tools, cfg)
        fp = fingerprint(o)
        if reason:
            log.info("odrzucona (%s): %s", reason, o.title[:80])
            to_mark.append((o.key, {"title": o.title, "odrzucona": reason}))
            continue
        if fp and fp in by_fp:  # ta sama oferta z innego źródła w tym przebiegu
            by_fp[fp].extra.setdefault("also_in", []).append(o.source)
            to_mark.append((o.key, {"title": o.title, "duplikat": by_fp[fp].key}))
            continue
        if fp and db.fp_owner(MODULE, fp):  # już wysłana wcześniej z innego źródła
            to_mark.append((o.key, {"title": o.title, "duplikat": db.fp_owner(MODULE, fp)}))
            continue
        if fp:
            by_fp[fp] = o
        kept.append(o)
        to_mark.append((o.key, {"title": o.title, "url": o.url, "extra": _small(o.extra)}))
    for fp, o in by_fp.items():
        if not opts.dry_run:
            db.add_fp(MODULE, fp, o.key)

    failed = [(s.name, _src_url(sources, s.name), s.error) for s in result.failed]
    subject, body = build_report(kept, failed, manual)
    # mail tylko, gdy są nowości; odrzucone zapisujemy razem z wysyłką (albo bez maila, gdy nic nowego)
    if kept or (first_run and not opts.only_source):
        outcome = deliver(db, MODULE, to_mark, subject, body, opts, startup_mail=d.get("mail_startowy", False))
    else:
        if not opts.dry_run:
            for k, data in to_mark:
                db.mark_seen(MODULE, k, data)
            db.commit()
        outcome = f"brak nowości (odrzucone/duplikaty: {len(to_mark)})"
    alert_failures(db, MODULE, d.get("failureAlertAfter", 6), opts, {s["name"]: _src_url(sources, s["name"]) for s in sources})
    if opts.dry_run:
        for o in sorted(kept, key=lambda x: x.extra.get("zl_ha_przel") or 1e12):
            log.info("OFERTA %s | %s | %s zł | %s", o.source, o.title[:70], o.effective_price, o.extra.get("flags"))
        Path("probe").mkdir(exist_ok=True)
        Path("probe/raport_dzialki.html").write_text(body, encoding="utf-8")
    log.info("Działki: %s", outcome)
    write_summary("Działki", result, outcome)
    uldk.close()
    http.close()
    db.close()
    return result


def _src_url(sources, name):
    for s in sources:
        if s["name"] == name:
            return s.get("manual_url") or (s.get("urls") or [""])[0]
    return ""


def _small(e: dict) -> dict:
    return {k: e[k] for k in ("zl_ha_przel", "ha_przel", "distance_km", "flags") if k in e}
