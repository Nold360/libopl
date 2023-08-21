#!/usr/bin/env python3
###
# Game Class
# 
from libopl.common import usba_crc32, slugify, is_file, read_in_chunks
from enum import Enum
from os import path

import re

from libopl.ul import ULConfigGame

class GameType(Enum):
    UL = 1
    ISO = 2

class Game():
    # constant values for gametypes
    type: GameType = None
    ulcfg = None

    # (Meta-)data-dict for all the game data
    data = { 
        "filedir": None,
        "filename": None,
        "filetype": None,
        "filepath": None,
        "id": None,
        "opl_id": None,
        "artwork":None,
        "title": None,
        "crc32": None,
        "size": None,

        "src_title": None,
        "src_filename": None,

        # Data from API
        "meta": None
    }

    # Regex for game serial/ids 
    id_regex = re.compile(r'S[a-zA-Z]{3}.?\d{3}\.?\d{2}')

    # Recover generate id from filename
    def __init__(self, filepath=None, id=None, recover_id=True):
        if filepath:
            self.set("filepath", filepath)
            self.get_common_filedata(recover_id)
        if id:
            self.set("id", id)
            self.gen_opl_id()
            

    # get data, crc32 is generated on the fly from the game title
    def get(self, key):
        if key == "crc32":
            try: return hex(usba_crc32(self.data["title"]))
            except: return None
        try: return self.data.get(key)
        except: return None

    # Set data
    def set(self, key, value):
        self.data[key] = value

    # Dump all da stuff...
    def dump(self):
        print("\n----------------------------------------")
        print("OPL-ID:       " + str(self.get("opl_id")))
        print("Size (MB):    " + str(self.get("size")))
        print("Source Title: " + str(self.get("src_title")))
        print("New Title:    " + str(self.get("title")))
        print("Filename:     " + str(self.get("filename")))

        print("")
        print("Filetype:     " + str(self.get("filetype")))
        print("Filedir:      " + str(self.get("filedir")))
        print("CRC32:        " + str(self.get("crc32")))
        print("Type:         " + str(self))
        print("ID:           " + str(self.get("id")))
        print("Filepath:     " + str(self.get("filepath")))
        print("")
        
    
    # Generate Serial/ID in OPL-Format
    def gen_opl_id(self):
      oplid = self.get("id").replace('-', '_')
      oplid = oplid.replace('.', '')
      try: 
        oplid = oplid[:8] + "." + oplid[8:]
      except: 
        oplid = None
      self.set("opl_id", oplid)
      return oplid.upper()

    def recover_id(self):
        print('Trying to recover Media-ID...')
        f = open(self.get('filepath'), 'rb')
        for chunk in read_in_chunks(f):
            id = self.id_regex.findall(str(chunk))
            if len(id) > 0:
                print('Success: %s' % id[0])
                self.set('id', id[0])
                self.gen_opl_id()
                return id[0]
        return None

    # Set missing attributes using api metadata
    def set_metadata(self, api, override=False):
        if not self.get("id"):
            return False

        try:
            meta = api.get_metadata(self.get("id"))
            self.set("meta", meta)
        except:
            return False
        
        self.set("src_title", self.get("title"))
        if self.get("meta"):
            try:
                if not self.get("title") or override: self.set("title", self.get("meta")["name"][:64])
                if not self.get("id") or override: self.set("id", self.metadata["id"])
                if not self.get("opl_id") or override: self.set("opl_id", self.metadata["opl_id"])
            except: pass

        # Max iso filename length = 64
        # Max UL title length = 32
        # FIXME: dynmaic length of filetype 
        if override:
            try:
                self.set("title", slugify(self.get("meta")["name"][:32]))
            except: pass
            
        self.set("filename", self.get("opl_id") + "." + self.get("title"))

        return True 
        #new_filename = self.filename[:64-len(".iso")]
        #self.new_filename = new_filename

    # Getting usefill data from filename
    # for ul & iso names
    def get_common_filedata(self, recover_id=True):
        self.set("filename", path.basename(self.get("filepath")))
        self.set("filedir", path.dirname(self.get("filepath")))

        if re.match(r'.*\.iso$', str(self.get("filename"))):
            self.set("filetype", "iso")
            self.type = GameType.ISO

        # try to get id out of filename
        try:
            self.set("id", self.id_regex.findall(self.get("filename"))[0])
        except:
            #else try to recover
            self.recover_id()
        if not self.get('id'):
            return False

        self.gen_opl_id()
        self.set("size", path.getsize(self.get("filepath"))>>20)
        return True

    # Return self as UL/IsoGameImage when filetype/name matches
    def evolve(self):
        if self.get("filetype") == "iso":
            return self.to_IsoGameImage()
        elif not self.get("title"):
            return False
        elif re.match(r'^ul\.', self.get("title")):
            return self.to_ULGameImage()
        return False

    def to_ULGameImage(self):
        try: return ULGameImage(data=self.data)
        except: return None

    def to_IsoGameImage(self):
        try: return IsoGameImage(data=self.data)
        except: return None


