# -*- coding: utf-8 -*-
#
"""
Maciej Bilicki
program służy do odebrania wyników z aparatu bioksel
i przesłania ich do systemu lab3000

wersja: 2.1
"""
import logging, logging.handlers
import time

from komunikacja.obsluga_baz import ObslugaBaz

from komunikacja.serwery import BiokselSerwerASTM
from komunikacja.gui import ConsoleGui

MEGABYTE = 1000*1000  # 1000000

nazwa_pliku_log = 'log/bioksel/kom.log'
# create logger with 'komunikacja'
logger = logging.getLogger('kom')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.handlers.RotatingFileHandler(
                                nazwa_pliku_log, 
                                maxBytes=MEGABYTE,
                                backupCount=100
                                )
fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)

ob = None
bioksel = None

if __name__ == '__main__':
    while True:
        ConsoleGui.odswiez()
        if not ob: ob = ObslugaBaz()
        if not bioksel: bioksel = BiokselSerwerASTM(ob)
        try:
            bioksel.loop()
            if not bioksel.zajety:
                ob.wyslij_jeden_wynik_do_mssql()
        except Exception as e:
            logger.error(e)
            ob = None
            bioksel = None
            time.sleep(10)



