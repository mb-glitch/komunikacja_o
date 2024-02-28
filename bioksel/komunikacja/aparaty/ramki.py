# -*- coding: utf-8 -*-
#
"""
Maciej Bilicki
program służy do odebrania wyników z aparatu sysmex-xs
i przesłania ich do systemu lab3000

wersja: 1.1
"""

import  komunikacja.ustawienia as config

class Wiadomosc:
    index = ['H', 'L']

    def __init__(self, ramka):
        self.ramka = ramka
        self.header = ramka
        self.ender = None
        self.pacjenci = []
        self.poprzedni = None
        self.rodzaj_msg = None

    def ustal_rodzaj_msg(self):
        for p in self.pacjenci:
            for o in p.orders:
                if o.index == 'O':
                    self.rodzaj_msg = 'R'
                    if 'QC' in o.ramka[3]:   # nr zlecenia i ozn qc jest na 4 pozycji rekordu
                        self.rodzaj_msg = 'QC'
                    elif 'BACKG' in o.ramka[3]:   #  background jest na 4 pozycji rekordu
                        self.rodzaj_msg = 'B'
                elif o.index == 'Q':
                    self.rodzaj_msg = 'Q'
                else:
                    self.rodzaj_msg = 'N'


class Pacjent:
    index = ['P', 'C']
    def __init__(self, ramka):
        self.ramka = ramka
        self.imie = None
        self.nazwisko = None
        self.plec = None
        self.data_urodzenia = None
        self.id_pacjenta = None
        self.oddzial = None
        self.orders = []
        self.komentarze = []


class Order:
    INDEX_NUMERU = 3 # index komórki w komunikacie aparatu z wynikiami
    PATTERN = '^^^^{nazwa}'
    index = None
    def __init__(self, ramka):
        self.ramka = ramka
        self.parent = None
        self.numer_zlecenia = None
        self.aparat = None
        self.data = None
        self.zlecone_testy = None
        self.zlecenie_info = None
        self.lista_testow = None
        self.wyniki = []
        self.komentarze = []
        self.znajdz_numer_zlecenia()

    def znajdz_numer_zlecenia(self):
        pass

    def uzupelnij_dane(self, aparat, ob, testy_do_aparatu):
        self.aparat = aparat
        self.zlecenie_info = ob.pobierz_pacjenta_i_zlecenie_dla_aparatu(pid=self.numer_zlecenia)
        self.lista_testow = ob.pobierz_badania_dla_aparatu(
                pid=self.numer_zlecenia,
                id_aparatu=self.aparat
                )
        if not self.zlecenie_info:
            return
        z_info = self.zlecenie_info[0]
        self.id_pacjenta = z_info['ID_PACJENTA']
        self.parent.imie = config.slugify(z_info['IMIE'])[:20]  # ograniczenie 20 znaków ze specyfikacji
        self.parent.nazwisko = config.slugify(z_info['NAZWISKO'])[:20]  # ograniczenie 20 znaków ze specyfikacji
        self.parent.data_urodzenia = z_info['DATA_URODZENIA'].strftime("%Y%m%d")
        # Muszę zmienić na angielskie odpowidniki Male, Female, Unkonwn        
        self.parent.plec = 'U'
        if z_info['PLEC'] == 'M':
            self.parent.plec = 'M'
        elif z_info['PLEC'] == 'K':
            self.parent.plec = 'F'
        self.parent.oddzial = config.slugify(z_info['NAZWA_ODDZIALU'])[:20]  # ograniczenie 20 znaków ze specyfikacji
        self.data = z_info['DATA_ZLECENIA'].strftime("%Y%m%d%H%M%S")
        testy = ''
        if not self.lista_testow:
            return
        for test in self.lista_testow:
            test_id = test['ID_BADANIA']
            badanie = next((item for item in testy_do_aparatu \
                    if item['tid'] == test_id), None)
            badanie = badanie['nazwa']
            testy += self.PATTERN.format(nazwa=badanie)
            testy += config.REPEAT_SEP
        if testy[-1] == config.REPEAT_SEP:
            testy = testy[:-1]
        self.zlecone_testy = testy


