#!/usr/bin/env python3
###
# Python CLI Replacement for OPLManager
#
from shutil import move, copyfile
from typing import List
from pathlib import Path
import glob

from libopl.api import API
from libopl.common import is_file, is_dir, path_to_ul_cfg 
from libopl.game import Game, ULGameImage, IsoGameImage, GameType
from libopl.ul import ULConfig, ULConfigGame

import os
import re
import sys
import argparse

# todo
# config file ~/.config/popl.yml
# recover media_id from iso file
# TODO:
#   popl init /media/opl_drive!!!


class POPLManager:
    args = None
    opl_drive: Path
    api = None
    games: List[Game] = []

    def __init__(self, args=None):
        self.set_args(args)

    def set_args(self, args):
        self.args = args

    # Return: array of filepath's for all games on opl_drive
    def __get_iso_game_files(self, type="DVD") -> List[Path]:
        path = Path(os.path.join(self.args.opl_drive, type))
        games = list(path.glob('*.[iI][sS][oO]'))
        return games

    def __get_all_iso_games(self) -> List[Game]:
        paths: List[Path] = self.__get_iso_game_files(
            "DVD") + self.__get_iso_game_files("CD")
        games: List[Game] = []
        for path in paths:
            game = IsoGameImage(str(path))
            game.set_metadata(self.api)
            games.append(game)
        return games

    def __get_all_ul_games(self) -> List[Game]:
        ul_cfg: ULConfig = ULConfig(
                 path_to_ul_cfg(self.args.opl_drive)
                )
        return [game_cfg.game for game_cfg in ul_cfg.ulgames.values()]

    # Generate Game-object for every path in "source"-list
    def __get_games(self, source: List[Path]):
        for filepath in source:
            game = IsoGameImage(str(filepath))
            game.set_metadata(self.api)
            yield game

    def __get_full_game_list(self) -> List[Game]:
        return self.__get_all_iso_games() + self.__get_all_ul_games()

    # Download artwork CLI, duh
    # For every game in args.opl_drive

    def download_artwork(self, args):
        print("Searching Artwork...")
        if not self.api:
            self.api = API()
        self.__get_games(self.__get_iso_game_files(args.opl_drive))

        for game in self.games:
            if game.type != GameType.UL:
                if not game.meta:
                    meta = self.api.get_metadata(game.id)
                    if meta:
                        game.meta = meta
                self.api.download_artwork(
                    game, args.opl_drive, override=args.force)

        print("\nReading ul.cfg...")
        if args.opl_drive.joinpath("ul.cfg").exists():
            ulcfg = ULConfig(os.path.join(args.opl_drive, "ul.cfg"))
            ulcfg.print_data()
            for ulgame in ulcfg.ulgames:
                game = ULGameImage(ulcfg=ulcfg.ulgames[ulgame])
                game.meta = self.api.get_metadata(game.opl_id)
                game.artwork = self.api.get_artwork(game)
                game.print_data()
                self.api.download_artwork(
                    game, args.opl_drive, override=args.force)
        else:
            print("Skipped. No ul.cfg found on opl_drive.")
        return True

    def delete(self, args):
        for game in self.__get_full_game_list():
            if game.opl_id == args.opl_id[0]:
                match game.type:
                    case GameType.UL:
                        print(f"Deleting {args.opl_id[0]}...")
                        ul_cfg = ULConfig(path_to_ul_cfg(args.opl_drive))
                        ul_cfg.ulgames.pop(game.ulcfg.region_code, None)
                        print("Adjusting ul.cfg...")
                        ul_cfg.write()
                        print('Deleting game chunks...')
                        game.delete_files(args.opl_drive)
                    case GameType.ISO:
                        if os.path.exists(fp := game.filepath):
                            print(f"Deleting {args.opl_id[0]}...")
                            os.remove(fp)

    # Add game(s) to args.opl_drive
    #  - split game if > 4GB / forced
    #  -  otherwise just copy with OPL-like filename
    #  - download metadata from api
    #  - rename game to title from api (if enabled)
    #  - download artwork
    def add(self, args):
        self.api = API()

        for game in self.__get_games(args.src_file):
            if not game.get('id'):
                print("Error while parsing file: %s" % game.filepath)
                continue

            if (game.size > 4000 and not args.iso) or args.ul:
                print("Forced conversion to UL-Format...")
                game = game.to_ULGameImage()

            game.set_metadata(self.api, args.rename)
            game.print_data()

            # UL Format, when splitting, or whatever...
            if game.type == GameType.UL:
                print("Adding file in UL-Format...")

                fileparts = game.to_UL(args.opl_drive, args.force)
                if fileparts == 0:
                    print("Something went wrong, skipping game '%s'!" %
                          game.get('filename'))
                    continue

                # Create OPL-Config for Game; read & merge ul.cfg
                game.ulcfg = ULConfigGame(game=game)
                cfg = ULConfig(os.path.join(args.opl_drive, "ul.cfg"),
                               {game.opl_id: game.ulcfg})

                print("Reading ul.cfg...")
                cfg.read()
                cfg.print_data()

                print("Writing ul.cfg...")
                cfg.write()

                print("Done! - Happy Gaming! :)")

            # Otherwise copy iso to opl_drive, optimizing the name for OPL
            else:
                if game.new_filename:
                    filename = game.new_filename
                else:
                    filename = game.filename

                filename += "." + game.filetype
                filepath = os.path.join(
                    args.opl_drive, "DVD" if game.size > 700 else "CD", filename)

                print("Copy file to " + str(filepath) + ", please wait...")
                if is_file(filepath) and not args.force:
                    print("Warn: File '%s' already exists! Use -f to force overwriting." %
                          game.get('filename'))
                    print('Skipping game...')
                    continue
                elif args.force:
                    print("Overwriting forced!")

                copyfile(game.filepath, filepath)

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
        self.__get_games(self.__get_iso_game_files(args.opl_drive))

        # FIXME: No merge, full overwrite..?
        self.ulcfg = ULConfig(args.opl_drive.joinpath("ul.cfg"))

        for game in self.__get_games(self.__get_iso_game_files(args.opl_drive)):
            if not game.get('id'):
                print(f"Error while parsing file: {game.get('filepath')}")
                continue

            print("Fixing '%s'..." % game.filename)

            if not game.id:
                print(f"ID not found in file: {game.get('filepath')}")
                continue

            # Always use API to fix game names
            # if not game.set_metadata(self.api, True):
            #     print("WARN: Couldn't get Metadata from API for '%s'" % game.filepath)

            # Generate OPL-ID
            game.gen_opl_id()

            game.print_data()

            # Change filename?
            if not game.new_filename:
                filename = game.filename
            else:
                filename = game.new_filename

            if isinstance(game, ULGameImage):
                # TODO:
                #  - Search ul-games on disk
                #  - read ul.cfg
                #  - check existance of images, in ul.cfg
                #  - write fixed ul.cfg
                game.ulcfg = ULConfigGame(game=game)
                cfg = (args.opl_drive.joinpath("ul.cfg"), {game.opl_id: game.ulcfg})

                # will override cfg for now if fixing stuff...

            # Game already in correct format?
            if game.filename == filename:
                print("Nothing to do...")
                continue

            # Move stuff
            print("Renaming: %s -> %s" % (game.filename, filename))
            destfilepath = os.path.join(
                args.opl_drive, "DVD", filename + "." + game.filetype)
            move(game.filepath, destfilepath)

    # List all Games on OPL-Drive
    def list(self, args):
        print("Searching Games on %s:" % args.opl_drive)
        print("|-> ISO Games:")

        # Find all game iso's
        for game in self.__get_all_iso_games():
            game.get_filedata()
            game.gen_opl_id()

            if args.online:
                api = API()
                game.set_metadata(api, args.rename)

            print(f" {str(game)}")

        # Read ul.cfg & output games
        if os.path.exists(path_to_ul_cfg(self.args.opl_drive)):
                print('|-> UL Games:')
                for game in self.__get_all_ul_games():
                    print(f" {str(game)}")
        else:
            print("No UL-Games installed")

        # Create OPL Folders / stuff

    def init(self, args):
        print("Inititalizing OPL-Drive...")
        for dir in ['APPS', 'BOOT', 'ART', 'CD', 'CFG', 'CHT', 'DVD', 'THM', 'VMC']:
            if not is_dir(os.path.join(args.opl_drive, dir)):
                os.mkdir(os.path.join(args.opl_drive, dir), 0o777)
        print("Done!")
