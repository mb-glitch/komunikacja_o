# -*- coding: utf-8 -*-
#
"""
Maciej Bilicki
program służy do odebrania wyników z aparatu sysmex-xs
i przesłania ich do systemu lab3000

wersja: 1.1
"""

from .aparat import Aparat
from .ramki import Wiadomosc, Pacjent, Order, OrderWyniki, Question, Wynik, Komentarz
import  komunikacja.ustawienia as config
import logging
from collections import OrderedDict


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
                    #if 'QC' in o.ramka[3]:   # nr zlecenia i ozn qc jest na 4 pozycji rekordu
                    #    self.rodzaj_msg = 'QC'
                    #elif 'BACKG' in o.ramka[3]:   #  background jest na 4 pozycji rekordu
                    #    self.rodzaj_msg = 'B'
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
    INDEX_NUMERU = 2 # index komórki w komunikacie aparatu z wynikiami
    PATTERN = '{nazwa}'
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
        testy = []
        if not self.lista_testow:
            return
        for test in self.lista_testow:
            test_id = test['ID_BADANIA']
            badanie = next((item for item in testy_do_aparatu \
                    if item['tid'] == test_id), None)
            badanie = badanie['nazwa']
            if badanie not in testy:
                testy.append(self.PATTERN.format(nazwa=badanie))
        self.zlecone_testy = testy


class OrderWyniki(Order):
    INDEX_NUMERU = 2 # index komórki w komunikacie aparatu z wynikiami
    index = 'O'
    
    def __init__(self, ramka):
        super().__init__(ramka)

    def znajdz_numer_zlecenia(self):
        # numer zlecenia jest na 4 pozycji rekordu
        nr_zlecenia = self.ramka[self.INDEX_NUMERU]
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
        # numer zlecenia jest na 4 pozycji rekordu
        nr_zlecenia = self.ramka[self.INDEX_NUMERU]
        for n in nr_zlecenia:
            if n not in ['0','1','2','3','4','5','6','7','8','9']:
                nr_zlecenia = nr_zlecenia.replace(n, '')
        nr_zlecenia = nr_zlecenia.zfill(10)
        self.numer_zlecenia = nr_zlecenia


class Wynik(Wynik):
    pole_data_wyniku = -2
    pole_nazwa_badania = 2
    pole_wynik = 3
    pole_jednostki = 4
    pole_flaga = 6
    do_usuniecia_ostatniej_pozycji = []
    def __init__(self, ramka):
        super().__init__(ramka)


class Bioksel6000(Aparat):
    NADPISZ = 'T'
    APARAT = 30 # Bioksel
    WYNIK_NUMERYCZNY = 'T'
    TYP_WYNIKU = 'N'
    # mapowane testy
    testy_znakowe = [
        {'nazwa':'0001', 'tid':74, 'nazwa_wydruk':'Czas PT', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY, 'jednostka':'s'},
        {'nazwa':'0001', 'tid':77, 'nazwa_wydruk':'Wskaźnik PT', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY, 'jednostka':'%'},
        {'nazwa':'0001', 'tid':78, 'nazwa_wydruk':'INR', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY, 'jednostka':''},
        {'nazwa':'0002', 'tid':75, 'nazwa_wydruk':'APTT', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY, 'jednostka':'s'},
        #{'nazwa':'0002', 'tid':0, 'data':'', 'wynik':'', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY, 'nadpisz':NADPISZ, 'id_aparatu':APARAT, 'wyslany':0, 'jednostka':''},
        ]
    testy_obrazy = []
    def __init__(self, ob):
        super().__init__(ob)
        self.import_ramek()
        self.logger = logging.getLogger('kom.bioksel')
        self.header = 'H|\^&|||HOST|||||bioksel6000||P|1|{data}{cr}'
        self.patient = 'P|1||||{nazwisko} {imie}||{data_urodzenia}|{plec}||||||||||||||||||||||||||{cr}'
        self.order = 'O|{lp}|{numer_zlecenia}||{test}|R|{data}|||||||||||||||||||O|||||{cr}'
        self.no_order = ''
        self.ender = 'L|1|N{cr}'
    
    def import_ramek(self):
        # ramki analiza
        self.Wiadomosc = Wiadomosc
        self.Pacjent = Pacjent
        self.Order = Order
        self.Question = Question
        self.OrderWyniki = OrderWyniki
        self.Wynik = Wynik
        self.Komentarz = Komentarz

    def clean_pytanie_o_badania(self):
        # header
        header = self.header.format(cr=config.CR, data=self.now) 
        self.odpowiedz.append(header)

        for p in self.dane.pacjenci:
            lp = 1
            for o in p.orders:
                if not o.zlecenie_info or not o.lista_testow:
                    self.logger.info('Błędny numer zlecenia lub brak testów do aparatu: {pid}'\
                            .format(pid=o.numer_zlecenia))
                    # wysyłam ramkę z generycznym zleceniem braku zlecenia
                    # zamówienie testów / order
                    #order = self.no_order.format(
                    #        numer_zlecenia=o.numer_zlecenia,
                    #        data=self.now,
                    #        cr=config.CR
                    #        )
                    #self.odpowiedz.append(order)
                else:
                    # pacjent
                    patient = self.patient.format(
                            id_pacjenta=p.id_pacjenta,
                            nazwisko=p.nazwisko,
                            imie=p.imie,
                            data_urodzenia=p.data_urodzenia,
                            plec=p.plec,
                            cr=config.CR
                            )
                    self.odpowiedz.append(patient)
                    for test in o.zlecone_testy:
                    # zamówienie testów / order
                        order = self.order.format(
                            lp=lp,
                            numer_zlecenia=o.numer_zlecenia,
                            test=test,
                            data=o.data,
                            cr=config.CR
                            )
                        self.odpowiedz.append(order)
                        lp += 1
        # ender 
        ender = self.ender.format(cr=config.CR)
        self.odpowiedz.append(ender)
        self.odpowiedz = [''.join(self.odpowiedz)]

    def clean_wyniki(self):
        for badanie in self.testy:
            for p in self.dane.pacjenci:
                for o in p.orders:
                    for w in o.wyniki:
                        if badanie['nazwa'] == w.nazwa and badanie['jednostka'] == w.jednostka:
                            wynik = OrderedDict(self.wynik_wzor)
                            wynik['pid'] = o.numer_zlecenia
                            wynik['tid'] = badanie['tid']
                            wynik['id_aparatu'] = self.APARAT
                            wynik['nazwa'] = badanie['nazwa_wydruk']
                            wynik['wynik'] = w.wynik
                            wynik['typ_wyniku'] = badanie['typ_wyniku']
                            wynik['wynik_numeryczny'] = badanie['wynik_numeryczny']
                            wynik['data'] = w.data_wyniku
                            # jeżeli ścieżka obrazka w wyniku
                            if w.obrazek: 
                                wynik['wynik'] = w.obrazek_sciezka
                                wynik['obrazek'] = 1
                            self.wyniki.append(wynik)          
    
