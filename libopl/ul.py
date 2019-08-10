#!/usr/bin/env python3
#from game import ULGameImage
from common import usba_crc32
from game import ULGameImage

# single game in ul.cfg / on filesyystem?
# ul.cfg is binary
# 64byte per game
class ULConfigGame():
    filedir = None

    ######### Fields in ul.cfg per game (always 64byte)
    # 32byte - Title/Name of Game
    name = '\0' * 32

    # 22byte - region_code is "ul." + OPL_ID (aka ID/Serial of game)
    region_code = None

    # 2byte - Number of file chunks / parts 
    parts = None

    # 2byte - media type?! so DVD/CD?...
    media = '\0' * 2

    # 2byte - This guy is unknown according to usbutil..
    unknown = '\0' * 2

    # 15byte - Also unused afaik
    remains = '\0' * 15

    ######### This CRC32-Hash is used for the ul-filenames 
    # By hashing the "name"-bytes OPL finds the files, 
    # that belong to a specific game
    crc32 = None

    # For Game object
    game = None

    def __init__(self, data=None, game=None):
        # data = from ul.cfg
        if data:
            self.name = data[:32].decode("utf-8") 
            self.region_code = data[32:46].decode("utf-8") 
            self.parts = bytes([data[47]])
            self.media = bytes([data[48]])
            self.unknown = bytes([data[49]]).decode("utf8")
            self.remains = data[49:64].decode("utf-8")

            self.opl_id = self.region_code[2:]
        # Create ul.cfg-entry for new game
        elif game:
            self.game = game
            self.name = self.game.get("title")[:32]
            self.opl_id = self.game.get("opl_id")
            self.region_code = "ul." + self.opl_id
            self.parts = int(self.game.get("parts"))
            #FIXME: static media type.. matters?
            self.media = b'\x14'
            self.unknown = b'\x00'
        else: 
            return None
        #Generate CRC32 from title
        self.crc32 = hex(usba_crc32(self.name))

    # returns byte string + \0 padding defined by "size"
    # converts string to bytestring if required
    def __get_bytes(self, data, size):
        if isinstance(data, int):
            data = chr(data)
        if isinstance(data, str):
            data = bytes(data, 'utf-8')
        return data.ljust(size, b'\0')

    # Get binary config data, with padding to 64byte
    def get_binary_data(self): 
        assert self.name
        assert self.region_code
        assert self.parts
        assert self.media

        # FIXME: for var: if ! byte(var): get_bytes(var)
        print(self.region_code)
        data =  self.__get_bytes(self.name.strip(), 32)
        data += self.__get_bytes(self.region_code.strip(), 14)
        data += self.__get_bytes(self.unknown, 1)
        data += self.__get_bytes(self.parts, 1)
        data += self.__get_bytes(self.media, 1)
        data += self.__get_bytes(self.remains, 12)

        return data.ljust(63, '\x00'.encode('utf-8'))

        
# ul.cfg handling class
class ULConfig():
    # Hasharray:
    #  OPL_ID: <ULConfigGame>
    ulgames = {}
    filepath = None

    # Generate ULconfig using ULGameConfig objects
    # Or Read ULConfig from filepath
    def __init__(self, filepath=None, ulgames=None):
        if ulgames:
            self.ulgames = ulgames

        if filepath:
            self.filepath = filepath

    # Add / Update Game using Game object
    def add_game(self, game):
        self.ulgames.update({"ul."+game.get("id"): game.ulcfg})

    # Add / Update Game using ul_ID & ULGameConfig object
    def add_ulgame(self, ul_id, ulgame):
        self.ulgames.update({ul_id: ulgame})

    # Print debug data
    def dump(self):
        print("Filepath: " +  str(self.filepath))
        print("ULGames:")
        for game in self.ulgames:
            print(" [%s] %s " % (str(game), str(self.ulgames[game].name)))
    
    # Read ul.cfg file
    def read(self):
        try:
            with open(self.filepath, 'rb') as data:
                while True:
                    game_cfg = data.read(64)
                    if len(game_cfg) == 0: break
                    game = ULConfigGame(game_cfg)
                    self.ulgames.update({game.region_code: game})
        except Exception as e:
            print("Ooops: ")
            print(e)
            return False
        return True

    # Write back games to ul.cfg
    def write(self):
        if not self.filepath: return False
        with open(self.filepath, 'wb+') as cfg:
            for id in self.ulgames:
                cfg.write(self.ulgames[id].get_binary_data())
        return True
