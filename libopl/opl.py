#!/usr/bin/env python3
###
# Python CLI Replacement for OPLManager

from shutil import copyfile
from typing import List
from pathlib import Path
from configparser import ConfigParser

from libopl.common import path_to_ul_cfg, get_iso_id
from libopl.game import Game, ULGameImage, IsoGameImage, GameType
from libopl.storage import Storage
from libopl.ul import ULConfig

import re
import sys
import argparse

class POPLManager:
    args = None
    opl_dir: Path
    storage: Storage
    games: List[Game]
    iso_games: List[IsoGameImage]
    ul_games: List[ULGameImage]

    def __init__(self, args=None):
        self.iso_games = []
        self.ul_games = []
        self.games = []

    def set_args(self, args):
        self.args = args
        self.opl_dir = args.opl_dir
        self.initialize_storage()

    def initialize_storage(self):
        config = ConfigParser()
        config.read(str(self.opl_dir.joinpath("libopl.ini")))
        self.storage = Storage(config.get("STORAGE", "location", fallback="DISABLED"), self.opl_dir)


    # Return: array of filepath's for all games on opl_dir
    def __get_iso_game_files(self, type="DVD") -> List[Path]:
        path = self.opl_dir.joinpath(type)
        games = list(path.glob('*.[iI][sS][oO]'))
        return games

    def __get_all_iso_games(self) -> List[Game]:
        if not self.iso_games:
            paths: List[Path] = self.__get_iso_game_files(
                "DVD") + self.__get_iso_game_files("CD")
            games: List[Game] = []
            for path in paths:
                game = IsoGameImage(str(path))
                games.append(game)
            self.iso_games = games
        return self.iso_games

    def __get_all_ul_games(self) -> List[Game]:
        ul_cfg: ULConfig = ULConfig(
            path_to_ul_cfg(self.opl_dir)
        )
        if not self.ul_games:
            games = [game_cfg.game for game_cfg in ul_cfg.ulgames.values()]
            self.ul_games = games
        return self.ul_games

    def __get_full_game_list(self) -> List[Game]:
        return self.__get_all_iso_games() + self.__get_all_ul_games()

    def delete(self, args):
        for opl_id in args.opl_id:
            for game in self.__get_full_game_list():
                if game.opl_id == opl_id:
                    match game.type:
                        case GameType.UL:
                            print(f"Deleting {opl_id}...")
                            ul_cfg = ULConfig(path_to_ul_cfg(args.opl_dir))
                            ul_cfg.ulgames.pop(game.ulcfg.region_code, None)
                            print("Adjusting ul.cfg...")
                            ul_cfg.write()
                            print("Deleting game chunks...")
                            game.delete_files()
                            print("No more games left, deleting ul.cfg...")
                            if not len(ul_cfg.ulgames):
                                ul_cfg.filepath.unlink()
                        case GameType.ISO:
                            if game.filepath.exists():
                                print(f"Deleting {opl_id}...")
                                game.filepath.unlink()

                    for art_file in args.opl_dir.joinpath("ART").glob(f"{args.opl_id}*"):
                        art_file.unlink()

    def rename(self, args):
        if hasattr(args, "storage"):
            setattr(args, "new_title", self.storage.get_game_title(args.opl_id))

        if len(args.new_title) > 32:
            print("Titles longer than 32 characters are not permitted!")
            sys.exit(1)

        for game in self.__get_full_game_list():
            if args.opl_id == game.opl_id:
                match game.type:
                    case GameType.ISO:
                        game.filepath = game.filepath.rename(
                            game.filepath.parent.joinpath(
                                args.new_title
                            ).with_suffix(".iso")
                        )
                        game.title = args.new_title
                        print(
                            f"The game \'{args.opl_id}\' was renamed to \'{game.title}\'")
                        print("Fixing game names...")
                        self.fix(args)
                    case GameType.UL:
                        game: ULGameImage = game
                        ULConfig(
                            path_to_ul_cfg(args.opl_dir)
                        ).rename_game(args.opl_id, args.new_title)
                        print(
                            f"The game \'{args.opl_id}\' was renamed to \'{args.new_title}\'")

    # Add game(s) to args.opl_dir
    #  - split game if > 4GB / forced
    #  - otherwise just copy with OPL-like filename

    def add(self, args):
        for game_path in args.src_file:
            game_path: Path = game_path
            iso_id = get_iso_id(game_path)
            # Game size in MB
            game_size = game_path.stat().st_size / 1024 ** 2

            if (game_size > 4000 and not args.iso) or args.ul:
                ul_cfg = ULConfig(path_to_ul_cfg(args.opl_dir))
                if self.storage.is_enabled() and args.storage:
                    ul_cfg.add_game_from_iso(game_path, args.force, self.storage.get_game_title(iso_id).encode('ascii'))
                else:
                    ul_cfg.add_game_from_iso(game_path, args.force)
            else:
                if not all(map(lambda x: x.id != iso_id, self.__get_all_iso_games())) and not args.force:
                    print(
                        f"Game with ID \'{iso_id}\' is already installed, skipping...")
                    print("Use the -f flag to force the installation of this game")
                    continue
                else:

                    if self.storage.is_enabled() and args.storage:
                        title = self.storage.get_game_title(iso_id)
                    else:
                        title = str.split(game_path.name, '.')[0]

                    if len(title) > 32:
                        print(
                            f"Game title \'{title}\' is longer than 32 characters, skipping...")
                        continue
                    new_game_path: Path = args.opl_dir.joinpath(
                        "DVD" if game_size > 700 else "CD",
                        f"{iso_id}.{title}.iso")

                    print(
                        f"Copying game to \'{new_game_path}\', please wait...")
                    copyfile(game_path, new_game_path)
                    print("Done!")
            
            if self.storage.is_enabled() and args.storage:
                self.storage.get_artwork_for_game(iso_id, True)

    # Fix ISO names for faster OPL access
    # Delete UL games with missing parts
    # Recover UL games which are not in ul.cfg
    # Find corrupted entries in ul.cfg first and delete them
    def fix(self, args):
        ULConfig.find_and_delete_corrupted_entries(path_to_ul_cfg(args.opl_dir))

        ulcfg = ULConfig(path_to_ul_cfg(args.opl_dir))
        ulcfg.find_and_recover_games()

        print("Fixing ISO names for OPL read speed and deleting broken UL games")
        for game in self.__get_full_game_list():
            if not game.id:
                print(f"Error while parsing file: {game.filepath}")
                continue

            match game.type:
                case GameType.ISO:
                    game_name_regex = re.compile(
                        r"^S[a-zA-Z]{3}.?\d{3}\.?\d{2}\.{1,32}")
                    if not game_name_regex.findall(game.filename):
                        print(f"Fixing \'{game.filename}\'...")
                        game.filepath = game.filepath.rename(
                            game.filepath.parent.joinpath(
                                f"{game.id}.{game.filename}.iso")
                        )
                        game.filename = game.filepath.name
                        game.gen_opl_id()
                        game.print_data()
                case GameType.UL:
                    for file in game.get_filenames():
                        if not file.exists():
                            print(f"Part \'{file.name}\' is missing from UL game \'{game.title}\'\
                                  , please re-install the game")
                            print("Deleting broken game...")
                            setattr(args, "opl_id", [game.opl_id])
                            self.delete(args)

    # Download all artwork for all games if storage is enabled
    def artwork(self, args):
        if self.storage.is_enabled():
            print("Downloading artwork for all games...")
            for game in self.__get_full_game_list():
                print(f"Downloading artwork for [{game.opl_id}] {game.title}")
                self.storage.get_artwork_for_game(game.opl_id, bool(args.overwrite))
        else:
            print("Storage link not supplied in opl_dir/libopl.ini, not downloading artwork.", sys.stderr)
            sys.exit(0)

    # List all Games on OPL-Drive
    def list(self, args):
        print("Searching Games on %s:" % args.opl_dir)
        iso_games = self.__get_all_iso_games()
        if iso_games:
            print("|-> ISO Games:")
            for game in self.__get_all_iso_games():
                game.get_filedata()
                game.gen_opl_id()

                print(f" {str(game)}")
        else:
            print("No ISO games installed")

        # Read ul.cfg & output games
        if path_to_ul_cfg(self.args.opl_dir).exists():
            print('|-> UL Games:')
            for game in self.__get_all_ul_games():
                print(f" {str(game)}")
        else:
            print("No UL-Games installed")

    # Create OPL Folders / stuff
    def init(self, args):
        print("Inititalizing OPL-Drive...")
        for dir in ["APPS", "LNG", "ART", "CD", "CFG", "CHT", "DVD", "THM", "VMC"]:
            if not (dir := args.opl_dir.joinpath(dir)).is_dir():
                dir.mkdir(0o777)
        print("Done!")
