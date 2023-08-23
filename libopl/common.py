#!/usr/bin/env python3
###
# Shared functions
from os import path
from pathlib import Path

import ctypes
import configparser
import unicodedata
import re


def is_file(filepath):
    return path.isfile(filepath)

def is_dir(dirpath):
    return path.isdir(dirpath)

def exists(filepath):
    if is_dir(filepath) or is_file(filepath):
        return True
    return False

def read_in_chunks(file_object, chunk_size=1024):
    """Lazy function (generator) to read a file piece by piece.
    Default chunk size: 1k."""
    while True:
        data = file_object.read(chunk_size)
        if not data:
            break
        yield data

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


def path_to_ul_cfg(opl_dir: Path) -> Path:
    return opl_dir.joinpath('ul.cfg')

def get_iso_id(filepath: Path) -> str:
    id_regex = re.compile(r'S[a-zA-Z]{3}.?\d{3}\.?\d{2}')
    with open(filepath, 'rb') as f:
        for chunk in read_in_chunks(f):
            id = id_regex.findall(str(chunk))
            if len(id) > 0:
                return id[0]
    raise ValueError(f"Cannot find Game ID for ISO file '{filepath}'")

def ul_files_from_iso(src_iso: Path, dest_path: Path, force=False) -> int:
    CHUNK_SIZE = 1073741824

    file_part = 0
    with src_iso.open('rb') as f:
        chunk = f.read(CHUNK_SIZE)
        title = re.sub(r'.[iI][sS][oO]', '', src_iso.name)

        while chunk:
            crc32 = hex(usba_crc32(title.encode('ascii')))[2:].upper()
            game_id = get_iso_id(src_iso)
            part = hex(file_part)[2:4].zfill(2).upper()

            filename = f"ul.{crc32}.{game_id}.{part}"
            filepath = dest_path.joinpath(filename)

            if is_file(filepath) and not force:
                print(f"Warn: File '{filename}' already exists! Use -f to force overwrite.")
                return 0

            print(f"Writing File '{filepath}'...")
            with open(filepath, 'wb') as outfile:
                outfile.write(chunk)
                file_part += 1 
                chunk = f.read(CHUNK_SIZE)
    return file_part
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
def usba_crc32(name: bytes):
    name = name.strip(b'\x00')
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
    name += b'\x00'
    while c < len(name):
        crc = ctypes.c_uint32(crctab[name[c] ^ ((crc >> 24) & 0xFF)] \
                ^ ((crc << 8) & 0xFFFFFF00)).value
        c+=1
    return ctypes.c_uint32(crc).value