####
# Main
#
# Parses arguments & calls function from POPLManager-object


def __main__():
    opl = POPLManager()

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='Choose your path...')

    list_parser = subparsers.add_parser("list", help="List Games on OPL-Drive")
    list_parser.add_argument(
        "--online", "-o", help="Check for Metadata in API", action='store_true', default=False)
    list_parser.add_argument(
        "opl_drive", help="Path to OPL - e.g. your USB- or SMB-Drive\nExample: /media/usb",
        type=lambda x: Path(x))
    list_parser.set_defaults(func=opl.list)

    add_parser = subparsers.add_parser(
        "add", help="Add Media Image to OPL-Drive")
    add_parser.add_argument(
        "--rename", "-r", help="Rename Game by obtaining it's title from API", action='store_true')
    add_parser.add_argument(
        "--force", "-f", help="Force overwriting of existing files", action='store_true', default=False)
    add_parser.add_argument(
        "--ul", "-u", help="Force UL-Game converting", action='store_true')
    add_parser.add_argument(
        "--iso", "-i", help="Don't do UL conversion", action='store_true')
    add_parser.add_argument(
        "opl_drive", help="Path to OPL - e.g. your USB- or SMB-Drive\nExample: /media/usb",
        type=lambda x: Path(x))
    add_parser.add_argument("src_file", nargs='+',
                            help="Media/ISO Source File")
    add_parser.set_defaults(func=opl.add)

    art_parser = subparsers.add_parser(
        "artwork", help="Download Artwork onto opl_drive")
    art_parser.add_argument(
        "--force", "-f", help="Force replacement of existing artwork", action='store_true')
    art_parser.add_argument(
        "opl_drive", help="Path to OPL - e.g. your USB- or SMB-Drive\nExample: /media/usb",
        type=lambda x: Path(x))
    art_parser.set_defaults(func=opl.download_artwork)

    fix_parser = subparsers.add_parser(
        "fix", help="rename/fix media filenames")
    fix_parser.add_argument(
        "opl_drive", help="Path to OPL - e.g. your USB- or SMB-Drive\nExample: /media/usb",
        type=lambda x: Path(x))
    fix_parser.set_defaults(func=opl.fix)

    init_parser = subparsers.add_parser(
        "init", help="Initialize OPL-Drive folder-structure")
    init_parser.add_argument(
        "opl_drive", help="Path to OPL - e.g. your USB- or SMB-Drive\nExample: /media/usb",
        type=lambda x: Path(x))
    init_parser.set_defaults(func=opl.init)

    del_parser = subparsers.add_parser("delete", help="Delete game from Drive")
    del_parser.add_argument(
        "opl_drive", help="Path to OPL - e.g. your USB- or SMB-Drive\nExample: /media/usb",
        type=lambda x: Path(x))
    del_parser.add_argument("opl_id", nargs='+',
                            help="OPL-ID of Media/ISO File to delete")
    del_parser.set_defaults(func=opl.delete)
    arguments = parser.parse_args()
    opl.set_args(arguments)
    
    if hasattr(arguments, 'opl_drive'):
        if not is_dir(arguments.opl_drive):
            print("Error: opl_drive directory doesn't exist!")
            sys.exit(1)

    if hasattr(arguments, 'func'):
        arguments.func(arguments)
    else:
        parser.print_help(sys.stderr)
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    __main__()