####
# UL-Format game, child-class of "Game"
class ULGameImage(Game):
    # ULConfigGame object
    ulcfg: ULConfigGame
    type: GameType = GameType.UL
    crc32: str

    # Chunk size matched USBUtil
    CHUNK_SIZE = 1073741824

    # Generate ULGameImage from filepath, ulcfg, or raw (meta-)data
    def __init__(self, filepath=None, ulcfg=None, data=None):
        # From file
        if filepath:
            super().__init__(filepath=filepath)
            self.get_filedata()
        # FRom ul.cfg
        elif ulcfg:
            self.ulcfg = ulcfg
            self.set("opl_id", self.ulcfg.region_code.replace('ul.', ''))
            self.set("id", self.get("opl_id"))
            self.set("title", self.ulcfg.name)
            self.set("crc32", self.ulcfg.crc32)
            self.set("filename", "ul." + self.get("crc32").replace('0x', '').upper())
            self.set("filename", self.get("filename") + "." + self.get("opl_id") + ".00")
        # Evolved from Game-Class
        elif data:
            self.data = data
        else: return None

    # Try to parse a filename to usefull data
    def get_filedata(self):
        self.filetype = None

        # Pattern: ul.{CRC32(title)}.{OPL_ID}.{PART}
        parts = self.get("filename").split('.')
        self.set("crc32", parts[1])

        # Trim Title to 32chars
        self.set("title", self.get("title")[:32])
        
        #self.crc32 = usba_crc32(self.title)
        return True

    # (Split) ISO into UL-Format
    def to_UL(self, dest_path, force=False):
        file_part = 0
        with open(self.get("filepath"), 'rb') as f:
            chunk = f.read(ULGameImage.CHUNK_SIZE)
            while chunk:
                filename =  'ul.%s.%s.%.2X' % ( self.get("crc32")[2:].upper(), \
                            self.get("opl_id"), file_part)
                filepath = path.join(dest_path, filename)

                if is_file(filepath) and not force:
                    print("Warn: File '%s' already exists! Use -f to force overwrite." % filename)
                    return 0

                print("Writing File '%s'..." % filepath)
                with open(filepath, 'wb') as outfile:
                    outfile.write(chunk)
                    file_part += 1 
                    chunk = f.read(ULGameImage.CHUNK_SIZE)
        self.set("parts", file_part)
        return file_part

####
# Class for ISO-Games (or alike), child-class of "Game"
class IsoGameImage(Game):
    type = GameType.ISO
    # Create Game based on filepath
    def __init__(self, filepath=None, data=None):
        if filepath:
            super().__init__(filepath)
            self.get_filedata() 
        if data:
            self.data = data

    # Get (meta-)data from filename
    def get_filedata(self):
        self.set("filetype", "iso")

        # FIXME: Better title / id sub
        self.set("title", self.id_regex.sub('', self.get("filename")))
        self.set("title", self.get("title").replace("."+self.get("filetype"), ''))
        self.set("title", self.get("title").strip('._-\ '))
        self.set("filename", self.get("filename").replace("."+self.get("filetype"), ''))
        self.set("crc32", hex(usba_crc32(self.get("title"))))
