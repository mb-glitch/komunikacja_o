# -*- coding: utf-8 -*-
#
"""
Maciej Bilicki
program służy do odebrania wyników z aparatu sysmex-xs
i przesłania ich do systemu lab3000

wersja: 1.1
"""
import logging

from .astm import ASTM
from komunikacja.aparaty import Bioksel6000
import komunikacja.ustawienia as config

class BiokselSerwerASTM(ASTM):
    """
    Tworzy wiecznie aktywny socket serwer,
    który przyjmuje tylko jedno połączenie i obsługuje je
    resetując i wznawiając połączenie

    Args:
        None 

    Returns:
        None

    Raises:
        KeyError: Raises an exception.

    """
    NAZWA_APARATU = 'Bioksel6000'
    HOST = '192.168.2.102'
    PORT = 5002
    serwer = False
    klient = True
    parser = Bioksel6000

    def __init__(self, ob):
        super().__init__(ob)
        self.logger = logging.getLogger('kom.BiokselASTM')
    
    @property
    def wiadomosc(self):
        self.mam_wiadomosc = False
        wiadomosc = []        
        for line in self.cleaned_data:
            if line[-1] == config.RECORD_SEP: line = line[:-1]
            wiadomosc += line.split(config.RECORD_SEP)
        self.cleaned_data = []
        return wiadomosc
