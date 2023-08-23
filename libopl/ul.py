#!/usr/bin/env python3
#from game import ULGameImage
import os
from typing import Dict
from enum import Enum
from pathlib import Path
from libopl.common import usba_crc32

class ULMediaType(Enum):
    CD = b'\x12'
    DVD = b'\x14'

# single game in ul.cfg / on filesystem
# ul.cfg is binary
# 64byte per game
class ULConfigGame():
    filedir: Path = None

    ######### Fields in ul.cfg per game (always 64byte)
    # 32byte - Title/Name of Game
    name: bytes

    # 14byte - region_code is "ul." + OPL_ID (aka ID/Serial of game)
    region_code: bytes

    # 1byte - According to USBUtil, "DESC"
    unknown: bytes
    # 1byte - Number of file chunks / parts 
    parts: bytes

    # 1byte - media type?! so DVD/CD?...
    media: ULMediaType

    # 15byte - According to USBUtil, simply named "Information"
    remains: bytes

    ######### This CRC32-Hash is used for the ul-filenames 
    # By hashing the "name"-bytes OPL finds the files, 
    # that belong to a specific game
    crc32 = None

    # For Game object
    game = None

    def __init__(self,filedir,data):
        from libopl.game import ULGameImage 
        self.filedir = Path(filedir)
        self.name = bytes(data[:32])
        self.crc32 = hex(usba_crc32(self.name)).capitalize()
        self.region_code = bytes(data[32:46])
        self.unknown = bytes([data[46]])
        self.parts = bytes([data[47]])
        self.media = ULMediaType(bytes([data[48]]))
        self.remains = bytes(data[49:64])

        self.opl_id = self.region_code[3:]
        self.game = ULGameImage(ulcfg=self)

    # Get binary config data, with padding to 64byte
    def get_binary_data(self): 
        assert self.name
        assert self.region_code
        assert self.parts
        assert self.media

        data = self.name[:32] + \
               self.region_code + self.unknown + self.parts + self.media.value + self.remains

        return data.ljust(64, b'\x00')

        
# ul.cfg handling class
class ULConfig():
    ulgames: Dict[bytes, ULConfigGame] = {}
    filepath: Path = None

    # Generate ULconfig using ULGameConfig objects
    # Or Read ULConfig from filepath
    def __init__(self, filepath=None, ulgames=None):
        if ulgames:
            self.ulgames = ulgames
        elif filepath:
            self.filepath = filepath
            self.read()

    # Add / Update Game using Game object
    def add_game(self, game):
        self.ulgames.update({"ul."+game.id: game.ulcfg})

    # Add / Update Game using ul_ID & ULGameConfi/g object
    def add_ulgame(self, ul_id: str, ulgame: ULConfigGame):
        self.ulgames.update({ul_id: ulgame})

    # Print debug data
    def print_data(self):
        print("Filepath: " +  str(self.filepath))
        print("ULGames:")
        for game in self.ulgames:
            print(f" [{str(game)}] {str(self.ulgames[game].name)} ")
    
    # Read ul.cfg file
    def read(self):
            with open(self.filepath, 'rb') as data:
                game_cfg = data.read(64)
                while game_cfg:
                    game = ULConfigGame(data=game_cfg, filedir=os.path.dirname(self.filepath))
                    self.ulgames.update({game.region_code: game})
                    game_cfg = data.read(64)

        # return True

    # Write back games to ul.cfg
    def write(self):
        with open(self.filepath, 'wb+') as cfg:
            for game in self.ulgames.values():
                cfg.write(game.get_binary_data())
