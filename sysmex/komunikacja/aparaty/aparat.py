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

import  komunikacja.ustawienia as config

class Aparat:
    NADPISZ = 'T'
    APARAT = None
    WYNIK_NUMERYCZNY = 'T'
    TYP_WYNIKU = 'N'
    # format nazwy badania w komunikacie z aparatu    
    PATTERN = ''
    # mapowane testy
    testy_znakowe = []
    testy_obrazy = []

    def __init__(self, ObslugaBaz):
        self.ob = ObslugaBaz # clasa ObsługaBaz() potrzeba do komunikacji
        self.testy = self.testy_znakowe
        self.testy_do_aparatu = self.testy_znakowe
        self.aktywny = True
        self.dane = None
        self.wyniki = []
        self.logger = logging.getLogger('kom.generic')
        self.odpowiedz = []
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
        # ramki
        self.header = ''
        self.patient = ''
        self.order = ''
        self.no_order = ''
        self.ender = ''
        self.import_ramek()

    def import_ramek(self):
        # ramki analiza
        self.Wiadomosc = None
        self.Pacjent = None
        self.Order = None
        self.Question = None
        self.OrderWyniki = None
        self.Wynik = None
        self.Komentarz = None


    def consume(self, new_data):
        frame = new_data
        frame = frame[:-1] if frame.endswith(config.RECORD_SEP) else frame
        frame = frame.split(config.FIELD_SEP)
        frame_index =  frame[0]
        self.logger.debug('new data = {}'.format(frame))    
        self.logger.debug('frame index = {}'.format(frame_index))    
        if frame_index == 'H':
            self.dane = self.Wiadomosc(frame)
        elif frame_index == 'P':
            klasa = self.Pacjent(frame)
            self.dane.pacjenci.append(klasa)
            self.dane.poprzedni = klasa
        elif frame_index == 'O':
            klasa = self.OrderWyniki(frame)
            ostatni_pacjent = self.dane.pacjenci[-1]
            ostatni_pacjent.orders.append(klasa)
            klasa.parent = ostatni_pacjent
            self.dane.poprzedni = klasa
        elif frame_index == 'Q':
            klasa = self.Question(frame)
            ostatni_pacjent = self.Pacjent('')
            self.dane.pacjenci.append(ostatni_pacjent)
            ostatni_pacjent.orders.append(klasa)
            klasa.parent = ostatni_pacjent
            self.dane.poprzedni = klasa
            # pobieram dane z bazy
            klasa.uzupelnij_dane(self.APARAT, self.ob, self.testy_do_aparatu)
        elif frame_index == 'C':
            klasa = self.Komentarz(frame)
            self.dane.poprzedni.komentarze.append(klasa)
        elif frame_index == 'R':
            klasa = self.Wynik(frame)
            ostatni_pacjent = self.dane.pacjenci[-1]
            ostatni_order = ostatni_pacjent.orders[-1]
            ostatni_order.wyniki.append(klasa)
            klasa.parent = ostatni_order
        elif frame_index == 'L':
            self.dane.ender = frame
            self.dane.ustal_rodzaj_msg()
            self.rodzaj_transmisji = self.dane.rodzaj_msg
            self.logger.debug('Ustaliłem rodzaj transmiji jako: {}'.format(self.rodzaj_transmisji))    

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
        self.logger.info('Zakończyłem odbieranie danych analizuje je i ewentualnie odpowiadam')
        self.aktywny = False

    def analizuj(self):
        self.logger.info('Analizuje transmisjię')
        if self.rodzaj_transmisji == 'R':  # wynik
            self.logger.info('Odebrałem wyniki - oczyszczam je i przygotowuje dla sqlite')
            self.clean_wyniki()
        elif self.rodzaj_transmisji == 'Q':  # pytanie o zlecone badania
            self.logger.info('Odebrałem pytanie o testy, odpowiadam do aparatu co ma zrobić')
            self.clean_pytanie_o_badania()
    
    def clean_pytanie_o_badania(self):
        # header
        header = self.header.format(cr=config.CR) 
        self.odpowiedz.append(header)

        for p in self.dane.pacjenci:
            for o in p.orders:
                if not o.zlecenie_info or not o.lista_testow:
                    self.logger.info('Błędny numer zlecenia lub brak testów do aparatu: {pid}'\
                            .format(pid=o.numer_zlecenia))
                    # wysyłam ramkę z generycznym zleceniem braku zlecenia
                    # zamówienie testów / order
                    order = self.no_order.format(
                            numer_zlecenia=o.numer_zlecenia,
                            data=self.now,
                            cr=config.CR
                            )
                    self.odpowiedz.append(order)
                else:
                    # pacjent
                    patient = self.patient.format(
                            pesel=p.pesel,
                            #id_pacjenta=p.id_pacjenta,
                            nazwisko=p.nazwisko,
                            imie=p.imie,
                            data_urodzenia=p.data_urodzenia,
                            plec=p.plec,
                            oddzial=p.oddzial,
                            cr=config.CR
                            )
                    self.odpowiedz.append(patient)
                    # zamówienie testów / order
                    order = self.order.format(
                            numer_zlecenia=o.numer_zlecenia,
                            testy=o.zlecone_testy,
                            data=o.data,
                            cr=config.CR
                            )
                    self.odpowiedz.append(order)
        # ender 
        ender = self.ender.format(cr=config.CR)
        self.odpowiedz.append(ender)

    def clean_wyniki(self):
        for badanie in self.testy:
            for p in self.dane.pacjenci:
                for o in p.orders:
                    for w in o.wyniki:
                        if badanie['nazwa'] == w.nazwa:
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
    
