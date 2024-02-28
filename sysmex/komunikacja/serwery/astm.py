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
import socket
import select
import logging

import komunikacja.ustawienia as config
from komunikacja.gui import ConsoleGui

class ASTM:
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
    NAZWA_APARATU = ''
    AKTYWNY = 1
    NIEAKTYWNY = 0
    HOST = ''
    PORT = 0
    CONN_IN_WAITING = 1  # parametr do listen()
    LOOP_TIMEOUT = 0.01
    SELECT_TIMEOUT = 0.01
    READ_TIMEOUT = 2
    CONN_TIMEOUT = 2
    DELAY = 5

    RAMKA_ROZMIAR_MAX = 233 # 240 - 6 znaków stx etx suma i crlf

    serwer = False
    klient = False
    parser = None
    
    def __init__(self, ob):

        self.logger = logging.getLogger('kom.SerwerASTM')
        self.logger.info('Inicjalizuje nowy serwer astm')
        self.soc, self.conn, self.addr = None, None, None
        self.zajety, self.odbieram, self.wysylam = False, False, False
        self.mam_wiadomosc = False
        self.czeka_na_ack = False
        self.blad_odbioru = False
        self.inbuffer = []
        self.outbuffer = []
        self.cleaned_data = []
        self.connected_v = False
        self.time_point = time.time()
        self.time_conn = time.time()
        self.delay = 0 # pierwsze połączenie bez opóźnienia    
        self.ob = ob
        ConsoleGui.stan_aparatu((self.NAZWA_APARATU, self.connected_v, 
                        self.zajety, self.wysylam, self.odbieram))



    def loop(self):
        time.sleep(self.LOOP_TIMEOUT)
        serv_list = []
        if self.serwer:
            if not self.soc: self._serve()
            serv_list.append(self.soc)
        if self.klient and not self.conn:
            self.connect()
        if self.conn: 
            ConsoleGui.stan_aparatu((self.NAZWA_APARATU, self.connected_v, 
                        self.zajety, self.wysylam, self.odbieram))
            serv_list.append(self.conn)
        else:
            ConsoleGui.stan_aparatu((self.NAZWA_APARATU, self.connected_v, 
                        self.zajety, self.wysylam, self.odbieram))
        # sprawdzam czy jest coś do odczytania lub wysłania
        if not serv_list:
            return
        readable, writeble, exceptional = select.select(
                serv_list, 
                serv_list, 
                [],
                self.SELECT_TIMEOUT
                )
        # na wszelki wypadek resetuje ustawienia zajętości jeżeli nie ma nic do zrobienia
        if self.conn not in readable and not self.outbuffer and not self.inbuffer:
            if not self.odbieram and not self.wysylam:
                self.zajety = False
        if self.soc in readable:
            self._handle_connect()
        if self.conn in readable:
            self.zajety, self.odbieram = True, True
            ConsoleGui.stan_aparatu((self.NAZWA_APARATU, self.connected_v, 
                        self.zajety, self.wysylam, self.odbieram))
            self._handle_receive(self._receive())
        if self.conn in writeble and self.outbuffer and not self.odbieram:
            self.zajety, self.wysylam = True, True
            ConsoleGui.stan_aparatu((self.NAZWA_APARATU, self.connected_v, 
                        self.zajety, self.wysylam, self.odbieram))
            self._handle_send()
        if self.mam_wiadomosc:
            self.analizuj_wiadomosc_serwera()

    def analizuj_wiadomosc_serwera(self):
        parser = self.parser(self.ob)
        for line in self.wiadomosc:
            parser.consume(line)
        parser.analizuj()
        if parser.wyniki:
            for wynik in parser.wyniki:
                self.ob.sqlite_wstaw_wynik(**wynik)
        if parser.odpowiedz:
            self.send(parser.odpowiedz)

    def _serve(self):
        self.soc, self.conn, self.addr = None, None, None
        self.soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.soc.bind((self.HOST, self.PORT))
        self.soc.listen(self.CONN_IN_WAITING)
        self.soc.setblocking(0)  # set non blocking

    def delay_connection(self):
        if self.delay > self.time_conn - self.time_point:
            self.time_conn = time.time()
            return True
        else:
            self.time_point = time.time()
            self.delay += self.DELAY
            return False

    def connect(self):
        if self.delay_connection():
            return
        try:
            self.logger.info('Czekam na połączenie...')
            self.conn = socket.create_connection((self.HOST, self.PORT), timeout=self.CONN_TIMEOUT)
            self.logger.info('Połączono z {addr}'.format(addr=self.conn.getpeername()[0]))
            self.connected_v = True
            self.delay = self.DELAY
        except Exception as e:
            self.logger.info('Nie udało się nawiązać połączenia. Błąd: {}'.format(e))
            #print(e)
            if self.conn:
                self._close()
            else:
                self.connected_v = False

    def _handle_send(self):
        do_wyslania = self.outbuffer.pop(0)
        self._send_frame(do_wyslania)
        if do_wyslania == config.EOT:  # nie wymaga potwierdzania otrzymania eot
            self.zajety, self.wysylam = False, False
            return
        data = self._receive()
        while data == config.NAK:
            self._send_frame(do_wyslania)
            data = self._receive()
        if do_wyslania == data == config.ENQ: # wymuszenie przesylania przez aparat
            self.outbuffer.insert(0, do_wyslania)
            self.wysylam = False
            return
        if self.outbuffer and data == config.ACK:
            return
        else:
            self.logger.error('Błąd przy wysyłaniu')
            self.zajety, self.wysylam = False, False
            self.outbuffer = []
            return

    def _handle_receive(self, data):
        if not data:
            self._close
            return
        elif data == config.NULL:
            self._close
            return
        elif data == config.ENQ:
            self.zajety, self.odbieram = True, True
            poprawna_ramka = True
            self.inbuffer = []
        elif data == config.EOT:
            self.zajety, self.odbieram = False, False
            self._analizuj()
            self.logger.debug('Koniec wiadomości')
            return
        elif data == config.ACK:
            return
        else:
            poprawna_ramka = self._czy_ramka_poprawna(data)
        if poprawna_ramka:
            self.zajety, self.odbieram = True, True
            self.logger.debug('Odebrałem poprawną ramkę')
            self._send_frame(config.ACK)
            if data not in [config.ENQ]:
                self.inbuffer.append(data)
        else:
            while data:
                if len(data) == 1:
                    chunk, data = data[0], None
                    self._handle_receive(chunk)
                elif data.startswith(config.STX) and config.CRLF in data:
                    self.logger.debug('Odebrałem błędną ramkę2')
                    crlf = data.find(config.CRLF) + 2  # +2 bo potrzebuje kawałek stringu razem z crlf
                    chunk, data = data[:crlf], data[crlf:] 
                    self.zajety, self.odbieram = True, True
                    self._handle_receive(chunk)
                elif data[0] == data[-1] == config.ENQ:
                    data = None
                    self._handle_receive(config.ENQ)
                else:
                    chunk, data = data[0], data[1:]
                    if chunk in [config.ACK, config.ENQ, config.EOT]:
                        self._handle_receive(chunk)
                    else:
                        self.logger.debug('Odebrałem błędną ramkę')
                        self._send_frame(config.NAK)
                        return
    
    def _handle_connect(self):
        try:
            self.conn, self.addr = self.soc.accept()
            self.conn.settimeout(self.READ_TIMEOUT)
            self.connected_v = True
            self.logger.info('Połączono z {addr}'.format(addr=self.addr))
        except Exception as e:
            self.logger.error('Nie udało się nawiązać połączenia')
            self.logger.error(e)
            self._close()
        
    def _close(self):
        try:
            self.logger.info('Zamykam połączenie')
            self.conn.close()
            self.conn, self.addr = None, None
            self.connected_v = False
            self.zajety, self.odbieram, self.wysylam = False, False, False
        except Exception as e:
            self.logger.error(e)
            self.logger.error('Nie udało się zamknąć połączenia')
            pass
    
    def _receive(self):
        """
        Odbiera dane z ustanowionego portu, w razie braku połączenia,
        próbuje je ponownie nawiązać i dalej czeka na dane

        Args:
            None 

        Returns:
            data: zwraca binarne dane odebrane z socket

        Raises:
            KeyError: Raises an exception.
        """
        self.logger.debug('Czekam na dane...')
        try:
            data = self.conn.recv(4096)
            self.logger.debug('Odebrałem: {data}'.format(data=config.translate(data.decode())))
            if not data:
                self._close()
            return data.decode()
        except Exception as e:
            self.logger.error(e)
            self._close()
    
    def _czy_ramka_poprawna(self, msg):
        """ Sprawdza czy ramka rozpoczyna i kończy się odpowiednimi znakami,
        wysyła odpowiednią część wiadomości do sprawdzenia sumy kontrolnej
        """
        if msg in [config.ACK, config.NAK, config.ENQ, config.EOT]:
            return True
        if not msg.startswith(config.STX) and msg.endswith(config.CRLF):
            return False
        if len(msg) < 7:
            return False        
        stx, frame, chck, crlf = msg[0], msg[1:-4], msg[-4:-2], msg[-2:] 
        suma_kontrolna = self._make_checksum(frame)
        if not suma_kontrolna == chck:
            self.logger.debug('Błędna suma kontrolna')
            self.logger.debug('Suma kontrolna: {suma}'.format(suma=suma_kontrolna))
            self.logger.debug('Ramka kontrolna: {frame}'.format(frame=config.translate(frame)))
            return False
        else:
            return True

    def _czy_ramka_podzielona(self, msg):
        """Checks plain msg for chunked byte."""
        length = len(msg)
        if len(msg) < 5:
            return False
        if config.ETB not in msg:
            return False
        return msg.index(config.ETB) == length - 5
    
    @property
    def _seq(self):
        seq = self.numeracja_ramek % 8 + 1        
        self.numeracja_ramek += 1
        return seq
    
    def _przygotuj_ramke_etx(self, data):
        """Przygotowuje ramkę do wysłania w wersji całej zakończonej ETX"""
        ramka = data
        frame = '{index}{ramka}{etx}'.format(index=self._seq,
                                            ramka=ramka,
                                            etx=config.ETX)
        chck = self._make_checksum(frame)
        ramka = '{stx}{frame}{chck}{crlf}'.format(stx=config.STX,
                                                frame=frame,
                                                chck=chck,
                                                crlf=config.CRLF)
        return ramka

    def _przygotuj_ramke_etb(self, data):
        """Przygotowuje ramkę do wysłania w wersji częsciowej zakończonej ETB"""
        ramka = data
        frame = '{index}{ramka}{etb}'.format(index=self._seq,
                                            ramka=ramka,
                                            etb=config.ETB)
        chck = self._make_checksum(frame)
        ramka = '{stx}{frame}{chck}{crlf}'.format(stx=config.STX,
                                                frame=frame,
                                                chck=chck,
                                                crlf=config.CRLF)
        return ramka

    def _przygotuj_ramke(self, data):
        """Przygotowuje ramkę do wysłania z listy wiadomości od parsera"""
        if not data:
            return data
        chunks = [data[i:i+self.RAMKA_ROZMIAR_MAX] \
                for i in range(0, len(data), self.RAMKA_ROZMIAR_MAX)]
        ile_ramek = len(chunks)
        lista_ramek = []
        if ile_ramek == 1:
            lista_ramek.append(self._przygotuj_ramke_etx(data))
            return lista_ramek
        else:
            i = 1
            for chunk in chunks:
                if i < ile_ramek:
                    lista_ramek.append(self._przygotuj_ramke_etb(chunk))
                    i += 1
                else:
                    lista_ramek.append(self._przygotuj_ramke_etx(chunk))
            return lista_ramek

    def _send_frame(self, ramka):
        """
        Wysyła dane do otwartego portu
        """
        ramka = ramka
        try:
            self.logger.debug('Wysyłam: {ramka}'.format(ramka=config.translate(ramka)))
            self.conn.sendall(ramka.encode())
            self.logger.debug('Wysłałem: {ramka}'.format(ramka=config.translate(ramka)))
        except Exception as e:
            self.logger.error('Wysyłam: {ramka}'.format(ramka=config.translate(ramka)))
            self.logger.error(e)
            self._close()

    def send(self, data):
        """
        Przygotowuje wiadomość do wysłania w formie listy kolejnych komunikatów

        Args:
            data: string dane do wysłania do socket 

        Returns:
            None

        Raises:
            KeyError: Raises an exception.
        """
        self.zajety = True
        self.numeracja_ramek = 0
        data = data
        msg = []
        if type(data) in (list, tuple):
            msg.append(config.ENQ)
            for line in data:
                ramka = self._przygotuj_ramke(line)
                msg += ramka
            msg.append(config.EOT)
        self.outbuffer = msg

    def _make_checksum(self, msg):
        """Calculates checksum for specified message.
        :param msg: ASTM message.
        :type msg: bytes
        :returns: Checksum value that is actually byte sized integer in hex base
        :rtype: bytes
        """
        if not isinstance(msg[0], int):
            msg = map(ord, msg)
        return hex(sum(msg) & 0xFF)[2:].upper().zfill(2)
    
    def _analizuj(self):
        """Analizuje odebrane ramki, łączy jeżeli były rozdzielone,
        dekoduje z binarnego,
        nie zamienia na listę - podział po | i wysyła do cleand data
        """
        chunks = []
        for msg in self.inbuffer:
            #stx, frame_nr, frame, etxoretb, chck, crlf = msg[0], msg[1], msg[2:-5], \
            #        msg[-5:-4], msg[-4:-2], msg[-2:]
            #dlachecksumy = frame_nr + frame + etxoretb
            #if chck != self._make_checksum(dlachecksumy):
            #    self._send_frame(config.NAK)
            #    self.logger.warning('Błąd check sumy ramki wysyłam NAK')
            frame = msg[2:-5]
            if msg[-5] == config.ETB:
                chunks.append(frame)
            else:
                if chunks:
                    joined_chunks = ''.join(chunks)
                    frame = joined_chunks + frame
                    chunks = []
                self.cleaned_data.append(frame)
                self.mam_wiadomosc = True
        # self.logger.debug(self.cleaned_data)

    @property
    def wiadomosc(self):
        self.mam_wiadomosc = False
        wiadomosc = self.cleaned_data
        self.cleaned_data = []
        return wiadomosc