####
# Main
#
# Parses arguments & calls function from POPLManager-object


def __main__():
    opl = POPLManager()

    parser = argparse.ArgumentParser()
    parser.prog = "opl"

    subparsers = parser.add_subparsers(help="Choose your path...")

    list_parser = subparsers.add_parser("list", help="List Games on OPL-Drive")
    list_parser.add_argument(
        "opl_dir", help="Path to OPL - e.g. your USB- or SMB-Drive\nExample: /media/usb",
        type=lambda x: Path(x))
    list_parser.set_defaults(func=opl.list)

    add_parser = subparsers.add_parser(
        "add", help="Add Media Image to OPL-Drive")
    add_parser.add_argument(
        "--force", "-f", help="Force overwriting of existing files", action='store_true', default=False)
    add_parser.add_argument(
        "--ul", "-u", help="Force UL-Game converting", action="store_true")
    add_parser.add_argument(
        "--iso", "-i", help="Don't do UL conversion", action="store_true")
    add_parser.add_argument(
        "--storage", "-s", help="Get title and artwork from storage if it's enabled", action="store_true")
    add_parser.add_argument(
        "opl_dir", help="Path to OPL - e.g. your USB- or SMB-Drive\nExample: /media/usb",
        type=lambda x: Path(x))
    add_parser.add_argument("src_file", nargs="+",
                            help="Media/ISO Source File",
                            type=lambda file: Path(file))
    add_parser.set_defaults(func=opl.add)

    storage_parser = subparsers.add_parser(
        "storage", help="Art and names storage-related functionality"
    )
    storage_subparsers = storage_parser.add_subparsers(help="Choose your path...")
    artwork_parser = storage_subparsers.add_parser(
        "artwork", help="Download artwork for all games installed in opl_dir"
    )
    artwork_parser.add_argument(
        "opl_dir", help="Path to OPL - e.g. your USB- or SMB-Drive\nExample: /media/usb",
        type=lambda x: Path(x))
    artwork_parser.add_argument(
        "--overwrite", "-o", help="Overwrite existing art files for games", action="store_true")
    artwork_parser.set_defaults(func=opl.artwork)
    storage_rename_parser = storage_subparsers.add_parser(
        "rename", help="Rename the game opl_id with a name taken from the storage"
    )
    storage_rename_parser.add_argument(
        "opl_dir", help="Path to OPL - e.g. your USB- or SMB-Drive\nExample: /media/usb",
        type=lambda x: Path(x))
    storage_rename_parser.add_argument("opl_id",
                               help="OPL-ID of Media/ISO File to delete")
    storage_rename_parser.set_defaults(storage=True, func=opl.rename)

    rename_parser = subparsers.add_parser(
        "rename", help="Given an opl_id, change the title of the game corresponding to that ID in the given opl_dir"
    )
    rename_parser.add_argument(
        "opl_dir", help="Path to OPL - e.g. your USB- or SMB-Drive\nExample: /media/usb",
        type=lambda x: Path(x))
    rename_parser.add_argument(
        "--ul", "-u", help="Force UL-Game converting", action="store_true")
    rename_parser.add_argument("opl_id",
                               help="OPL-ID of Media/ISO File to delete")
    rename_parser.add_argument("new_title",
                               help="New title for the game")
    rename_parser.set_defaults(func=opl.rename)

    
    fix_parser = subparsers.add_parser(
        "fix", help="rename/fix media filenames")
    fix_parser.add_argument(
        "opl_dir", help="Path to OPL - e.g. your USB- or SMB-Drive\nExample: /media/usb",
        type=lambda x: Path(x))
    fix_parser.set_defaults(func=opl.fix)

    init_parser = subparsers.add_parser(
        "init", help="Initialize OPL folder structure")
    init_parser.add_argument(
        "opl_dir", help="Path to your OPL USB or SMB Directory\nExample: /media/usb",
        type=lambda x: Path(x))
    init_parser.set_defaults(func=opl.init)

    del_parser = subparsers.add_parser("delete", help="Delete game from Drive")
    del_parser.add_argument(
        "opl_dir", help="Path to OPL - e.g. your USB- or SMB-Drive\nExample: /media/usb",
        type=lambda x: Path(x))
    del_parser.add_argument("opl_id", nargs="+",
                            help="OPL-ID of Media/ISO File to delete")
    del_parser.set_defaults(func=opl.delete)
    arguments = parser.parse_args()
    opl.set_args(arguments)

    if hasattr(arguments, "opl_dir"):
        opl_dir: Path = arguments.opl_dir
        if not opl_dir.exists() or not opl_dir.is_dir():
            print("Error: opl_dir directory doesn't exist!")
            sys.exit(1)

    if hasattr(arguments, "func"):
        arguments.func(arguments)
    else:
        parser.print_help(sys.stderr)
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    __main__()
