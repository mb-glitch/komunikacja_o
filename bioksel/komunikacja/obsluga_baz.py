# -*- coding: utf-8 -*-
#
"""
Maciej Bilicki
program służy do odebrania wyników z aparatu sysmex-xs
i przesłania ich do systemu lab3000
"""
import os
import time
from PIL import Image, ImageOps
import binascii
import sqlite3
import _mssql  #pymssql nie obsługuje dużych wyników obrazkowych
from collections import OrderedDict
import logging

import komunikacja.ustawienia as config
from komunikacja.gui import ConsoleGui

class ObslugaBaz:
    sqlite_db = config.SQLITE_NAME
    mssql_db = config.BAZA_MS
    row_wzor = config.WYNIK_WZOR
    wynikow_do_wyslania_v = 0
    wyslanych_v = 0
    sqlite_sql_init = """
CREATE TABLE wyniki (id integer primary key, pid, nazwa, tid, data, 
typ_wyniku, wynik, wynik_numeryczny, nadpisz, id_aparatu,
wyslany, obrazek);
"""
    sqlite_sql_select_wyniki = """
SELECT * FROM wyniki WHERE wyslany=0 and obrazek=0
"""
    sqlite_sql_select_obrazki = """
SELECT * FROM wyniki WHERE wyslany=0 and obrazek=1
"""
    sqlite_sql_select_niewstawione = """
SELECT * FROM wyniki WHERE wyslany=0
"""
    sqlite_sql_update_wyslane = """
UPDATE wyniki SET wyslany=1 WHERE id={id}
"""
    sqlite_sql_insert_wynik = """
INSERT INTO wyniki VALUES (NULL, '{pid}', '{nazwa}', {tid}, '{data}',
'{typ_wyniku}', '{wynik}', '{wynik_numeryczny}', '{nadpisz}',
{id_aparatu}, {wyslany}, {obrazek})
"""
    mssql_sql_insert_wyniki = """
exec proc_wstaw_wyniki_comdata 
@PID='{pid}', 
@TID={tid}, 
@data_wyniku='{data}', 
@typ_wyniku='{typ_wyniku}', 
@flaga='', 
@wynik='{wynik}', 
@opis='', 
@flaga_typu='W', 
@wynik_numeryczny='{wynik_numeryczny}', 
@nadpisz='{nadpisz}', 
@obrazek=null, 
@id_aparatu={id_aparatu}, 
@info='', 
@statyw=''
"""
    mssql_sql_select_table_wyniki = """
select ID_TABELI from WYNIKI_BADAN where ID_ZLECENIA = (
select distinct ID_ZLECENIA from zlecenie_probki where NR_PROBKI={pid}
) and ID_BADANIA={tid}
        """
    mssql_sql_insert_obrazek = """
update WYNIKI_BADAN set OBRAZEK={obrazek} 
where ID_TABELI={id_tabeli_wynikow}
"""
    mssql_sql_select_pacjent = """
select PACJENCI.ID_PACJENTA, PACJENCI.IMIE, PACJENCI.NAZWISKO,
PACJENCI.PESEL, PACJENCI.DATA_URODZENIA, PACJENCI.PLEC,
zlecenie_badania.DATA_ZLECENIA,
oddzialy.NAZWA_ODDZIALU
from PACJENCI
join zlecenie_badania on zlecenie_badania.ID_PACJENTA = PACJENCI.ID_PACJENTA
join oddzialy on zlecenie_badania.ID_ODDZIALU = oddzialy.ID_ODDZIALU
where ID_ZLECENIA = (
select distinct ID_ZLECENIA from zlecenie_probki where NR_PROBKI={pid} and WYN_ANUL='N'
)
"""
    mssql_sql_select_idbadan_zleconych_na_aparat = """
select ID_BADANIA from WYNIKI_BADAN
where ID_ZLECENIA = (
select distinct ID_ZLECENIA from zlecenie_probki where NR_PROBKI={pid} and WYN_ANUL='N'
)
and ID_BADANIA in (
select ID_BADANIA from badanie_aparat where ID_APARATU={id_aparatu}
)
"""
    
    def __init__(self):
        ConsoleGui.polaczenie_z_baza = False
        self._conn_sqlite = None
        self._conn_mssql = None
        self.logger = logging.getLogger('kom.ObslugaBaz')
        self.logger.info('Inicjalizuje połączenia z bazami danych')
        self._sqlite_connect()
        self._mssql_connect()

    def _sqlite_connect(self):
        if self._sqlite_baza_istnieje():
            self._conn_sqlite = sqlite3.connect(self.sqlite_db)
        else:
            self._conn_sqlite = sqlite3.connect(self.sqlite_db)
            self._sqlite_execute(self.sqlite_sql_init)
        self.logger.info('Połączyłem się z sqlite3')
        
            
    def _sqlite_disconnect(self):
        self._conn_sqlite.close()

    def _sqlite_baza_istnieje(self):
        if os.path.isfile(self.sqlite_db):
            return True
        else:
            return False

    def _sqlite_przypisz_row_do_row_wzor(self, row):
        row = row
        row_wg_wzoru = OrderedDict(self.row_wzor)
        i = 0
        for wiersz in list(self.row_wzor.items()):
            row_wg_wzoru[wiersz[0]] = row[i]
            i += 1
        return row_wg_wzoru
    
    def _sqlite_pobierz_wyniki_niewstawione(self):
        # self.logger.debug('Pobieram niewstawione wyniki z sqlite')    
        lista_row_wg_wzoru = []
        for row in self._sqlite_execute(self.sqlite_sql_select_wyniki):
            row = self._sqlite_przypisz_row_do_row_wzor(row)
            lista_row_wg_wzoru.append(row)
        return lista_row_wg_wzoru
    
    def _sqlite_pobierz_obrazki_niewstawione(self):
        lista_row_wg_wzoru = []
        # self.logger.debug('Pobieram niewstawione obrazki z sqlite')    
        for row in self._sqlite_execute(self.sqlite_sql_select_obrazki):
            row = self._sqlite_przypisz_row_do_row_wzor(row)
            lista_row_wg_wzoru.append(row)
        return lista_row_wg_wzoru

    def _sqlite_update_wyniki_jako_wyslane(self, **kwargs):
        """
        kwargs = row_wg_wzoru
        """
        row = kwargs
        sqlcmd = self.sqlite_sql_update_wyslane.format(**row)
        self._sqlite_execute(sqlcmd)
        self.logger.debug('Update wyników jako wstawione')    

    def sqlite_wstaw_wynik(self, **kwargs):
        """
        kwargs = row_wg_wzoru
        """
        row = kwargs
        sqlcmd = self.sqlite_sql_insert_wynik.format(**row)
        self._sqlite_execute(sqlcmd)
        wynik_str = '{pid} - {nazwa} - {wynik}'.format(**row)
        ConsoleGui.wyniki.append(wynik_str)
        self.logger.debug(wynik_str)
        
        
    def _sqlite_execute(self, sqlcmd):
        sqlcmd = sqlcmd
        cursor = self._conn_sqlite.cursor()
        try:
            cursor.execute(sqlcmd)
            self._conn_sqlite.commit()
            # self.logger.debug('Wysłałem zapytanie do sqlite: {sqlcmd}'.format(sqlcmd=sqlcmd))    
            response = cursor.fetchall()
            cursor.close()
            # self.logger.debug('Odpowiedź sqlite: {response}'.format(response=response))    
            return response
        except sqlite3.OperationalError as e:
            self.logger.debug(e)
            self.logger.debug('Baza sqlite zajęta, próbuje ponownie')
            time.sleep(0.1)
            self._sqlite_execute(sqlcmd)

    def _mssql_connect(self):
        try:
            if not self._conn_mssql:
                self._conn_mssql = _mssql.connect(**self.mssql_db)
            elif not self._conn_mssql.connected:
                self._conn_mssql = _mssql.connect(**self.mssql_db)
            self.logger.info('Połączyłem się z mssql')
            ConsoleGui.polaczenie_z_baza = True
        except Exception as e:
            self.logger.error(e)
            print(e)

    def connected(self):
        if self._conn_mssql:
            return self._conn_mssql.connected
        else:
            return False
        
    def _mssql_disconnect(self):
        self._conn_mssql.close()
        self.mssql_connected = False

    def _mssql_execute(self, sqlcmd):
        """
        Wykonuje zapytanie sqlcmd

        Args:
            sciezka: w pełni sformatowane zapytanie sql

        Returns:
            response: zwraca listę dict w formacie
            [{0: 'wartość', 'NAZWA_KOLUMNY': 'wartość'}]

        Raises:
            KeyError: Raises an exception.
        """
        sqlcmd = sqlcmd
        if not self._conn_mssql.connected:
            self._mssql_connect()
        response = []
        try:
            self._conn_mssql.execute_query(sqlcmd)
            #self.logger.debug('Wysłałem zapytanie do mssql: {sqlcmd}'.format(sqlcmd=sqlcmd))    
            response = [row for row in self._conn_mssql]
            self.logger.debug('Odpowiedź mssql: {response}'.format(response=response))    
        except Exception as e:
            self.logger.error('Błąd zapytania do mssql: {sqlcmd}'.format(sqlcmd=sqlcmd))    
            self.logger.error(e)    
            # self._mssql_execute(sqlcmd)
        return response

    def pobierz_badania_dla_aparatu(self, pid, id_aparatu, **kwargs):
        """
        kwargs = row_wg_wzoru
        """
        row = {}
        if kwargs:
            row = kwargs
        row['id_aparatu'] = id_aparatu
        row['pid'] = pid
        if not self._conn_mssql.connected:
            self._mssql_connect()
        self._conn_mssql.select_db(config.DB_NAME)
        sqlcmd = self.mssql_sql_select_idbadan_zleconych_na_aparat
        sqlcmd = sqlcmd.format(**row)
        self.logger.debug('Pobieram badania do wykonania na aparacie')    
        return self._mssql_execute(sqlcmd)
    
    def pobierz_pacjenta_i_zlecenie_dla_aparatu(self, pid, **kwargs):
        """
        kwargs = row_wg_wzoru
        """
        row = {}
        if kwargs:
            row = kwargs
        row['pid'] = pid
        if not self._conn_mssql.connected:
            self._mssql_connect()
        self._conn_mssql.select_db(config.DB_NAME)
        sqlcmd = self.mssql_sql_select_pacjent
        sqlcmd = sqlcmd.format(**row)
        self.logger.debug('Pobieram informacje o zleceniu dla aparatu')    
        return self._mssql_execute(sqlcmd)
    
    def _mssql_wstaw_wynik(self, **kwargs):
        """
        kwargs = row_wg_wzoru
        """
        row = kwargs
        if not self._conn_mssql.connected:
            self._mssql_connect()
        self._conn_mssql.select_db(config.COMDATA)
        sqlcmd = self.mssql_sql_insert_wyniki
        sqlcmd = sqlcmd.format(**row)
        try:
            self._mssql_execute(sqlcmd)
            self._sqlite_update_wyniki_jako_wyslane(**row)
        except Exception as e:
            self.logger.error('Błąd wysyłania wyniku do mssql')
            self.logger.error(e)
            pass
       
        
    def _pobierz_obrazek(self, sciezka):
        """
        Pobiera obrazek z komputera ipu
        Zmienia format i zamienia na string taki jak może wejść do mssql

        Args:
            sciezka: ścieżka do obrazka

        Returns:
            obrazek: obrazek w formie gotowej do wrzucenia do bazy

        Raises:
            KeyError: Raises an exception.
        """
        self.logger.debug('Pobieram obrazek z dysku sieciowego')    
        img = Image.open(sciezka) # ścieżka obrazka pod indeksem wyniku
        img = img.convert('L')
        img = ImageOps.invert(img)
        img = img.convert('1')
        img = img.save('img/diff.bmp')

        with open('img/diff.bmp', 'rb') as f:
            obrazek = f.read()
            obrazek = '0x'.encode('ascii') + binascii.hexlify(obrazek)
            obrazek = obrazek.decode()
            return obrazek
    
    def _mssql_wstaw_obrazek(self, **kwargs):
        """
        kwargs = row_wg_wzoru
        """
        row = kwargs
        if not self._conn_mssql.connected:
            self._mssql_connect()
        self._conn_mssql.select_db(config.DB_NAME)
        sqlcmd = self.mssql_sql_select_table_wyniki
        sqlcmd = sqlcmd.format(**row)
        id_tabeli_wynikow = self._mssql_execute(sqlcmd) 
        if id_tabeli_wynikow:
            id_tabeli_wynikow = id_tabeli_wynikow[0]['ID_TABELI'] 
            sciezka = row['wynik']
            try:
                obrazek = self._pobierz_obrazek(sciezka)
                sqlcmd = self.mssql_sql_insert_obrazek
                sqlcmd = sqlcmd.format(obrazek=obrazek,
                                   id_tabeli_wynikow=id_tabeli_wynikow)
                self._mssql_execute(sqlcmd)
                self.logger.debug('Wstawiłem obrazek do bazy')
                self._sqlite_update_wyniki_jako_wyslane(**row)
            except IOError as e:
                self.logger.error('Brak pliku lub dostępu do zasobów sieciowych')
                self.logger.error(e)
                self._sqlite_update_wyniki_jako_wyslane(**row)
                pass
             
        else:
            self.logger.error('Błąd numeru zlecenia, nie wstawiam wyniku obrazkowego')    
    
    def wyslanych(self):
        return ObslugaBaz.wyslanych_v
    
    def wynikow_do_wyslania(self):
        return ObslugaBaz.wynikow_do_wyslania_v

    def wyslij_jeden_wynik_do_mssql(self):
        """
        pobiera jeden wynik z sqlite do wprowadzenia do bazy.
        wykorzystuje zapytanie które zwraca listę wszystkich wyników,
        można zoptymalizować i napisać nowe funkcje
        """
        rows = None
        rows = self._sqlite_pobierz_wyniki_niewstawione()
        
        if rows:
            self.wynikow_do_wyslania = len(rows)
            row = rows[0]
            self._mssql_wstaw_wynik(**row)
            ConsoleGui.wynikow_lokalnie = len(self._sqlite_execute(self.sqlite_sql_select_niewstawione))
            ConsoleGui.wynikow_wyslanych += 1
            self.logger.debug('Pozostałych wyników tekstowych do wstawienia: {ilosc}'.format(
                            ilosc=len(rows)-1))    
        else:
            rows = self._sqlite_pobierz_obrazki_niewstawione()
            if rows:
                row = rows[0]
                self._mssql_wstaw_obrazek(**row)
                ConsoleGui.wynikow_lokalnie = len(self._sqlite_execute(self.sqlite_sql_select_niewstawione))
                ConsoleGui.wynikow_wyslanych += 1
                self.logger.debug('Pozostałych obrazów do wstawienia: {ilosc}'.format(
                            ilosc=len(rows)-1))    
