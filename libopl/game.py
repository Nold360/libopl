#!/usr/bin/env python3
###
# Game Class
# 
from functools import reduce
from pathlib import Path
from libopl.common import get_iso_id, slugify, read_in_chunks, usba_crc32

import re
from typing import List
from enum import Enum
from os import path
import os

class GameType(Enum):
    UL = "UL (USBExtreme)"
    ISO = "ISO"

class Game():
    # constant values for gametypes
    type: GameType = None

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
    id_regex = re.compile(r'S[a-zA-Z]{3}.?\d{3}\.?\d{2}')

    # Recover generate id from filename
    def __init__(self, filepath, id=None):
        if filepath:
            self.filepath = Path(filepath)
            self.get_common_filedata()
        if id:
            self.id = id
            self.gen_opl_id()

    def __repr__(self):
        return f"""\n----------------------------------------
LANG=en_US.UTF-8OPL-ID:       {self.opl_id}
Size (MB):    {self.size} 
Source Title: {self.src_title} 
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
        print('Trying to recover Media-ID...')
        with open(self.filepath, 'rb') as f:
            for chunk in read_in_chunks(f):
                id = self.id_regex.findall(str(chunk))
                if len(id) > 0:
                    print('Success: %s' % id[0])
                    self.id = id[0]
                    self.gen_opl_id()
                    return id[0]
        return None

    # Set missing attributes using api metadata, returns False if it fails,
    # True if it succeeds
    def set_metadata(self, api, override=False):
        if not self.id:
            return 
        try:
            meta = api.get_metadata(self.id)
            self.meta = meta
        except:
            return 
        
        self.src_title = self.title
        if self.meta:
            try:
                if not self.title or override: self.title = self.meta["name"][:64]
                if not self.id or override: self.id = self.metadata["id"]
                if not self.opl_id or override: self.opl_id = self.metadata["opl_id"]
            except: pass

        # Max iso filename length = 64
        # Max UL title length = 32
        # FIXME: dynmaic length of filetype 
        if override:
            try:
                self.title = slugify(self.meta["name"][:32])
            except: pass
            
        # self.filename = self.opl_id + "." + self.title

        return True 
        #new_filename = self.filename[:64-len(".iso")]
        #self.new_filename = new_filename

    # Getting usefill data from filename
    # for ul & iso names
    def get_common_filedata(self) -> None:
        self.filename = path.basename(self.filepath)
        self.filedir = path.dirname(self.filepath)

        if re.match(r'.*\.iso$', str(self.filename)):
            self.filetype = "iso"
            self.type = GameType.ISO

        # try to get id out of filename
        if (res := self.id_regex.findall(self.filename)):
            self.id = res[0]
        else:
            self.recover_id()

        if not self.id:
            return 

        self.gen_opl_id()
        self.size = path.getsize(self.filepath)>>20

####
# UL-Format game, child-class of "Game"
class ULGameImage(Game):
    # ULConfigGame object
    from libopl.ul import ULConfigGame
    ulcfg: ULConfigGame
    filenames: List[Path]
    size: float
    type: GameType = GameType.UL
    crc32: str

    # Chunk size matched USBUtil
    CHUNK_SIZE = 1073741824

    # Generate ULGameImage from ulcfg
    def __init__(self, ulcfg: ULConfigGame):
        self.ulcfg = ulcfg
        self.opl_id = self.ulcfg.region_code.replace(b'ul.', b'').decode('utf-8')
        self.id = self.opl_id
        self.title = self.ulcfg.name.decode('utf-8')
        self.crc32 = self.ulcfg.crc32
        self.filenames = self.get_filenames()
        self.size = self.get_size()
    
    def get_filenames(self):
        if hasattr(self, "filenames"):
            return self.filenames
        else:
            self.filenames = [self.ulcfg.filedir.joinpath( 
                                    f"ul.{self.crc32[2:].upper()}.{self.id}.{hex(part)[2:4].zfill(2).upper()}")
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
    
    def delete_files(self, opl_drive) -> None:
        for file in self.get_filenames():
            os.remove(file)

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

    # Get (meta-)data from filename
    def get_filedata(self) -> None:
        self.filetype = "iso"

        # FIXME: Better title / id sub
        self.title = self.id_regex.sub('', self.filename)
        self.title = self.title.replace("."+self.filetype, '')
        self.title = self.title.strip('._-\ ')
        self.filename = self.filename.replace("."+self.filetype, '')

    # (Split) ISO into UL-Format, returns number of parts
    #TODO: Build a good ISO to UL conversion pipeline, it's a bit weird atm
    def to_UL(src_iso: Path, dest_path: Path, force=False) -> int:
        file_part = 0
        with src_iso.open('rb') as f:
            chunk = f.read(ULGameImage.CHUNK_SIZE)
            title = re.sub(r'.[iI][sS][oO]', '', src_iso.name)

            while chunk:
                crc32 = hex(usba_crc32(title.encode('ascii')))[2:].upper()
                game_id = get_iso_id(src_iso)
                part = hex(file_part)[2:4].zfill(2).upper()

                filename = f"ul.{crc32}.{game_id}.{part}"
                filepath = dest_path.joinpath(filename)

                if filepath.is_file() and not force:
                    print(f"Warn: File '{filename}' already exists! Use -f to force overwrite.")
                    return 0

                print(f"Writing File '{filepath}'...")
                with open(filepath, 'wb') as outfile:
                    outfile.write(chunk)
                    file_part += 1 
                    chunk = f.read(ULGameImage.CHUNK_SIZE)
        return file_part
