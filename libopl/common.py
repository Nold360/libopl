#!/usr/bin/env python3
###
# Shared functions
from os import path
from pathlib import Path

import ctypes
import configparser
import unicodedata
import re
import sys


def is_file(filepath):
    return path.isfile(filepath)

def is_dir(dirpath):
    return path.isdir(dirpath)

def exists(filepath):
    if is_dir(filepath) or is_file(filepath):
        return True
    return False

# Read configuration file
######
# Configuration Class for libopl
# Reads config file located at /home/$(whoami)/.config/opl.ini
#
def config(section, key, filepath=str(Path.home())+"/.config/opl.ini"):
    if is_file(filepath):
        config = configparser.ConfigParser()
        try:
            config.read(filepath)
            return config[section][key]
        except Exception as e:
            print("Error: Couldn't read config file %s" % filepath)
            print(e)
            return None
    return None


"""
Normalizes string, **DOESN'T** converts to lowercase, removes non-alpha characters,

Stolen from: https://docs.djangoproject.com/en/2.1/ref/utils/#django.utils.text.slugify
"""
def slugify(value, allow_unicode=False):
        value = str(value)
        if allow_unicode:
            value = unicodedata.normalize('NFKC', value)
        else:
            value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
            value = re.sub(r'[^\w\s-]', '', value).strip()#.lower()
            #return re.sub(r'[-\s]+', '_', value)
            return value


'''
//Original CRC32-Function from OPL-Sourcecode:

unsigned int USBA_crc32(char *string)
{
    int crc, table, count, byte;

    for (table = 0; table < 256; table++) {
        crc = table << 24;

        for (count = 8; count > 0; count--) {
            if (crc < 0)
                crc = crc << 1;
            else
                crc = (crc << 1) ^ 0x04C11DB7;
        }
        crctab[255 - table] = crc;
    }

    do {
        byte = string[count++];
        crc = crctab[byte ^ ((crc >> 24) & 0xFF)] ^ ((crc << 8) & 0xFFFFFF00);
    } while (string[count - 1] != 0);

    return crc;
}
'''

# ^ That function in shitty python
# Generate crc32 from game title for ul.cfg
def usba_crc32(string):
    crctab = [0] * 1024
    crc = ctypes.c_int32()
    for table in range(0,256):
        crc = (table << 24)

        for i in range(8,0,-1):
            crc = ctypes.c_int32(crc).value
            if ((crc)) < 0:
                crc = (crc << 1)
            else:
                crc = (crc << 1) ^ 0x04C11DB7
        crctab[255 - table] = ctypes.c_uint32(crc).value
    
    c=0
    string=string+"\0"
    while c < len(string):
        crc = ctypes.c_uint32(crctab[ord(string[c]) ^ ((crc >> 24) & 0xFF)] \
                ^ ((crc << 8) & 0xFFFFFF00)).value
        c+=1
    return ctypes.c_uint32(crc).value


