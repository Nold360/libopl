#!/usr/bin/env python3
###
# Python CLI Replacement for OPLManager
# 
from shutil import move, copyfile
from zlib import crc32

from artwork import Artwork
from api import API
from common import is_file, is_dir, exists
from game import Game, ULGameImage, IsoGameImage
from ul import ULConfig, ULConfigGame

import os
import re
import sys
import json
import argparse
import requests

## todo
# config file ~/.config/popl.yml
# recover media_id from iso file
# TODO: 
#   popl init /media/opl_drive!!!
class POPLManager:
    args = None
    api = None
    games = []

    def __init__(self, args=None):
        self.set_args(args)

    def set_args(self, args):
        self.args = args

    # Return: array of filepath's for all games on opl_drive
    def __get_opl_games(self, opl_drive, type="DVD"):
        path = os.path.join(opl_drive, type)
        games = []
        for f in os.listdir(path): 
            filepath = os.path.join(path, f)

            # Skip parts of ul-files
            if re.match(r'^ul\..*\.[0-9][1-9]$', f): continue
            if is_file(filepath):
                games.append(filepath)
        return games

    # Generate Game-object for every path in "source"-list
    def __get_games(self, source):
        for filepath in source:
            if re.match(r'.*/ul\..*0$', filepath):
                game = ULGameImage(filepath)
            elif re.match('.*\.iso$', filepath):
                game = IsoGameImage(filepath)
            else:
                print("ERROR: Couldn't determine filetype from '%s'" % filepath)
                continue

            game.set_metadata(self.api)
            self.games.append(game)

    # Download artwork CLI, duh
    # For every game in args.opl_drive
    def download_artwork(self, args):
        print("Searching Artwork...")
        if not self.api:
            self.api = API()
        self.__get_games(self.__get_opl_games(args.opl_drive))
        
        print(args.force)
        for game in self.games:
            if game.type != Game.UL:
                if not game.get("meta"):
                    meta = self.api.get_metadata(game.get("id"))
                    if meta:
                        game.set("meta", meta)
                self.api.download_artwork(game, args.opl_drive, override=args.force)

        print("\nReading ul.cfg...")
        if is_file(args.opl_drive + "/ul.cfg"):
            ulcfg = ULConfig(os.path.join(args.opl_drive, "ul.cfg"))
            ulcfg.read()
            ulcfg.dump()
            for ulgame in ulcfg.ulgames:
                game=ULGameImage(ulcfg=ulcfg.ulgames[ulgame])
                game.set("meta", self.api.get_metadata(game.get("opl_id")))
                game.set("artwork", self.api.get_artwork(game))
                game.dump()
                self.api.download_artwork(game, args.opl_drive, override=args.force)
        else:
            print("Skipped. No ul.cfg found on opl_drive.")
        return True

    # Add game(s) to args.opl_drive
    #  - split game if > 4GB / forced
    #  -  otherwise just copy with OPL-like filename
    #  - download metadata from api
    #  - rename game to title from api (if enabled)
    #  - download artwork
    def add(self, args):
        self.api = API()
        self.__get_games(args.src_file)

        for game in self.games:
            if not game.get_common_filedata():
                print("Error while parsing file: %s" % game.get("filepath"))
                continue

            if game.get("size") > 4000 or args.ul:
                print("Forced conversion to UL-Format...")
                game = game.to_ULGameImage()

            game.set_metadata(self.api, args.rename)

            # Show nerdy data
            game.dump()
            
            # UL Format, when splitting, or whatever...
            if game.type == Game.UL:
                print("Adding file in UL-Format...")
                game.to_UL(args.opl_drive)

                # Create OPL-Config for Game; read & merge ul.cfg
                game.ulcfg = ULConfigGame(game=game)
                cfg = ULConfig(os.path.join(args.opl_drive, "ul.cfg"), \
                        {game.get("opl_id"): game.ulcfg})

                print("Reading ul.cfg...")
                cfg.read()
                cfg.dump()

                print({game.get("opl_id"): game.ulcfg})
                print("Writing ul.cfg...")
                cfg.write()

                print("Done! - Happy Gaming! :)")

	    # Otherwise copy iso to opl_drive, optimizing the name for OPL
            else:
                if game.get("new_filename"):
                    filename = game.get("new_filename")
                else:
                    filename = game.get("filename")

                filename += "." + game.get("filetype")
                filepath = os.join.path(args.opl_drive, "DVD", filename)

                print("Copy file to " + str(filepath) + ", please wait...")
                copyfile(game.get("filepath"), filepath)
 
            
            # Finally download artwork
            print("Downloading Artwork...")
            self.api.download_artwork(game, args.opl_drive)
                
    def __get_data_from_api(self, title_id):
        if not self.api:
            self.api = API()
        return self.api.get_title_by_id(title_id)

    # Try fixing a OPL-Drive by:
    #  - Rename ISOs to {OPL-ID}.{title}.iso
    #  - Download missing artwork / overwrite existing
    def fix(self, args):
        self.api = API()
        self.__get_games(self.__get_opl_games(args.opl_drive))
        
        # FIXME: No merge, full overwrite..?
        self.ulcfg = ULConfig(os.path.join(args.opl_drive, "ul.cfg"))
        self.ulcfg.read()

        for game in self.games:
            if not game.get_common_filedata():
                print("Error while parsing file: %s" % game.get("filepath"))
                continue

            print("Fixing '%s'..." % game.get("filename"))

            if not game.get("id"):
                print("ID not found in file: '%s'" % game.get("filepath"))
                continue


            # Always use API to fix game names
            if not game.set_metadata(self.api, True):
                print("WARN: Couldn't get Metadata from API for '%s'" % game.filepath)

            # Generate OPL-ID & try evolving game-object to child class
            #game.gen_opl_id()
            tmp = game.evolve()
            if tmp:
                game = tmp
            game.dump()

            # Change filename?
            if not game.get("new_filename"):
                filename = game.get("filename")
            else:
                filename = game.get("new_filename")

            if isinstance(game, ULGameImage):
                # TODO: 
                #  - Search ul-games on disk
                #  - read ul.cfg
                #  - check existance of images, in ul.cfg
                #  - write fixed ul.cfg
                continue
                game.ulcfg = ULConfigGame(game=game) 
                cfg = (args.opl_drive+"/ul.cfg", {game.get("opl_id"): game.ulcfg})
           
            # Game already in correct format?
            if game.get("filename") == filename:
                print("Nothing to do...")
                continue

            # Move stuff
            print("Renaming: %s -> %s" %(game.get("filename"), filename))
            destfilepath=os.path.join(args.opl_drive, "DVD", filename + "." + game.get("filetype"))
            move(game.get("filepath"), destfilepath)

    # List all Games on OPL-Drive
    def list(self, args):
        print("Searching Games on %s:" % args.opl_drive)
        
        print("|-> ISO-Games:")
        # Find all game iso's
        for media_file in self.__get_opl_games(args.opl_drive, type="DVD"):
            game = Game(media_file)
            game.get_common_filedata()
            game = game.evolve()
            game.get_filedata()
