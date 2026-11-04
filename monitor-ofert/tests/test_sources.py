import json

from monitor.sources.listing import parse_listing
from monitor.sources.otodom import parse_next_data

ADRADAR_LIKE = """<html><body><div class="lista">
<div class="item"><a href="/licytacja/12345-dzialka-rolna-klomnice">Działka rolna, Kłomnice</a>
 <p>Pow. 0,52 ha. Cena wywołania: 18 750,00 zł. Termin: 12.12.2026. Sygn. Km 1234/25</p>
 <a href="/licytacja/12345-dzialka-rolna-klomnice">więcej</a></div>
<div class="item"><a href="/licytacja/12346-grunt">Grunt, Mykanów</a><p>2100 m2, 25 000 zł</p></div>
<a href="/regulamin">Regulamin</a>
</div></body></html>"""


def test_parse_listing():
    cfg = {"link_pattern": r"/licytacja/\d+", "category": "grunty"}
    offers = parse_listing(ADRADAR_LIKE, "https://przetargi.adradar.pl/p/grunty", cfg, "adradar")
    assert len(offers) == 2
    o = offers[0]
    assert o.url == "https://przetargi.adradar.pl/licytacja/12345-dzialka-rolna-klomnice"
    assert o.title == "Działka rolna, Kłomnice"
    assert o.area_m2 == 5200
    assert o.price == 18750
    assert o.auction_date == "2026-12-12"
    assert o.signature == "Km 1234/25"
    assert offers[1].area_m2 == 2100 and offers[1].price == 25000


def test_otodom():
    data = {"props": {"pageProps": {"data": {"searchAds": {"items": [
        {"id": 1, "slug": "dzialka-rolna-ID4abc", "title": "Działka rolna 1 ha",
         "totalPrice": {"value": 60000, "currency": "PLN"}, "areaInSquareMeters": 10000,
         "location": {"address": {"city": {"name": "Kruszyna"}, "province": {"name": "śląskie"}}}}]}}}}}
    html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'
    o = parse_next_data(html, "otodom")[0]
    assert o.url.endswith("dzialka-rolna-ID4abc")
    assert o.price == 60000 and o.area_m2 == 10000
    assert o.location == "Kruszyna, śląskie"
