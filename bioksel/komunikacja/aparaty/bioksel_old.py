# -*- coding: utf-8 -*-
#
"""
Maciej Bilicki
program służy do odebrania wyników z aparatu sysmex-xs
i przesłania ich do systemu lab3000

wersja: 1.1
"""
import os
import time
import datetime
from collections import OrderedDict
import logging

import komunikacja.ustawienia as config


class Bioksel6000:
    NADPISZ = 'T'
    APARAT = 30 # Bioksel6000
    WYNIK_NUMERYCZNY = 'T'
    TYP_WYNIKU = 'N'
    # format nazwy badania w komunikacie z aparatu    
    # mapowane testy
    testy_znakowe = [
        {'nazwa':'0001', 'tid':74, 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY, 'jednostka':'s'},
        {'nazwa':'0001', 'tid':77, 'data':'', 'wynik':'', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY, 'nadpisz':NADPISZ, 'id_aparatu':APARAT, 'wyslany':0, 'jednostka':'%'},
        {'nazwa':'0001', 'tid':78, 'data':'', 'wynik':'', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY, 'nadpisz':NADPISZ, 'id_aparatu':APARAT, 'wyslany':0, 'jednostka':''},
        {'nazwa':'0002', 'tid':75, 'data':'', 'wynik':'', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY, 'nadpisz':NADPISZ, 'id_aparatu':APARAT, 'wyslany':0, 'jednostka':'s'},
        #{'nazwa':'0002', 'tid':0, 'data':'', 'wynik':'', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY, 'nadpisz':NADPISZ, 'id_aparatu':APARAT, 'wyslany':0, 'jednostka':''},
        ]
    testy_obrazy = []
    testy = testy_znakowe + testy_obrazy
    testy_do_aparatu = testy_znakowe

    header = 'H|\^&|||HOST|||||bioksel6000||P|1|{teraz}{cr}'
    patient = 'P|1||||{nazwisko} {imie}||{data_urodzenia}|{plec}||||||||||||||||||||||||||{cr}'
    order = 'O|{lp}|{numer_zlecenia}||{test}|R|{teraz}|||||||||||||||||||O|||||{cr}'
    ender = 'L|1|N{cr}'

    ZLECENIE_INDEX_O = 2 # index komórki w komunikacie aparatu z wynikiami
    ZLECENIE_INDEX_Q = 2 # index komórki w komunikacie aparatu z zapytaniem o testy

    def __init__(self, ObslugaBaz):
        self.ob = ObslugaBaz # clasa ObsługaBaz() potrzeba do komunikacji
        self.aktywny = True
        self.logger = logging.getLogger('kom.MbParser')
        self.logger.info('Inicjalizuje nowy parser')
        self.dane_list = []
        self.n = 0
        self.dane = {
            'H':'',  # header info
            'P':'',  # patient info
            'O':'',  # test order i numer zlecenia?
            'Q':'',  # zapytanie o kolejność testów
            'C':[],  # lista komentarzy pacjenta i order
            'R':[],  # lista wszystkich wyników
            'L':'',  # ramka końcowa
            }
        self.dane_nowe = {'H':'', 'P':'', 'O':'', 'Q':'', 'C':[], 'R':[], 'L':''}
        self.dane_wiele_zlecen = []
        self.wyniki = []
        self.odpowiedz = []
        self.pid = ''
        self.now = time.strftime("%Y%m%d%H%M%S", time.localtime())
        self.wynik_wzor = config.WYNIK_WZOR
        self.rodzeje_transmisji = {
            'R':'wynik',  # R bo rekordy wynikow w transmisji są R
            'QC':'qualitycheck',
            'B':'backgroundcheck',
            'Q':'zapytanie o test order',
            'N':'nieustalony'
            }
        self.rodzaj_transmisji = ''
        
    def ustal_rodzaj_transmisji(self):
        """
        Sprawdza czy wynik jest kontrolą jakości
        Uruchomić po odebraniu wszystkich ramek

        Args:
            None

        Returns:
            False: jeżeli nie jest, inaczej True 

        Raises:
            KeyError: Raises an exception.
        """
        for dane in self.dane_list:
            if dane['R']:
                self.rodzaj_transmisji = 'R'
            elif dane['Q']:
                self.rodzaj_transmisji = 'Q'
            else:
                self.rodzaj_transmisji = 'N'
        self.logger.debug('Ustaliłem rodzaj transmiji jako: {}'.format(self.rodzaj_transmisji))    
    
    def consume(self, new_data):
        """
        Przyjmuje komunikat z listy astm_server_wiadomosc

        Args:
            new_data: wiadomosc

        Returns:
            None
        Raises:
            KeyError: Raises an exception.
        """
        frame = new_data
        frame = frame[:-1] if frame.endswith(config.RECORD_SEP) else frame
        frame = frame.split(config.FIELD_SEP)
        frame_index = frame[0]
        if frame_index == 'L':
            self.dane_list += [dict(self.dane_nowe)]
        if frame_index == 'P':
            if self.dane_nowe['P']:
                self.dane_list += [dict(self.dane_nowe)]
            self.dane_nowe = {'H':'', 'P':'', 'O':'', 'Q':'', 'C':[], 'R':[], 'L':''}
        if frame_index in ['R', 'C']:
            self.dane_nowe[frame_index].append(frame)
        else:
            self.dane_nowe[frame_index] = frame
        self.logger.debug('new data = {}'.format(frame))    
        self.logger.debug('frame index = {}'.format(frame_index))    
        self.logger.debug('dane list = {}'.format(self.dane_list))    

        
    def deaktywuj(self):
        """
        Ustawia flagę aktywności na False
        Jeżeli jest False to przestaje odbierać wyniki i oczyszcza dane

        Args:
            None

        Returns:
            None

        Raises:
            KeyError: Raises an exception.
        """
        self.logger.info('Zakończyłem odbieranie danych analizuje je i odpowiadam')
        self.aktywny = False

    def znajdz_numer_zlecenia(self, dane):
        """
        Zwraca numer zlecenia z dict['O']

        Args:
            None

        Returns:
            numer_zlecenia: 10 cyfrowy string numeru zlecenia

        Raises:
            KeyError: Raises an exception.
        """
        if dane['O']:
            # uwaga teraz order 'O' jest listą! Biorę numer zlecenia tylko pierwszego
            numer_zlecenia = dane['O'][self.ZLECENIE_INDEX_O] # numer zlecenia jest na 3 pozycji rekordu
        elif dane['Q']:
            numer_zlecenia = dane['Q'][self.ZLECENIE_INDEX_Q] # numer zlecenia jest na 3 pozycji rekordu
        for n in numer_zlecenia:
            if n not in ['0','1','2','3','4','5','6','7','8','9']:
                numer_zlecenia = numer_zlecenia.replace(n, '')
        numer_zlecenia = numer_zlecenia.zfill(10)
        return numer_zlecenia
    
    def analizuj(self):
        """
        Na podstawie rodzaju transmisji wybiera opcję dalszego działania

        Args:
            None

        Returns:
            None

        Raises:
            KeyError: Raises an exception.
        """
        
        self.logger.info('Analizuje transmisjię')
        self.ustal_rodzaj_transmisji()
        if self.rodzaj_transmisji == 'R':  # wynik
            self.logger.info('Odebrałem wyniki - oczyszczam je i przygotowuje dla sqlite')
            self.clean_wyniki()
        elif self.rodzaj_transmisji == 'Q':  # pytanie o zlecone badania
            self.logger.info('Odebrałem pytanie o testy, odpowiadam do aparatu co ma zrobić')
            self.clean_pytanie_o_badania()

    def clean_pytanie_o_badania(self):
        """
        Oczyszcza dict dane
        Ustawia tylko numer zlecenia / numer próbki
        o którą prosi aparat

        Args:
            None

        Returns:
            None

        Raises:
            KeyError: Raises an exception.
        """
        for dane in self.dane_list:
            self.pid = self.znajdz_numer_zlecenia(dane)
        lista_testow = self.ob.pobierz_badania_dla_aparatu(
                pid=self.pid,
                id_aparatu=self.APARAT
                )
        zlecenie_info = self.ob.pobierz_pacjenta_i_zlecenie_dla_aparatu(pid=self.pid)
        if not zlecenie_info:
            print('Błędny numer zlecenia: {pid}'.format(pid=self.pid))
            self.logger.info('Błędny numer zlecenia: {pid}'.format(pid=self.pid))
            self.odpowiedz = None
            return False
        zlecenie_info = zlecenie_info[0]
        id_pacjenta = zlecenie_info['ID_PACJENTA']
        imie = config.slugify(zlecenie_info['IMIE'])[:20]  # ograniczenie 20 znaków ze specyfikacji
        nazwisko = config.slugify(zlecenie_info['NAZWISKO'])[:20]  # ograniczenie 20 znaków ze specyfikacji
        data_urodzenia = zlecenie_info['DATA_URODZENIA'].strftime("%Y%m%d")
        # Muszę zmienić na angielskie odpowidniki Male, Female, Unkonwn        
        plec = 'U'
        if zlecenie_info['PLEC'] == 'M':
            plec = 'M'
        elif zlecenie_info['PLEC'] == 'K':
            plec = 'F'
        oddzial = config.slugify(zlecenie_info['NAZWA_ODDZIALU'])[:20]  # ograniczenie 20 znaków ze specyfikacji
        data = zlecenie_info['DATA_ZLECENIA'].strftime("%Y%m%d%H%M%S")
        testy = []
        for test in lista_testow:
            test_id = test['ID_BADANIA']
            badanie = next((item for item in self.testy_do_aparatu \
                    if item['tid'] == test_id), None)
            badanie = badanie['nazwa']
            if badanie not in testy:
                testy.append(badanie)
        msg = ''
        # header
        header = self.header.format(
                teraz=self.now,
                cr=config.CR
                ) 
        msg += header
        # pacjent
        patient = self.patient.format(
                nazwisko=nazwisko,
                imie=imie,
                data_urodzenia=data_urodzenia,
                plec=plec,
                cr=config.CR
                )
        msg += patient
        # zamówienie testów / order
        lp = 1  # liczba porządkowa zamówienia testu
        for test in testy:
            order = self.order.format(
                    lp=lp,
                    numer_zlecenia=self.pid,
                    test=test,
                    teraz=self.now,
                    data=data,
                    cr=config.CR
                    )
            msg += order
            lp += 1
        # ender 
        ender = self.ender.format(cr=config.CR)
        msg += ender
        self.odpowiedz.append(msg)        
        print(self.odpowiedz)
           
    def clean_wyniki(self):
        """
        Oczyszcza dict dane
        Wrzuca wyniki w formie przystępnej dla procedury wrzucenia do sql
        Wrzuca wyniki do listy wyniki

        Args:
            None

        Returns:
            None

        Raises:
            KeyError: Raises an exception.
    """
        for dane in self.dane_list:
            pid = self.znajdz_numer_zlecenia(dane)
            for badanie in self.testy:
                wynik = OrderedDict(self.wynik_wzor)
                for record in dane['R']:
                    pattern = badanie['nazwa']
                    if pattern == record[2] and badanie['jednostka'] == record[4]:
                        wynik['pid'] = pid
                        wynik['tid'] = badanie['tid']
                        wynik['id_aparatu'] = self.APARAT
                        wynik['nazwa'] = badanie['nazwa']
                        wynik['wynik'] = str(record[3])
                        wynik['typ_wyniku'] = badanie['typ_wyniku']
                        wynik['wynik_numeryczny'] = badanie['wynik_numeryczny']
                        # jeżeli ścieżka obrazka w wyniku
                        data_wyniku = record[-2]
                        data_wyniku = data_wyniku.replace('\r', '')
                        data_wyniku = '{rok}-{miec}-{dzien} {godz}:{minuta}:{sek}'.format(
                            rok=data_wyniku[:4],
                            miec=data_wyniku[4:6],
                            dzien=data_wyniku[6:8],
                            godz=data_wyniku[8:10],
                            minuta=data_wyniku[10:12],
                            sek=data_wyniku[12:14],
                            )
                        wynik['data'] = data_wyniku
                        self.wyniki.append(wynik)

