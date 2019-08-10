#!/usr/bin/env python3
###
# Game Class
# 
from common import usba_crc32, slugify
from os import path

import re

class Game():
    # constant values for gametypes
    UL = 0
    ISO = 1
    type = None
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
    id_regex = re.compile(r'[a-zA-Z]{4}.?\d{3}\.?\d{2}')

    # Recover generate id from filename
    def __init__(self, filepath=None, id=None, recover_id=True):
        if filepath:
            self.set("filepath", filepath)
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
      self.set("opl_id", oplid.upper())
      return oplid.upper()

    # Set missing attributes using api metadata
    def set_metadata(self, api, override=False):
        if not self.get("meta"):
            if not self.get("id"):
                return False

            meta = api.get_metadata(self.get("id"))
            if meta:
                self.set("meta", meta)
            else:
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
                self.set("title", slugify(self.get("meta")["name"][:64]))
            except: pass
            
        self.set("filename", self.get("opl_id") + "." + self.get("title"))

        return True 
        #new_filename = self.filename[:64-len(".iso")]
        #self.new_filename = new_filename

    # Getting usefill data from filename
    # for ul & iso names
    def get_common_filedata(self):
        if '/' in self.get("filepath"):
            self.set("filename", path.basename(self.get("filepath")))
            self.set("filedir", path.dirname(self.get("filepath")))

        if re.match(r'.*\.iso$', self.get("filename")):
            self.set("filetype", "iso")

        try:
            self.set("id", self.id_regex.findall(self.get("filename"))[0])
            self.gen_opl_id()
        except:
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
    ulcfg = None
    type = Game.UL

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
        self.type = Game.UL

        # Call func from super
        self.get_common_filedata()

        # Pattern: ul.{CRC32(title)}.{OPL_ID}.{PART}
        parts = self.get("filename").split('.')
        self.set("crc32", parts[1])

        # Trim Title to 32chars
        self.set("title", self.get("title")[:32])
        
        #self.crc32 = usba_crc32(self.title)
        return True

    # (Split) ISO into UL-Format
    def to_UL(self, dest_path):
        file_part = 0
        with open(self.get("filepath"), 'rb') as f:
            chunk = f.read(ULGameImage.CHUNK_SIZE)
            while chunk:
                filename =  '%s/ul.%s.%s.%.2X' %( dest_path, \
                    self.get("crc32")[2:].upper(), self.get("opl_id"), file_part)

                print("Writing File '%s'..." % filename)
                with open(filename, 'wb') as outfile:
                    outfile.write(chunk)
                    file_part += 1 
                    chunk = f.read(ULGameImage.CHUNK_SIZE)
        self.set("parts", file_part)
        return file_part

####
# Class for ISO-Games (or alike), child-class of "Game"
class IsoGameImage(Game):
    type = Game.ISO
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

        self.get_common_filedata()

        # FIXME: Better title / id sub
        self.set("title", self.id_regex.sub('', self.get("filename")))
        self.set("title", self.get("title").replace("."+self.get("filetype"), ''))
        self.set("title", self.get("title").strip('._-\ '))
        self.set("filename", self.get("filename").replace("."+self.get("filetype"), ''))
        self.set("crc32", hex(usba_crc32(self.get("title"))))