class OrderWyniki(Order):
    INDEX_NUMERU = 3 # index komórki w komunikacie aparatu z wynikiami
    index = 'O'
    
    def __init__(self, ramka):
        super().__init__(ramka)

    def znajdz_numer_zlecenia(self):
        # numer zlecenia jest na 4 pozycji rekordu
        nr_zlecenia = self.ramka[self.INDEX_NUMERU]
        nr_zlecenia = nr_zlecenia[-10:-2] # poprawić w jakiśrozsądniejszy sposób
        for n in nr_zlecenia:
            if n not in ['0','1','2','3','4','5','6','7','8','9']:
                nr_zlecenia = nr_zlecenia.replace(n, '')
        nr_zlecenia = nr_zlecenia.zfill(10)
        self.numer_zlecenia = nr_zlecenia

class Question(Order):
    INDEX_NUMERU = 2 # index komórki w komunikacie aparatu z zapytaniem o testy
    index = 'Q'
    
    def __init__(self, ramka):
        super().__init__(ramka)
    def znajdz_numer_zlecenia(self):
        # numer zlecenia jest na 3 pozycji rekordu
        nr_zlecenia = self.ramka[self.INDEX_NUMERU]
        nr_zlecenia = nr_zlecenia[-9:-1] # poprawić w jakiśrozsądniejszy sposó
        for n in nr_zlecenia:
            if n not in ['0','1','2','3','4','5','6','7','8','9']:
                nr_zlecenia = nr_zlecenia.replace(n, '')
        nr_zlecenia = nr_zlecenia.zfill(10)
        self.numer_zlecenia = nr_zlecenia


class Wynik:
    index = ['R', 'C']
    pole_data_wyniku = -1
    pole_nazwa_badania = 2
    pole_wynik = 3
    pole_jednostki = 4
    pole_flaga = 6
    do_usuniecia_ostatniej_pozycji = ['1','2','3','4','5','6','7','8','9','0']
    def __init__(self, ramka):
        self.ramka = ramka
        self.parent = None
        self.tid = None
        self.nazwa = None
        self.nazwa_org = None
        self.nazwa_ludzka = None
        self.wynik = None
        self.obrazek = False
        self.obrazek_sciezka = None
        self.flaga = None
        self.jednostka = None
        self.data_wyniku = None
        self.komentarze = []
        self.uzupelnij_dane()

    def uzupelnij_dane(self):
        # data
        data_wyniku = self.ramka[self.pole_data_wyniku]
        data_wyniku = data_wyniku.replace('\r', '')
        data_wyniku = '{rok}-{miec}-{dzien} {godz}:{minuta}:{sek}'.format(
            rok=data_wyniku[:4],
            miec=data_wyniku[4:6],
            dzien=data_wyniku[6:8],
            godz=data_wyniku[8:10],
            minuta=data_wyniku[10:12],
            sek=data_wyniku[12:14],
            )
        self.data_wyniku = data_wyniku
        # nazwa
        self.nazwa_org = self.ramka[self.pole_nazwa_badania]
        self.nazwa = self.nazwa_org.replace('^', '')
        if self.nazwa[-1] in self.do_usuniecia_ostatniej_pozycji: 
            self.nazwa = self.nazwa[:-1]
        # wynik
        self.wynik = str(self.ramka[self.pole_wynik])
        # jednostki
        self.jednostka = self.ramka[self.pole_jednostki]
        # flaga
        self.flaga = self.ramka[self.pole_flaga]
        # obrazek
        if 'PNG' in self.wynik:
            sciezka = '\\\\192.168.2.200\\shared\\{}'
            sciezka_z_wyniku = self.wynik.replace('&R&', '\\')
            self.obrazek_sciezka = sciezka.format(sciezka_z_wyniku)
            self.obrazek = True

class Komentarz:
    index = 'C'

    def __init__(self, ramka):
        self.ramka = ramka
        self.tresc = None     
    
