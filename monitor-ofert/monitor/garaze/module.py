"""Moduł garaży: przeniesiona logika monitor-garazy.ps1."""
from __future__ import annotations

import html
import logging
from collections import OrderedDict
from pathlib import Path

from monitor.core.config import DATA_DIR, load_config, load_json
from monitor.core.db import DB
from monitor.core.http import Http
from monitor.core.run import (RunOptions, RunResult, SourceStatus, alert_failures, deliver,
                              track_source, write_summary)
from monitor.garaze.detect import SKIP_EXT, Hit, deep_hits, find_hits, parse_page

log = logging.getLogger("monitor")
MODULE = "garaze"


def load_sites() -> list[dict]:
    data = load_json("strony_garaze.json")
    sites = data["sites"] if isinstance(data, dict) and "sites" in data else data
    sites = [s for s in sites if s.get("enabled", True) and s.get("url")]
    if not sites:
        raise SystemExit("Brak stron w config/strony_garaze.json – wklej tam zawartość strony.json z monitora PowerShell.")
    return sites


def scan_site(site: dict, http: Http, browser, db: DB, opts: dict, visited: list[str], probe_dir: Path | None):
    if site.get("render") == "browser":
        if browser is None:
            raise RuntimeError("strona wymaga przeglądarki (Playwright niedostępny)")
        html_text, _ = browser.render(site["url"])
    else:
        html_text = http.get_text(site["url"])
    if probe_dir:
        (probe_dir / f"{_slug(site['name'])}.html").write_text(html_text, encoding="utf-8")
    page = parse_page(html_text, site["url"])
    hits, deep = find_hits(page, opts)
    list_lines = set(page.lines)
    done = 0
    for url in deep:
        if done >= opts.get("maxDeepLinksPerSite", 15):
            break
        if SKIP_EXT.search(url) or db.visited_recently(url, opts.get("visitedMemoryDays", 120)):
            continue
        done += 1
        try:
            sub = parse_page(http.get_text(url), url)
        except Exception as e:  # noqa: BLE001  podstrona nie psuje strony głównej
            log.debug("podstrona %s: %s", url, e)
            continue
        visited.append(url)  # zapis dopiero po udanym mailu
        for frag in deep_hits(sub, list_lines, opts):
            hits.append(Hit(f"url:{url}", url, frag, "podstrona"))
    return hits


def _slug(s: str) -> str:
    import re  # noqa: PLC0415
    return re.sub(r"[^a-z0-9]+", "-", s.lower())[:60]


def build_mail(new: list[tuple[dict, Hit]]) -> tuple[str, str]:
    groups: OrderedDict[str, OrderedDict[str, list[str]]] = OrderedDict()
    site_of: dict[str, dict] = {}
    for site, hit in new:
        groups.setdefault(site["name"], OrderedDict()).setdefault(hit.url, []).append(hit.snippet)
        site_of[site["name"]] = site
    n = sum(len(v) for v in groups.values())
    parts = [f"<h2>NOWE garaże na sprzedaż: {n}</h2>"]
    for name, urls in groups.items():
        s = site_of[name]
        parts.append(f"<h3>{html.escape(name)} <small>({html.escape(s.get('city', ''))}, "
                     f"{html.escape(s.get('type', ''))})</small></h3><ul>")
        for url, snippets in urls.items():
            frag = "<br>".join(f"„{html.escape(x)}”" for x in dict.fromkeys(snippets))
            parts.append(f"<li>{frag}<br><a href='{html.escape(url)}'>{html.escape(url)}</a></li>")
        parts.append("</ul>")
    return f"NOWE garaże na sprzedaż: {n}", "\n".join(parts)


def run(opts: RunOptions, browser=None) -> RunResult:
    cfg = load_config()
    g = cfg.get("garaze", {})
    db = DB(DATA_DIR / "monitor.db")
    http = Http(timeout=g.get("requestTimeoutSeconds", 30), delay_ms=g.get("delayBetweenRequestsMs", 400))
    probe_dir = None
    if opts.probe:
        probe_dir = Path("probe/garaze")
        probe_dir.mkdir(parents=True, exist_ok=True)
    result = RunResult()
    sites = load_sites()
    if opts.only_source:
        sites = [s for s in sites if opts.only_source.lower() in s["name"].lower()]
    new: list[tuple[dict, Hit]] = []
    seen_now: set[str] = set()
    visited: list[str] = []
    for site in sites:
        try:
            hits = scan_site(site, http, browser, db, g, visited, probe_dir)
            st = SourceStatus(site["name"], True, len(hits))
        except Exception as e:  # noqa: BLE001  błąd jednej strony nie zatrzymuje reszty
            hits, st = [], SourceStatus(site["name"], False, error=f"{type(e).__name__}: {e}")
        result.add(st)
        track_source(db, MODULE, st, opts.dry_run)
        for h in hits:
            if h.key in seen_now or db.is_seen(MODULE, h.key):
                continue
            seen_now.add(h.key)
            new.append((site, h))
    http.close()
    if not opts.dry_run:
        db.commit()  # liczniki awarii zapisane niezależnie od wysyłki
    subject, body = build_mail(new)
    outcome = deliver(db, MODULE, [(h.key, {"site": s["name"], "url": h.url, "snippet": h.snippet}) for s, h in new],
                      subject, body, opts, startup_mail=g.get("startupMail", False))
    if not opts.dry_run:
        for url in visited:
            db.mark_visited(url)
        db.prune_visited(g.get("visitedMemoryDays", 120))
        db.commit()
    alert_failures(db, MODULE, g.get("failureAlertAfter", 6), opts, {s["name"]: s["url"] for s in sites})
    if opts.dry_run and new:
        for s, h in new:
            log.info("TRAFIENIE [%s] %s – %s", s["name"], h.snippet[:120], h.url)
    log.info("Garaże: %s", outcome)
    write_summary("Garaże", result, outcome)
    db.close()
    return result
