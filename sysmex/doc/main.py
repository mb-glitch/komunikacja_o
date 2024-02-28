# -*- coding: utf-8 -*-
#
"""
Maciej Bilicki
program służy do odbiory zleceń z plików .ord
pliki znajdują się w katalogu
wymiana plików podlega innemu mechanizmowi (najchętniej pscp i scp i ssh)
wersja: 0.1
"""

import os
import codecs


if __name__ == "__main__":
    files = [f for f in os.listdir()]
    files.sort(key=lambda x: os.path.getmtime(x))
    a = open('listawysylek', 'w+')

    for f in files:
        with codecs.open(f, "r", "iso-8859-1") as sourceFile:
            contents = sourceFile.readline()
            while contents:
                #print(contents)
                if 'Odebra³em: ' in contents and not '<ACK>' in contents:
                    contents = contents[contents.find('<'):]
                    a.write(contents)
                contents = sourceFile.readline()




