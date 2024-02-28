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

class BiokselClientASTM:
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
    HOST = '192.168.2.102'
    PORT = 5002
    CONN_IN_WAITING = 1  # parametr do listen()
    LOOP_TIMEOUT = 0.1
    SELECT_TIMEOUT = 0.2
    READ_TIMEOUT = 2
    CONNECT_TIMEOUT = 0.1
    DELAY = 5

    RAMKA_ROZMIAR_MAX = 233 # 240 - 6 znaków stx etx suma i crlf

    def __init__(self):
        self.logger = logging.getLogger('kom.SerwerASTM')
        self.logger.info('Inicjalizuje nowy serwer astm')
        self.soc, self.conn, self.addr = None, None, None
        self.zajety = False
        self.mam_wiadomosc = False
        self.czeka_na_ack = False
        self.blad_odbioru = False
        self.inbuffer = []
        self.outbuffer = []
        self.cleaned_data = []
        self.numeracja_ramek = 1
        self.connected_v = False
        self.time_point = time.time()
        self.time_conn = time.time()
        self.delay = 0 # pierwsze połączenie bez opóźnienia
     
    def loop(self):
        serv_list = []
        if not self.soc:
            if not self.delay_connection():
                self.connect()
            #serv_list.append(self.soc)
        if self.soc:
            serv_list.append(self.soc)
        if self.conn: 
            serv_list.append(self.conn)
        if serv_list:
            readable, writeble, exceptional = select.select(
                    serv_list, 
                    serv_list, 
                    [],
                    self.SELECT_TIMEOUT
                    )
            if self.soc in readable:
                self.inbuffer = []
                self._handle_receive()
            if self.soc in writeble and self.outbuffer:
                self._handle_send()
    
    def delay_connection(self):
        if self.delay > self.time_conn - self.time_point:
            self.time_conn = time.time()
            return True
        else:
            self.time_point = time.time()
            self.delay += self.DELAY
            return False

    def _serve(self):
        self.soc, self.conn, self.addr = None, None, None
        self.soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.soc.bind((self.HOST, self.PORT))
        self.soc.listen(self.CONN_IN_WAITING)
        self.soc.setblocking(0)  # set non blocking
        print('Czekam na połączenie...')

    def connect(self):
        try:
            print('Czekam na połączenie...')
            self.soc = socket.create_connection((self.HOST, self.PORT), timeout=self.CONNECT_TIMEOUT)
            print('Połączono z {addr}'.format(addr=self.soc.getpeername()[0]))
            self.connected_v = True
            self.delay = self.DELAY
        except Exception as e:
            self.logger.info('Nie udało się nawiązać połączenia. Błąd: {}'.format(e))
            #print(e)
            if self.soc:
                self._close()
            else:
                self.connected_v = False

    def connected(self):
        return self.connected_v

    def _handle_send(self):
        do_wyslania = self.outbuffer.pop(0)
        self._send_frame(do_wyslania)
        if do_wyslania == config.EOT:  # nie wymaga potwierdzania otrzymania eot
            return
        data = self._receive()
        while data == config.NAK:
            self._send_frame(do_wyslania)
            data = self._receive()
        while self.outbuffer and data == config.ACK:
            self._handle_send()

    def _handle_receive(self):
        data = self._receive()
        if not data:
            self._close
            return
        elif data == config.ENQ:
            self._send_frame(config.ACK)
            self.zajety = True
            return
        elif data == config.EOT:
            # self._send_frame(config.ACK)  # specyfikacja nie wymaga potwierdzenia
            self.zajety = False
            self._analizuj()
            self.logger.debug('Koniec wiadomości')
            print('Koniec wiadomości')
            return
        elif data == config.ACK and not self.zajety:
            return
        poprawna_ramka = self._czy_ramka_poprawna(data)
        if not poprawna_ramka:
            self._send_frame(config.NAK)
            self._handle_receive()
            return
        while poprawna_ramka and self.zajety:
            self.logger.debug('Odebrałem poprawną ramkę')
            self.inbuffer.append(data)
            self._send_frame(config.ACK)
            self._handle_receive()
    
    def _handle_communication(self):
        data = self._receive()
        if not data:
            self._close
        elif data == config.ENQ:
            self._send_frame(config.ACK)
            self.zajety = True
            self.inbuffer = []
        elif data == config.EOT:
            self.zajety = False
            self._analizuj()
        elif data == config.ACK:
            self.czeka_na_ack = False
            self.zajety = True
        elif data == config.NAK:
            self.blad_odbioru = True
            self.zajety = True
        elif self._czy_ramka_poprawna(data) and self.zajety:
            self.logger.debug('Odebrałem pobrawną ramkę')
            self.inbuffer.append(data)
            self._send_frame(config.ACK)
        else:
            self._send_frame(config.NAK)
        
    def _close(self):
        try:
            print('Zamykam połączenie')
            self.logger.info('Zamykam połączenie')
            if self.soc:            
                self.soc.close()
            self.soc, self.conn, self.addr = None, None, None
            self.connected_v = False
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
            data = self.soc.recv(4096)
            self.logger.info('Odebrałem: {data}'.format(data=config.translate(data.decode())))
            print('Odebrałem: {data}'.format(data=config.translate(data.decode())))
            if not data:
                self._close()
            return data.decode()
        except:

            self._close()
    
    def _czy_ramka_poprawna(self, msg):
        """ Sprawdza czy ramka rozpoczyna i kończy się odpowiednimi znakami,
        wysyła odpowiednią część wiadomości do sprawdzenia sumy kontrolnej
        """
        if msg in [config.ACK, config.NAK, config.ENQ, config.EOT]:
            return True
        stx, frame, chck, crlf = msg[0], msg[1:-4], msg[-4:-2], msg[-2:] 
        if not msg.startswith(config.STX) and msg.endswith(config.CRLF):
            return False
        suma_kontrolna = self._make_checksum(frame)
        self.logger.debug('Suma kontrolna: {suma}'.format(suma=suma_kontrolna))
        self.logger.debug('Ramka kontrolna: {frame}'.format(frame=config.translate(frame)))
        if not suma_kontrolna == chck:
            self.logger.debug('Błędna suma kontrolna')
            return False  # bioksel nie wysyła sum kontrolnych
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
        seq = self.numeracja_ramek
        if self.numeracja_ramek < 8:        
            self.numeracja_ramek += 1
            return seq
        else:
            self.numeracja_ramek = 1
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
            self.soc.sendall(ramka.encode())
            self.logger.info('Wysłałem: {ramka}'.format(ramka=config.translate(ramka)))
            print('Wysłałem: {ramka}'.format(ramka=config.translate(ramka)))
        except Exception as e:
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
        self.numeracja_ramek = 1
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
            stx, frame_nr, frame, etxoretb, chck, crlf = msg[0], msg[1], msg[2:-5], \
                    msg[-5:-4], msg[-4:-2], msg[-2:]
            dlachecksumy = frame_nr + frame + etxoretb
            if chck != self._make_checksum(dlachecksumy):
                self._send_frame(config.NAK)
                self.logger.warning('Błąd check sumy ramki wysyłam NAK')
            elif etxoretb == config.ETB:
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
        wiadomosc = []        
        for line in self.cleaned_data:
            wiadomosc += line.split(config.RECORD_SEP)  
        # wiadomosc = self.cleaned_data
        self.cleaned_data = []
        return wiadomosc
