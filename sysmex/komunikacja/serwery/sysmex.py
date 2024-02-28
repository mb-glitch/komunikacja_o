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
from komunikacja.aparaty import SysmexXs1000

class SysmexSerwerASTM(ASTM):
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
    NAZWA_APARATU = 'Sysmex Xs 1000'
    HOST = ''
    PORT = 5001
    serwer = True
    klient = False
    parser = SysmexXs1000

    def __init__(self, ob):
        super().__init__(ob)
        self.logger = logging.getLogger('kom.SysmexASTM')
    