#            game.gen_opl_id()

            if args.online:
                api = API()
                game.set_metadata(api, args.rename)
            
            if isinstance(game, IsoGameImage):
                print(" [%s] %s " %(game.get("opl_id"), game.get("title")))

        # Read il.cfg & output games
        ulcfg = ULConfig(args.opl_drive + "/ul.cfg")
        ulcfg.read()
        print("\n|-> UL-Games:")
        if ulcfg.ulgames != {}:
            for game in ulcfg.ulgames:
                print(" [%s] %s" % (game.replace('ul.', ''), ulcfg.ulgames[game].name))

    
        # Create OPL Folders / stuff
    def init(self, args):
        print("Inititalizing OPL-Drive...")
        for dir in ['APPS', 'ART', 'CD', 'CFG', 'DVD', 'THM']:
            if not is_dir(os.path.join(args.opl_drive, dir)):
                print(dir)
                os.mkdir(os.path.join(args.opl_drive, dir))
        print("Done!")
####
# Main
# 
# Parses arguments & calls function from POPLManager-object 
if __name__ == '__main__':
    opl = POPLManager()

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--foo', action='store_true')

    subparsers = parser.add_subparsers(help='Choose your path...')

    list_parser = subparsers.add_parser("list", help="List Games on OPL-Drive")
    list_parser.add_argument("--online", "-o" , help="Check for Metadata in API", action='store_true', default=False)
    list_parser.add_argument("opl_drive", help="Path to OPL - e.g. your USB- or SMB-Drive\nExample: /media/usb")
    list_parser.set_defaults(func=opl.list)

    add_parser = subparsers.add_parser("add", help="Add Media Image to OPL-Drive")
    add_parser.add_argument("--rename", "-r" , help="Rename Game by obtaining it's title from API", action='store_true')
    add_parser.add_argument("--ul", "-u" , help="Force UL-Game converting", action='store_true')
    add_parser.add_argument("opl_drive", help="Path to OPL - e.g. your USB- or SMB-Drive\nExample: /media/usb")
    add_parser.add_argument("src_file",nargs='+', help="Media/ISO Source File")
    add_parser.set_defaults(func=opl.add)

    art_parser = subparsers.add_parser("artwork", help="Download Artwork onto opl_drive")
    art_parser.add_argument("--force", "-f" , help="Force replacement of existing artwork", action='store_true')
    art_parser.add_argument("opl_drive", help="Path to OPL - e.g. your USB- or SMB-Drive\nExample: /media/usb")
    art_parser.set_defaults(func=opl.download_artwork)

    fix_parser = subparsers.add_parser("fix", help="rename/fix media filenames")
    fix_parser.add_argument("opl_drive", help="Path to OPL - e.g. your USB- or SMB-Drive\nExample: /media/usb")
    fix_parser.set_defaults(func=opl.fix)

    init_parser = subparsers.add_parser("init", help="Initialize OPL-Drive folder-structure")
    init_parser.add_argument("opl_drive", help="Path to OPL - e.g. your USB- or SMB-Drive\nExample: /media/usb")
    init_parser.set_defaults(func=opl.init)

    args = parser.parse_args()
    opl.set_args(args)

    if hasattr(args, 'opl_drive'):
        if not is_dir(args.opl_drive):
            print("Error: opl_drive directory doesn't exist!")
            sys.exit(1)
    
    if hasattr(args, 'func'):
        args.func(args)
    else: 
        parser.print_help(sys.stderr)
        sys.exit(1)
    sys.exit(0)
