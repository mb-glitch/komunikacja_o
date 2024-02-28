# -*- coding: utf-8 -*-
#
import re
import unicodedata
from collections import OrderedDict

# baza
COMDATA = 'comdata'
DB_NAME = 'lab3000'
BAZA_MS = {
    'server':'192.168.2.110',
    'port':1433,
    #ms
    #'server':'127.0.0.1',
    #'port':11432,
    #bdl
    #'server':'127.0.0.1',
    #'port':11433,
    
   #'server':'192.168.0.128',
    #'port':1433,
    'user':'ADMIN',
    'password':'***',
    'database':DB_NAME,
    'charset':'cp1250'
    }

SQLITE_NAME = 'wyniki.db'
WYNIK_WZOR = OrderedDict(
        [
        ('id', ''),
        ('pid', ''),
        ('nazwa', 'DUMMY'),
        ('tid', 0),
        ('data', '2017-06-10 14:20:00'),
        ('typ_wyniku', ''),
        ('wynik', ''),
        ('wynik_numeryczny', ''),
        ('nadpisz', 'T'),
        ('id_aparatu', 0),
        ('wyslany', 0),
        ('obrazek', 0),
        ]
    )

#: ASTM specification base encoding.
ENCODING = 'latin-1'
#: NULL BIT
NULL = '\x00'
#: Message start token.
STX = '\x02'
#: Message end token.
ETX = '\x03'
#: ASTM session termination token.
EOT = '\x04'
#: ASTM session initialization token.
ENQ = '\x05'
#: Command accepted token.
ACK = '\x06'
#: Command rejected token.
NAK = '\x15'
#: Message chunk end token.
ETB = '\x17'
LF  = '\x0A'
CR  = '\x0D'
# CR + LF shortcut
CRLF = CR + LF
#: Record fields delimiter.
FIELD_SEP_BIN     = '\x7C' # |  #

#: Message records delimiter.
RECORD_SEP    = '\x0D' # \r #
#: Record fields delimiter.
FIELD_SEP     = '\x7C' # |  #
#: Delimeter for repeated fields.
REPEAT_SEP    = '\x5C' # \  #
#: Field components delimiter.
COMPONENT_SEP = '\x5E' # ^  #
#: Date escape token.
ESCAPE_SEP    = '\x26' # &  #


slownik = {
        NULL: '<NULL>',
        STX: '<STX>',
        ETX: '<ETX>',
        EOT: '<EOT>',
        ENQ: '<ENQ>',
        ACK: '<ACK>',
        NAK: '<NAK>',
        ETB: '<ETB>',
        CR: '<CR>',
        LF: '<LF>',
        } 

def translate(tekst):
    if tekst == '':
        return '<NULL>'
    for k in slownik:
        if k in tekst:
            tekst = re.sub(k, slownik[k], tekst)
    return tekst

def retranslate(tekst):
    if tekst == '':
        return '<NULL>'
    for k in slownik:
        if slownik[k] in tekst:
            tekst = re.sub(slownik[k], k, tekst)
    return tekst

def slugify(value):
    """
    Converts to upperrcase, removes non-word characters (alphanumerics and
    underscores) and converts spaces to hyphens. Also strips leading and
    trailing whitespace.
    """
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub('[^\w\s-]', '', value).strip().upper()
    return re.sub('[-\s]+', '-', value)

