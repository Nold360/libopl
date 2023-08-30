#!/usr/bin/env python3
###

from shutil import copyfile, move
from typing import List
from pathlib import Path
from configparser import ConfigParser
import pyoplm.bintools
from pyoplm.bintools import BinMergeArgs, Cue2PopsArgs, BChunkArgs

from pyoplm.common import path_to_ul_cfg, get_iso_id
from pyoplm.game import Game, POPSGameImage, ULGameImage, IsoGameImage, GameType
from pyoplm.storage import Storage
from pyoplm.ul import ULConfig

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
    pops_games: List[POPSGameImage]

    def __init__(self):
        self.iso_games = []
        self.ul_games = []
        self.games = []
        self.pops_games = []

    def set_args(self, args):
        self.args = args
        self.opl_dir = args.opl_dir
        self.initialize_storage()

    def initialize_storage(self):
        config = ConfigParser()
        config.read(str(self.opl_dir.joinpath("pyoplm.ini")))
        self.storage = Storage(config.get("STORAGE", "location", fallback=None), self.opl_dir, config.get(
            "STORAGE.INDEXING", "zip_contents_location", fallback=None))

    def __get_all_pops_game_files(self) -> List[Path]:
        path = self.opl_dir.joinpath("POPS")
        games = list(path.glob("*.[vV][cC][dD]"))
        return games

    def __get_all_pops_games(self) -> List[POPSGameImage]:
        if not self.pops_games:
            games: List[POPSGameImage] = []
            paths = self.__get_all_pops_game_files()
            for path in paths:
                game = POPSGameImage(path)
                games.append(game)
            self.pops_games = games
        return self.pops_games

    def __get_iso_game_files(self, type="DVD") -> List[Path]:
        path = self.opl_dir.joinpath(type)
        games = list(path.glob('*.[iI][sS][oO]'))
        return games

    def __get_all_iso_games(self) -> List[IsoGameImage]:
        if not self.iso_games:
            paths: List[Path] = self.__get_iso_game_files(
                "DVD") + self.__get_iso_game_files("CD")
            games: List[Game] = []
            for path in paths:
                game = IsoGameImage(path)
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
        return self.__get_all_iso_games() \
            + self.__get_all_ul_games() \
            + self.__get_all_pops_games()

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
                            game.delete_game()
                            print("No more games left, deleting ul.cfg...")
                            if not len(ul_cfg.ulgames):
                                ul_cfg.filepath.unlink()
                        case GameType.ISO | GameType.POPS:
                            if game.filepath.exists():
                                game.delete_game()

                    for art_file in args.opl_dir.joinpath("ART").glob(f"{args.opl_id}*"):
                        art_file.unlink()

    def rename(self, args):
        if not hasattr(args, "storage"):
            args.opl_id = [args.opl_id]

        if not args.opl_id:
            print("Renaming all games from storage...")

        for game in self.__get_full_game_list():
            if game.opl_id in args.opl_id or not args.opl_id:
                if hasattr(args, "storage"):
                    if not self.storage.is_enabled():
                        print("Proper storage link not supplied in opl_dir/pyoplm.ini,\
                               not downloading artwork.", file=sys.stderr)
                        sys.exit(0)

                    setattr(args, "new_title",
                            self.storage.get_game_title(game.opl_id))
                if not args.new_title:
                    continue

                if len(args.new_title) > 32:
                    print(f"Title {args.new_title} is too long!",
                          file=sys.stderr)
                    print(
                        "Titles longer than 32 characters are not permitted!", file=sys.stderr)
                    print(f"Skipping {game.opl_id}...", file=sys.stderr)
                    continue

                match game.type:
                    case GameType.ISO | GameType.POPS:
                        new_filename = f"{game.opl_id}.{args.new_title}.{game.filetype}"
                        new_filepath = game.filepath.parent.joinpath(
                            new_filename
                        )
                        game.filepath = game.filepath.rename(new_filepath)

                        game.title = args.new_title
                        print(
                            f"The game \'{game.opl_id}\' was renamed to \'{game.title}\'")
                    case GameType.UL:
                        game: ULGameImage = game
                        ULConfig(
                            path_to_ul_cfg(args.opl_dir)
                        ).rename_game(game.opl_id, args.new_title)
                        print(
                            f"The game \'{game.opl_id}\' was renamed to \'{args.new_title}\'")

        print("Fixing all games just in case...")
        self.fix(args)

    def __psx_add(self, cuefile_path: Path):
        TMP_FILES_NAME = "pyoplm_tmp"
        print("Installing PSX game " + cuefile_path.as_posix())
        if len(cuefile_path.stem) > 32:
            print(f"The cue file's name will be kept as a game title, please make the filename {cuefile_path.stem} less than 32 characters long", file=sys.stderr)
            return
        if not (cuefile_path.exists()):
            print(f"POPS game with path {cuefile_path.as_posix()} doesn't exist, skipping...", file=sys.stderr)
            return

        with cuefile_path.open("r") as cue:
            filecount = cue.read().count("FILE")
            needs_binmerge = filecount > 1
            if filecount == 0:
                print(f"Cue file is invalid {cuefile_path.as_posix()} or there are no bin files, skipping...", file=sys.stderr)
                return

        if needs_binmerge:
            bm_args: BinMergeArgs = BinMergeArgs(cuefile=cuefile_path,
                                                 basename=TMP_FILES_NAME,
                                                 license=None,
                                                 split=None,
                                                 outdir="/tmp")
            binmerge_exit_code = pyoplm.bintools.binmerge(bm_args)
            if binmerge_exit_code != 0:
                print(f"Binmerge finished with exit code: {binmerge_exit_code} for game {cuefile_path}, skipping..."
                      ,file=sys.stderr)
                return

        cue2pops_input = cuefile_path if not needs_binmerge else Path(
            f"/tmp/{TMP_FILES_NAME}.cue")
        cue2pops_args: Cue2PopsArgs = Cue2PopsArgs(
            input_file=cue2pops_input, 
            gap=None,
            vmode=None,
            trainer=None,
            output_file=self.opl_dir.joinpath("POPS", cuefile_path.stem + ".VCD")
            )
        cue2pops_exit_code = pyoplm.bintools.cue2pops(cue2pops_args)           
        if cue2pops_exit_code != 1:
            print(f"Cue2pops finished with exit code: {cue2pops_exit_code} for game {cuefile_path}, skipping..."
                   ,file=sys.stderr)
            if needs_binmerge:
                cue2pops_input.unlink()
                cue2pops_input.with_suffix(".bin").unlink()
            return
        
        print(f"Successfully installed POPS {cuefile_path.stem} game to opl_dir, ")
        print(cue2pops_input)
        if needs_binmerge:
            cue2pops_input.unlink()
            cue2pops_input.with_suffix(".bin").unlink()

        self.fix(self.args)


    def __conv_ps2_cd_to_iso(self, cuefile_path: Path):
        if not cuefile_path.exists():
            print(f"File {cuefile_path.as_posix()} does not exist, skipping...")
            return
        if len(cuefile_path.stem) > 32:
            print(f"The cue file's name will be kept as a game title, please make the filename {cuefile_path.stem} less than 32 characters long",file=sys.stderr)
            return
        with cuefile_path.open("r") as cue:
            if len(binfile := re.findall(r"\"(.*.bin)\"", cue.read())) > 1:
                print(f"The game {cuefile_path.as_posix()} has more than one track, which is not supported for single-iso conversion by bchunk", file=sys.stderr)
                return 
            elif not binfile:
                print(f"Cue file is invalid {cuefile_path.as_posix()} or there are no bin files, skipping...", file=sys.stderr)
                return
        print("BINFILE: " + str(binfile))

        bchunk_binfile = cuefile_path.parent.joinpath(binfile[0])
        bchunk_exit_code = pyoplm.bintools.bchunk(BChunkArgs(
            p=None,
            src_bin=bchunk_binfile,
            src_cue=cuefile_path,
            basename=cuefile_path.stem
        ))
        if bchunk_exit_code != 0:
            print(f"Failed to install game {cuefile_path.stem}")
            print(f"Cue2pops finished with exit code: {bchunk_exit_code} for game {cuefile_path}, skipping..."
                   ,file=sys.stderr)

        finished_conv_path = cuefile_path.with_name(cuefile_path.stem + "01.iso")
        move(
            finished_conv_path,
            self.opl_dir.joinpath("CD", cuefile_path.stem + ".iso")
        )

        print(f"Successfully installed game {cuefile_path.stem}")

        self.fix(self.args)


    # Add game(s) to args.opl_dir
    #  - split game if > 4GB / forced
    #  - otherwise just copy with OPL-like filename
    #  - If storage features are enabled, try to get title from storage and download artwork

    def add(self, args):
        for game_path in args.src_file:
            if args.psx:
                self.__psx_add(game_path)
                continue

            if re.match(r"^.[cC][uU][eE]$", game_path.suffix):
                print(f"Attempting to convert game {game_path} to ISO...")
                self.__conv_ps2_cd_to_iso(game_path)
                continue

            iso_id = get_iso_id(game_path)
            # Game size in MB
            game_size = game_path.stat().st_size / 1024 ** 2

            if (game_size > 4000 and not args.iso) or args.ul:
                ul_cfg = ULConfig(path_to_ul_cfg(args.opl_dir))
                if self.storage.is_enabled() and args.storage:
                    ul_cfg.add_game_from_iso(
                        game_path, args.force, self.storage.get_game_title(iso_id).encode('ascii'))
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

                    if title:
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
        ULConfig.find_and_delete_corrupted_entries(
            path_to_ul_cfg(args.opl_dir))

        ulcfg = ULConfig(path_to_ul_cfg(args.opl_dir))
        ulcfg.find_and_recover_games()

        print("Fixing ISO and POPS game file names for OPL read speed and deleting broken UL games")
        for game in self.__get_full_game_list():
            if not game.id:
                print(f"Error while parsing file: {game.filepath}")
                continue

            match game.type:
                case GameType.ISO | GameType.POPS:
                    game_name_regex = re.compile(
                        r"^[HhMmPpGgNnCcSsJjTtBbDdAaKk][a-zA-Z]{3}.?\d{3}\.?\d{2}\..{1,32}")
                    if not game_name_regex.findall(game.filename):
                        print(f"Fixing \'{game.filename}\'...")
                        game.filepath = game.filepath.rename(
                            game.filedir.joinpath(
                                f"{game.opl_id}.{game.title}.{game.filetype}")
                        )

                        if game.type == GameType.POPS:
                            pops_data_folder = game.filedir.joinpath(
                                game.filename[:-4])
                            if pops_data_folder.exists():
                                game.filedir.joinpath(game.filename[:-4]).rename(
                                    game.filedir.joinpath(
                                        f"{game.opl_id}.{game.title}")
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
            if not args.opl_id:
                print("Downloading artwork for all games...")
            for game in self.__get_full_game_list():
                if game.opl_id in args.opl_id or not args.opl_id:
                    print(
                        f"Downloading artwork for [{game.opl_id}] {game.title}")
                    self.storage.get_artwork_for_game(
                        game.opl_id, bool(args.overwrite))
        else:
            print(
                "Storage link not supplied in opl_dir/pyoplm.ini, not downloading artwork.", file=sys.stderr)
            sys.exit(0)

    # List all Games on OPL-Drive
    def list(self, args):
        print("Searching Games on %s:" % args.opl_dir)
        iso_games = self.__get_all_iso_games()
        if iso_games:
            print("|-> ISO Games:")
            for game in self.__get_all_iso_games():
                print(f" {str(game)}")
        else:
            print("No ISO games installed")

        pops_games = self.__get_all_pops_games()
        if pops_games:
            print("|-> POPS Games:")
            for game in pops_games:
                print(f" {str(game)}")

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
        for dir in ["APPS", "LNG", "ART", "CD", "CFG", "CHT", "DVD", "THM", "VMC", "POPS"]:
            if not (dir := args.opl_dir.joinpath(dir)).is_dir():
                dir.mkdir(0o777)
        print("Done!")
####
# Main
#
# Parses arguments & calls function from POPLManager-object


def main():
    opl = POPLManager()

    parser = argparse.ArgumentParser()
    parser.prog = "pyoplm"

    subparsers = parser.add_subparsers(help="Choose your path...")

    list_parser = subparsers.add_parser("list", help="List Games on OPL-Drive")
    list_parser.add_argument(
        "opl_dir", help="Path to your OPL directory",
        type=lambda x: Path(x))
    list_parser.set_defaults(func=opl.list)

    add_parser = subparsers.add_parser(
        "add", help="Add Media Image to opl_dir")
    add_parser.add_argument(
        "--force", "-f", help="Force overwriting of existing files", action='store_true', default=False)
    add_parser.add_argument(
        "--psx", "-p", help="Install PSX games", action="store_true")
    add_parser.add_argument(
        "--ul", "-u", help="Force UL-Game converting", action="store_true")
    add_parser.add_argument(
        "--iso", "-i", help="Don't do UL conversion", action="store_true")
    add_parser.add_argument(
        "--storage", "-s", help="Get title and artwork from storage if it's enabled", action="store_true")
    add_parser.add_argument(
        "opl_dir", help="Path to your OPL directory",
        type=lambda x: Path(x))
    add_parser.add_argument("src_file", nargs="+",
                            help="Media/ISO Source File",
                            type=lambda file: Path(file))
    add_parser.set_defaults(func=opl.add)

    storage_parser = subparsers.add_parser(
        "storage", help="Art and title storage-related functionality"
    )
    storage_subparsers = storage_parser.add_subparsers(
        help="Choose your path...")

    artwork_parser = storage_subparsers.add_parser(
        "artwork", help="Download artwork for games installed in opl_dir\
            , if no opl_id are supplied, downloads artwork for all games"
    )
    artwork_parser.add_argument(
        "opl_dir", help="Path to your OPL directory",
        type=lambda x: Path(x))
    artwork_parser.add_argument(
        "--overwrite", "-o", help="Overwrite existing art files for games", action="store_true")
    artwork_parser.add_argument("opl_id", help="OPL-IDs of games to download artwork for", nargs="*"
                                )
    artwork_parser.set_defaults(func=opl.artwork)

    storage_rename_parser = storage_subparsers.add_parser(
        "rename", help="Rename the game opl_id with a name taken from the storage\
            , if no opl_id are supplied, renames all games"
    )
    storage_rename_parser.add_argument(
        "opl_dir", help="Path to your OPL directory",
        type=lambda x: Path(x))
    storage_rename_parser.add_argument("opl_id",
                                       help="OPL-IDs of games to rename",
                                       nargs="*")
    storage_rename_parser.set_defaults(storage=True, func=opl.rename)

    rename_parser = subparsers.add_parser(
        "rename", help="Change the title of the game corresponding to opl_id to new_title in the given opl_dir"
    )
    rename_parser.add_argument(
        "opl_dir", help="Path to your OPL directory",
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
        "opl_dir", help="Path to your OPL directory",
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
        "opl_dir", help="Path to your OPL directory",
        type=lambda x: Path(x))
    del_parser.add_argument("opl_id", nargs="+",
                            help="OPL-ID of Media/ISO File to delete")
    del_parser.set_defaults(func=opl.delete)

    tools_parser = subparsers.add_parser(
        "bintools", help="Tools for processing cue/bin games")
    tools_subparser = tools_parser.add_subparsers(help="Choose your path...")

    bchunk_parser = tools_subparser.add_parser(
        "bin2iso", help="Bin to ISO conversion (uses bchunk, repo: https://github.com/extramaster/bchunk)")
    bchunk_parser.add_argument(
        "-p", help=" PSX mode for MODE2/2352: write 2336 bytes from offset 24")
    bchunk_parser.add_argument("src_bin", help="BIN file to convert")
    bchunk_parser.add_argument("src_cue", help="CUE file related to image.bin")
    bchunk_parser.add_argument("basename", help="name (without extension) for your new bin/cue files")
    bchunk_parser.set_defaults(tools_func=pyoplm.bintools.bchunk)

    binmerge_parser = tools_subparser.add_parser(
        "binmerge", help="Merge multibin/cue into a single bin/cue (uses binmerge, repo: https://github.com/putnam/binmerge)")
    binmerge_parser.add_argument(
        "--outdir", "-o", help="output directory. defaults to the same directory as source cue.directory will be created (recursively) if needed.")
    binmerge_parser.add_argument(
        "--license", "-l", action="store_true", help="prints license info and exit")
    binmerge_parser.add_argument("--split", "-s", action="store_true",
                                 help="reverses operation, splitting merged files back to individual tracks")
    binmerge_parser.add_argument(
        "cuefile", type=Path, help="CUE file pointing to bin files (bin files are expected in the same dir)")
    binmerge_parser.add_argument(
        "basename", help="name (without extension) for your new bin/cue files")
    binmerge_parser.set_defaults(tools_func=pyoplm.bintools.binmerge)

    cue2pops_parser = tools_subparser.add_parser(
        "cue2pops", help="Turn single cue/bin files into VCD format readable by POPSTARTER (uses cue2pops-linux, repo: https://github.com/tallero/cue2pops-linux).")
    cue2pops_parser.add_argument(
        "input_file", type=Path, help="Input cue file")
    cue2pops_parser.add_argument(
        "--gap", choices=["++", "--"], help="Adds(gap++)/subtracts(gap--) 2 seconds to all track indexes MSF")
    cue2pops_parser.add_argument("--vmode", "-v", action="store_true",
                                 help="Attempts to patch the video mode to NTSC and to fix the screen position")
    cue2pops_parser.add_argument(
        "--trainer", "-t", action="store_true", help="Enable cheats")
    cue2pops_parser.add_argument("output_file", help="output file", nargs="?")
    cue2pops_parser.set_defaults(tools_func=pyoplm.bintools.cue2pops)

    arguments = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    if hasattr(arguments, "opl_dir"):
        opl.set_args(arguments)
        opl_dir: Path = arguments.opl_dir
        if not opl_dir.exists() or not opl_dir.is_dir():
            print("Error: opl_dir directory doesn't exist!")
            sys.exit(1)
        if hasattr(arguments, "func"):
            arguments.func(arguments)
        else:
            parser.print_help(sys.stderr)
            sys.exit(1)

    if hasattr(arguments, "tools_func"):
        arguments.tools_func(arguments)
    elif hasattr(arguments, "func"):
        pass
    else:
        parser.print_help(sys.stderr)
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
