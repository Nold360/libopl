#!/usr/bin/env python3
###
# Game Class
#
from functools import reduce
from pathlib import Path
from pyopl.common import REGION_CODE_REGEX_BYTES, get_iso_id, slugify, read_in_chunks, usba_crc32, REGION_CODE_REGEX_STR

import re
from typing import List
from enum import Enum
from os import path

class GameType(Enum):
    UL = "UL (USBExtreme)"
    ISO = "ISO"


class Game():
    # constant values for gametypes
    type: GameType = None
    global REGION_CODE_REGEX_BYTES
    ulcfg = None

    filedir: str
    filename: str
    filetype: str
    filepath: Path
    id: str
    opl_id: str
    title: str
    crc32: str
    size: float
    src_title: str
    src_filename: str
    meta: dict

    # Regex for game serial/ids

    # Recover generate id from filename
    def __init__(self, filepath):
        if filepath:
            self.filepath = Path(filepath)

    def __repr__(self):
        return f"""\n----------------------------------------
LANG=en_US.UTF-8OPL-ID:       {self.opl_id}
Size (MB):    {self.size} 
New Title:    {self.title} 
Filename:     {self.filename}

Filetype:     {self.filetype}
Filedir:      {self.filedir}
Type:         {self.type}
ID:           {self.id} 
Filepath:     {self.filepath}
"""

    def __str__(self):
        return f"[{self.opl_id}] {self.title}"

    def print_data(self):
        print(repr(self))

    # Generate Serial/ID in OPL-Format
    def gen_opl_id(self):
        oplid = self.id.replace('-', '_')
        oplid = oplid.replace('.', '')
        try:
            oplid = oplid[:8] + "." + oplid[8:]
        except:
            oplid = None
        self.opl_id = oplid
        return oplid.upper()

    def recover_id(self):
        with open(self.filepath, 'rb') as f:
            for chunk in read_in_chunks(f):
                id_matches: List[bytes] = REGION_CODE_REGEX_BYTES.findall(chunk)
                if id_matches:
                    self.id = id_matches[0].decode('ascii', 'ignore')
                    self.gen_opl_id()


####
# UL-Format game, child-class of "Game"


class ULGameImage(Game):
    # ULConfigGame object
    from pyopl.ul import ULConfigGame, ULConfig
    ulcfg: ULConfigGame
    filenames: List[Path]
    size: float
    type: GameType = GameType.UL
    crc32: str

    global REGION_CODE_REGEX_STR

    # Chunk size matched USBUtil
    CHUNK_SIZE = 1073741824

    # Generate ULGameImage from ulcfg
    def __init__(self, ulcfg: ULConfigGame):
        self.ulcfg = ulcfg
        self.opl_id = self.ulcfg.region_code.replace(
            b'ul.', b'').decode('utf-8')
        self.id = self.opl_id
        self.title = self.ulcfg.name.decode('utf-8')
        self.crc32 = self.ulcfg.crc32
        self.filenames = self.get_filenames()
        self.size = self.get_size()


    def get_filenames(self):
        if hasattr(self, "filenames"):
            return self.filenames
        else:
            crc32 = self.crc32[2:].upper()
            def part_format(part): return hex(part)[2:4].zfill(2).upper()

            self.filenames = [self.ulcfg.filedir.joinpath(
                f"ul.{crc32}.{self.id}.{part_format(part)}")
                    for part in range(0, int(self.ulcfg.parts[0]))]
            return self.filenames

    def get_size(self):
        if hasattr(self, "size"):
            return self.size
        else:
            self.size = reduce(lambda x, y: x + y.stat().st_size / (1024 ^ 2),
                               self.get_filenames(), 0)
            return self.size

    def is_ok(self) -> bool:
        for file in self.get_filenames():
            if not path.isfile(file):
                return False
        if len(self.title) > 32:
            return False
        return True

    def delete_files(self, opl_dir: Path) -> None:
        for file in self.get_filenames():
            file.unlink()
        for directory in ["ART", "CFG", "CHT"]:
            for file in opl_dir.joinpath(directory).glob(f"{self.id}*"):
                file.unlink()

    def __repr__(self):
        return f"""\n----------------------------------------
LANG=en_US.UTF-8OPL-ID:       {self.opl_id}
Size (MB):    {self.size} 
Title:    {self.title} 

Game type:     UL
Game dir:      {self.filedir}
CRC32:        {self.crc32}
ID:           {self.id} 
Filepath:     {self.filepath}
"""

####
# Class for ISO-Games (or alike), child-class of "Game"


class IsoGameImage(Game):
    type = GameType.ISO
    title: str
    filename: str
    crc32: str

    # Create Game based on filepath
    def __init__(self, filepath=None):
        if filepath:
            super().__init__(filepath)
            self.get_filedata()

    # Get data from filename
    def get_filedata(self) -> None:
        self.get_common_filedata()
        self.filetype = "iso"

        # FIXME: Better title / id sub
        self.title = REGION_CODE_REGEX_STR.sub('', self.filename)
        self.title = self.title.replace("."+self.filetype, '')
        self.title = self.title.strip('._-\ ')
        self.filename = self.filename.replace("."+self.filetype, '')

    # Getting useful data from filename
    # for iso names
    def get_common_filedata(self) -> None:
        self.filename = self.filepath.name
        self.filedir = self.filepath.parent

        self.filetype = "iso"
        self.type = GameType.ISO

        # try to get id out of filename
        if (res := REGION_CODE_REGEX_STR.findall(self.filename)):
            self.id = res[0]
        else:
            self.id = get_iso_id(self.filepath)

        if not self.id:
            return

        self.gen_opl_id()
        self.size = path.getsize(self.filepath) >> 20

    def delete_game(self, opl_dir: Path): 
        self.filepath.unlink()
        for directory in ["ART", "CFG", "CHT"]:
            for file in opl_dir.joinpath(directory).glob(f"{self.id}*"):
                file.unlink()