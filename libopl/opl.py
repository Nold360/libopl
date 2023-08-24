#!/usr/bin/env python3
###
# Python CLI Replacement for OPLManager

from shutil import copyfile
from typing import List
from pathlib import Path

from libopl.common import path_to_ul_cfg, get_iso_id
from libopl.game import Game, ULGameImage, IsoGameImage, GameType
from libopl.ul import ULConfig

import re
import sys
import argparse

class POPLManager:
    args = None
    opl_drive: Path
    games: List[Game]
    iso_games: List[IsoGameImage]
    ul_games: List[ULGameImage]

    def __init__(self, args=None):
        self.iso_games = []
        self.ul_games = []
        self.games = []
        self.set_args(args)

    def set_args(self, args):
        self.args = args

    # Return: array of filepath's for all games on opl_drive
    def __get_iso_game_files(self, type="DVD") -> List[Path]:
        path = self.args.opl_drive.joinpath(type)
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
            path_to_ul_cfg(self.args.opl_drive)
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
                            ul_cfg = ULConfig(path_to_ul_cfg(args.opl_drive))
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

                    for art_file in args.opl_drive.joinpath("ART").glob(f"{args.opl_id}*"):
                        art_file.unlink()

    def rename(self, args):
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
                            path_to_ul_cfg(args.opl_drive)
                        ).rename_game(args.opl_id, args.new_title)
                        print(
                            f"The game \'{args.opl_id}\' was renamed to \'{args.new_title}\'")

    # Add game(s) to args.opl_drive
    #  - split game if > 4GB / forced
    #  - otherwise just copy with OPL-like filename

    def add(self, args):
        # self.api = API()
        for game_path in args.src_file:
            game_path: Path = game_path
            # Game size in MB
            game_size = game_path.stat().st_size / 1024 ** 2
            if (game_size > 4000 and not args.iso) or args.ul:
                ul_cfg = ULConfig(path_to_ul_cfg(args.opl_drive))
                ul_cfg.add_game_from_iso(game_path, args.force)
            else:
                iso_id = get_iso_id(game_path)
                if not all(map(lambda x: x.id != iso_id, self.__get_all_iso_games())) and not args.force:
                    print(
                        f"Game with ID \'{iso_id}\' is already installed, skipping...")
                    print("Use the -f flag to force the installation of this game")
                    continue
                else:
                    if len(title := str.split(game_path.name, '.')[0]) > 32:
                        print(
                            f"Game title \'{title}\' is longer than 32 characters, skipping...")
                        continue
                    new_game_path: Path = args.opl_drive.joinpath(
                        "DVD" if game_size > 700 else "CD",
                        f"{iso_id}.{game_path.name}")

                    print(
                        f"Copying game to \'{new_game_path}\', please wait...")
                    copyfile(game_path, new_game_path)
                    print("Done!")

    # Fix ISO names for faster OPL access
    # Delete UL games with missing parts
    # Recover UL games which are not in UL.cfg
    def fix(self, args):
        ulcfg = ULConfig(path_to_ul_cfg(args.opl_drive))
        ulcfg.find_and_recover_games()

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

    # List all Games on OPL-Drive

    def list(self, args):
        print("Searching Games on %s:" % args.opl_drive)
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
        if path_to_ul_cfg(self.args.opl_drive).exists():
            print('|-> UL Games:')
            for game in self.__get_all_ul_games():
                print(f" {str(game)}")
        else:
            print("No UL-Games installed")

    # Create OPL Folders / stuff
    def init(self, args):
        print("Inititalizing OPL-Drive...")
        for dir in ["APPS", "LNG", "ART", "CD", "CFG", "CHT", "DVD", "THM", "VMC"]:
            if not (dir := args.opl_drive.joinpath(dir)).is_dir():
                dir.mkdir(0o777)
        print("Done!")
####
# Main
#
# Parses arguments & calls function from POPLManager-object


def __main__():
    opl = POPLManager()

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help="Choose your path...")

    list_parser = subparsers.add_parser("list", help="List Games on OPL-Drive")
    list_parser.add_argument(
        "opl_drive", help="Path to OPL - e.g. your USB- or SMB-Drive\nExample: /media/usb",
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
        "opl_drive", help="Path to OPL - e.g. your USB- or SMB-Drive\nExample: /media/usb",
        type=lambda x: Path(x))
    add_parser.add_argument("src_file", nargs="+",
                            help="Media/ISO Source File",
                            type=lambda file: Path(file))
    add_parser.set_defaults(func=opl.add)

    rename_parser = subparsers.add_parser(
        "rename", help="Given an opl_id, change the title of the game corresponding to that ID in the given opl_drive"
    )
    rename_parser.add_argument(
        "opl_drive", help="Path to OPL - e.g. your USB- or SMB-Drive\nExample: /media/usb",
        type=lambda x: Path(x))
    rename_parser.add_argument("opl_id",
                               help="OPL-ID of Media/ISO File to delete")
    rename_parser.add_argument("new_title",
                               help="New title for the game")
    rename_parser.set_defaults(func=opl.rename)

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
    del_parser.add_argument("opl_id", nargs="+",
                            help="OPL-ID of Media/ISO File to delete")
    del_parser.set_defaults(func=opl.delete)
    arguments = parser.parse_args()
    opl.set_args(arguments)

    if hasattr(arguments, "opl_drive"):
        opl_drive: Path = arguments.opl_drive
        if not opl_drive.exists() or not opl_drive.is_dir():
            print("Error: opl_drive directory doesn't exist!")
            sys.exit(1)

    if hasattr(arguments, "func"):
        arguments.func(arguments)
    else:
        parser.print_help(sys.stderr)
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    __main__()
