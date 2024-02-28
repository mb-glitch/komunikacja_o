# -*- coding: utf-8 -*-
#

import os
import time


class Aparat:
    def __init__(self):
        self.polaczenie = False
        self.przesylanie = False


class ConsoleGui:
    Hz = 1
    OK = 'ok'
    BRAK = 'BRAK!'
    SEPARATOR = '------------------------------'
    event = time.time()
    polaczenie_z_baza = False
    aparaty = {}
    wyniki = []
    wynikow_lokalnie = 0
    wynikow_wyslanych = 0
    clear = 'clear' if os.name == 'posix' else 'cls'
    e_karuzeli = ['|', '/', '-', '\\', '|', '/', '-', '\\']
    znak_karuzeli = ''

    def wydruk():
        os.system(ConsoleGui.clear)
        print(ConsoleGui.znak_karuzeli)
        if ConsoleGui.polaczenie_z_baza:
            baza = ConsoleGui.OK
        else:
            baza = ConsoleGui.BRAK
        print('Połączenie z bazą:  {}'.format(baza))
        print(ConsoleGui.SEPARATOR)

        for k in ConsoleGui.aparaty:
            if ConsoleGui.aparaty[k][0]:
                aparat = ConsoleGui.OK
            else:
                aparat = ConsoleGui.BRAK
            if ConsoleGui.aparaty[k][1]:
                przesylanie = ConsoleGui.znak_karuzeli
            else:
                przesylanie = ''
            print('Połączenie z {nazwa}:  {stan}{przesylanie}    w:{wysylam:d} o:{odbieram:d}'.format(
                        nazwa=k, stan=aparat, przesylanie=przesylanie,
                        wysylam=ConsoleGui.aparaty[k][2], odbieram=ConsoleGui.aparaty[k][3]
                        )
                    )
        print(ConsoleGui.SEPARATOR)
        
        print('Wyników loalnie:   {:7}'.format(ConsoleGui.wynikow_lokalnie))
        print('Wyników wysłanych: {:7}'.format(ConsoleGui.wynikow_wyslanych))
        print(ConsoleGui.SEPARATOR)
     
        #if len(ConsoleGui.wyniki) > 15:
        wyniki = ConsoleGui.wyniki[-27:]
        #else:
        #    wyniki = ConsoleGui.wyniki
        for wynik in wyniki:
            print(wynik)

    def odswiez():
        if time.time() - ConsoleGui.event > ConsoleGui.Hz:
            ConsoleGui.wydruk()
            ConsoleGui.event = time.time()
            ConsoleGui.znak_karuzeli = ConsoleGui.karuzela()

    def stan_aparatu(aparat):
        """aparat to tuple (nazwa, połączenie, zajety, wysylanie, odbieranie)
        połączenie to 0 lub 1 jeżeli połączony
        aktywność to 0 lub 1 jeżeli przesyła
        """
        ConsoleGui.aparaty[aparat[0]] = (aparat[1], aparat[2], aparat[3], aparat[4])

    def karuzela():
        sign = ConsoleGui.e_karuzeli.pop(0)
        ConsoleGui.e_karuzeli.append(sign)
        return sign
