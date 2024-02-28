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
import logging

class SysmexXs1000(Aparat):
    NADPISZ = 'T'
    APARAT = 31 # XS-1000 Sysmex
    WYNIK_NUMERYCZNY = 'T'
    TYP_WYNIKU = 'N'
    # format nazwy badania w komunikacie z aparatu    
    PATTERN = '^^^^{nazwa}'
    # mapowane testy
    testy_znakowe = [
        {'nazwa':'WBC', 'tid':26, 'nazwa_wydruk':'WBC','typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'RBC', 'tid':27, 'nazwa_wydruk':'RBC', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'HGB', 'tid':28, 'nazwa_wydruk':'HGB', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'HCT', 'tid':29, 'nazwa_wydruk':'HCT', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'MCV', 'tid':30, 'nazwa_wydruk':'MCV', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'MCH', 'tid':31, 'nazwa_wydruk':'MCH', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'MCHC', 'tid':32, 'nazwa_wydruk':'MCHC', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'PLT', 'tid':33, 'nazwa_wydruk':'PLT', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'LYMPH%', 'tid':52, 'nazwa_wydruk':'LYMPH%', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'MONO%', 'tid':207, 'nazwa_wydruk':'MONO%', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'NEUT%', 'tid':48, 'nazwa_wydruk':'NEUT%', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'EO%', 'tid':209, 'nazwa_wydruk':'EO%', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'BASO%', 'tid':211, 'nazwa_wydruk':'BASO%', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'LYMPH#', 'tid':56, 'nazwa_wydruk':'LYMPH#', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'MONO#', 'tid':53, 'nazwa_wydruk':'MONO#', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'NEUT#', 'tid':57, 'nazwa_wydruk':'NEUT#', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'EO#', 'tid':208, 'nazwa_wydruk':'EO#', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'BASO#', 'tid':210, 'nazwa_wydruk':'BASO#', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'RDW-CV', 'tid':60, 'nazwa_wydruk':'RDW-CV', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'RDW-SD', 'tid':902, 'nazwa_wydruk':'RDW-SD', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'PDW', 'tid':58, 'nazwa_wydruk':'PDW', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'MPV', 'tid':59, 'nazwa_wydruk':'MPV', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'P-LCR', 'tid':34, 'nazwa_wydruk':'P-LCR', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'PCT', 'tid':903, 'nazwa_wydruk':'PCT', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        ]
    testy_obrazy = [
        {'nazwa':'DIST_WBC', 'tid':26, 'nazwa_wydruk':'', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'DIST_RBC', 'tid':27, 'nazwa_wydruk':'', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'DIST_PLT', 'tid':33, 'nazwa_wydruk':'', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        {'nazwa':'SCAT_DIFF', 'tid':211, 'nazwa_wydruk':'', 'typ_wyniku':TYP_WYNIKU, 'wynik_numeryczny':WYNIK_NUMERYCZNY},
        ]
    def __init__(self, ob):
        super().__init__(ob)
        self.import_ramek()
        self.logger = logging.getLogger('kom.sysmex')
        self.header = 'H|\^&|||||||||||E1394-97{cr}'
        self.patient = 'P|1|||{id_pacjenta}|^{nazwisko}^{imie}||{data_urodzenia}|{plec}|||||^bd||||||||||||^^^{oddzial}{cr}'
        self.order = 'O|1|2^1^{numer_zlecenia}^B||{testy}||{data}|||||N||||||||||||||Q{cr}'
        self.no_order = 'O|1|2^1^{numer_zlecenia}^B||||{data}|||||N||||||||||||||Y{cr}'
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

