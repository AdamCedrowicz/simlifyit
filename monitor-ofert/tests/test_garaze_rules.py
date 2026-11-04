from monitor.garaze.rules import is_sale_hit


def test_sprzedaz_garazu():
    assert is_sale_hit("Przetarg ustny nieograniczony na sprzedaż garażu przy ul. Mickiewicza")


def test_slabe_slowo_wystarcza():
    assert is_sale_hit("Wykaz nieruchomości – garaż nr 5")


def test_brak_slowa_o_sprzedazy():
    assert not is_sale_hit("Garaże przy ul. Kościuszki – informacja")


def test_najem_bez_silnego_slowa():
    assert not is_sale_hit("Przetarg na najem garażu")


def test_roboty_bez_silnego_slowa():
    assert not is_sale_hit("Zaproszenie do złożenia oferty na remont garaży")
    assert not is_sale_hit("Przetarg na wymianę bram garażowych")


def test_silne_slowo_wygrywa_z_robotami():
    assert is_sale_hit("Sprzedaż garażu po remoncie, cena wywoławcza 40 000 zł")


def test_bliskosc_najem_blizej():
    t = "Sprzedaż lokalu mieszkalnego. Oddanie w najem garażu nr 3"
    assert not is_sale_hit(t)


def test_bliskosc_sprzedaz_blizej():
    t = "Ogłoszenie o najmie lokalu użytkowego. Sprzedaż garażu nr 3"
    assert is_sale_hit(t)


def test_bez_polskich_znakow():
    assert is_sale_hit("Przetarg na sprzedaz garazu blaszanego")


def test_miejsca_postojowe_opcja():
    t = "Sprzedaż miejsca postojowego w hali garażowej"
    assert is_sale_hit(t)  # „garażowej” to też garaż
    assert not is_sale_hit("Sprzedaż miejsca postojowego nr 12")
    assert is_sale_hit("Sprzedaż miejsca postojowego nr 12", include_parking=True)


def test_najem_wlaczony():
    assert is_sale_hit("Przetarg na najem garażu", include_rental=True)
