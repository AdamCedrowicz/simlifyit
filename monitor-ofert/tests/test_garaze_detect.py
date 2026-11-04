from monitor.garaze.detect import deep_hits, find_hits, link_text, parse_page

LIST_HTML = """<html><head><title>BIP Miasto – Ogłoszenia</title></head><body>
<nav><a href="/">Start</a> &gt; <a href="/bip">BIP</a> &gt; Ogłoszenia o sprzedaży garażu</nav>
<ul>
 <li><a href="/ogl/1">Przetarg na sprzedaż garażu przy ul. Polnej 3</a></li>
 <li>Wykaz nieruchomości przeznaczonych do zbycia – garaż w Sosnowcu <a href="/ogl/2">więcej</a></li>
 <li><a href="/ogl/3">Ogłoszenie o przetargu nr 15/2026</a></li>
 <li><a href="/ogl/4">Przetarg na najem garażu</a></li>
 <li><a href="/pliki/x.pdf">Ogłoszenie o przetargu (PDF)</a></li>
</ul>
<p>Burmistrz ogłasza sprzedaż garażu bez przetargu na rzecz najemcy.</p>
<footer>Kontakt: ul. Rynek 1</footer>
</body></html>"""


def test_link_text_ogolny():
    assert link_text("więcej", "Sprzedaż garażu") == "Sprzedaż garażu więcej"
    assert link_text("Sprzedaż garażu", "x") == "Sprzedaż garażu"


def test_find_hits():
    page = parse_page(LIST_HTML, "https://bip.miasto.pl/ogloszenia")
    hits, deep = find_hits(page, {})
    keys = {h.key for h in hits}
    assert "url:https://bip.miasto.pl/ogl/1" in keys
    assert "url:https://bip.miasto.pl/ogl/2" in keys
    assert "url:https://bip.miasto.pl/ogl/4" not in keys
    assert any(k.startswith("text:https://bip.miasto.pl/ogloszenia|burmistrz ogłasza") for k in keys)
    # okruszki nawigacji nie dają trafienia
    assert not any("start" in k for k in keys)
    assert deep == ["https://bip.miasto.pl/ogl/3"]


def test_deep_hits_pomija_wspolne_linie():
    page = parse_page(LIST_HTML, "https://bip.miasto.pl/ogloszenia")
    sub = parse_page("""<html><body><footer>Kontakt: ul. Rynek 1</footer>
      <p>Prezydent Miasta ogłasza I przetarg ustny nieograniczony na sprzedaż garażu nr 7.</p>
      <p>Cena wywoławcza: 35 000 zł</p></body></html>""", "https://bip.miasto.pl/ogl/3")
    out = deep_hits(sub, set(page.lines), {})
    assert len(out) == 1 and "garażu nr 7" in out[0]


def test_deep_hits_brak():
    sub = parse_page("<p>Przetarg na sprzedaż działki nr 12/3.</p>", "https://x.pl/a")
    assert deep_hits(sub, set(), {}) == []
