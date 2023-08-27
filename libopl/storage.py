import csv
from io import BytesIO
from enum import Enum
from pathlib import Path
import re
from typing import Dict, Iterator, List, Set, Tuple, NewType
from urllib.request import urlopen, pathname2url
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from sys import stderr
from PIL import Image
from io import StringIO


def urls_for_odd_type(region_code: str, art_type: str, url=None) -> Iterator[Tuple[str, str]]:
    """URL generator for types SCR and BG, which do not follow other 
    art type's naming conventions in danielb's art backups"""
    curr_num = 0
    while True:
        path_no_extension = f"{url if url else ''}PS2/{region_code}/{region_code}_{art_type}_{str(curr_num).rjust(2, '0')}"
        yield (f"{path_no_extension}.jpg", f"{path_no_extension}.png")
        curr_num += 1




class Storage:
    """Class which manages all storage-related features such as updating game
    names from the CSVs in the backups and placing a game's artwork files into
    OPL's ART directory"""

    class OperationState(Enum):
        """The storage's operation states"""
        FILESYSTEM = 1
        ONLINE = 2
        DISABLED = 3

    Dimensions = NewType("Dimensions", Tuple[int, int])

    operation_state: OperationState
    """The Storage's current operation state"""

    storage_location: str | Path
    """Location of the backup"""

    old_dir: Path
    """Path to OPL folder"""

    cached_game_list: Dict[str, str]
    """Saved mapping from game region codes to titles"""

    global urls_for_odd_type

    PS2_TYPES_OF_ART: Set[str] = set(
        ("COV", "COV2", "ICO", "LAB", "SCR", "BG", "LGO"))
    """All the types of OPL PS2 art files"""

    PS2_ART_SIZES: Dict[str, Dimensions] = {
        "COV": (140, 200),
        "COV2": (242, 344),
        "ICO": (64, 64),
        "LAB": (18, 240),
        "SCR": (250, 188),
        "BG": (640, 480),
        "SCR2": (250, 188),
        "LGO": (300, 125)
    }
    """Sizes for different types of PS2 art"""

    def __init__(self, backup_location: str, opl_dir: Path):
        if backup_location == "DISABLED":
            self.operation_state = self.OperationState.DISABLED
            return 

        self.opl_dir = opl_dir
        self.cached_game_list = {}
        if backup_location[-1] != "/":
            backup_location += "/"

        if (loc := Path(backup_location)).exists():
            self.operation_state = self.OperationState.FILESYSTEM
            self.storage_location = loc
        else:
            try:
                url = urlopen(backup_location)
                url.close()
                self.operation_state = self.OperationState.ONLINE
                self.storage_location = backup_location
            except HTTPError as e:
                print(
                    f"Attempt to access storage on the web failed, reason: {e.reason}")
                print(f"Error code: {e.code}", file=stderr)
                print(f"Response headers: {e.headers}", file=stderr)
                print(f"WARNING: Features depending on storage have been disabled, there were issues finding and accessing the supplied storage.")
                self.disable_storage()
            except URLError as e:
                print(
                    f"Error accessing web storage on the given link, reason: {e.reason}", file=stderr)
                print(f"WARNING: Features depending on storage have been disabled, there were issues finding and accessing the supplied storage.")
                self.disable_storage()
            except Exception as e:
                print(e, file=stderr)
                print(f"WARNING: Features depending on storage have been disabled, there were issues finding and accessing the supplied storage.")
                self.disable_storage()

    def is_enabled(self):
        match self.operation_state:
            case self.OperationState.DISABLED:
                return False
            case _:
                return True

    def process_game_list_csv(self, file) -> Dict[str, str]:
        if not self.cached_game_list:
            cols_to_delete = ["ID"]
            source = StringIO(urlopen(str(file)).read().decode('utf-8'))
            next(source)
            output = StringIO()

            reader = list(csv.reader(source))
            headers = reader[0]

            indexes_to_delete = [idx for idx, elem in enumerate(
                headers) if elem in cols_to_delete]
            result = [[o for idx, o in enumerate(
                obj) if idx not in indexes_to_delete] for obj in reader]

            writer = csv.writer(output)
            writer.writerows(result)

            output.seek(0)
            self.cached_game_list = dict(csv.reader(output))
        return self.cached_game_list

    def disable_storage(self):
        """Set the Storage's operation state to Disabled, effectively
        disabling all Storage dependent features on the app"""
        self.operation_state = self.OperationState.DISABLED

    def should_resize(self, art_type: str) -> bool:
        """Checks whether an art file should be automatically resized or not
        based on its art type"""
        return art_type == "COV" or art_type == "LAB"\
            or art_type == "SCR" or art_type == "BG"

    def resize_artwork(self, art_type: str, image_data: bytes, path: str) -> BytesIO:
        file_format = "jpeg" if path.split(".")[-1] == "jpg" else "png"
        output: BytesIO = BytesIO()
        if self.should_resize(art_type):
            image = Image.open(BytesIO(image_data))
            image = image.resize(self.PS2_ART_SIZES[art_type])
            image.save(output, file_format)
        else:
            output.write(image_data)
        output.seek(0)
        return output

    def get_filename_options(self, region_code: str, art_type: str, url: str = None) -> Iterator[Tuple[str, str]]:
        if art_type != "SCR" and art_type != "BG":
            return [(
                self.storage_location +
                f"PS2/{region_code}/{region_code}_{art_type}.jpg",
                self.storage_location +
                f"PS2/{region_code}/{region_code}_{art_type}.png",
            )]
        else:
            return urls_for_odd_type(region_code, art_type, url)

    def __get_already_existing_art_types_for_game(self, region_code) -> Set[str]:
        existing = self.opl_dir.glob(f"ART/{region_code}*")
        return set(
                map(lambda x: re.findall(r'S[a-zA-Z]{3}.?\d{3}\.?\d{2}_([A-Z]*2?)', x.name)[0], existing)
            )

    def get_artwork_for_game(self, region_code: str, overwrite: bool) -> Dict[str, str | Path]:
        """Retrieves  all artwork files related to a title, properly resizes them 
        and places them in the OPL ART directory.

        Returns all the kinds of art files it found and their locations in the 
        storage."""

        final_locations: Dict[str, str | Path] = {}

        existing_types = self.__get_already_existing_art_types_for_game(region_code)

        for art_type in self.PS2_TYPES_OF_ART:
            if art_type in existing_types and not overwrite:
                continue
            match self.operation_state:
                case self.OperationState.ONLINE:
                    possible_locations = self.get_filename_options(
                        region_code, art_type, self.storage_location)
                    # File can be either a jpg or png
                    if art_type != "SCR" and art_type != "BG":
                        final_location: str = ""
                        # Check which extension our storage has for this filetype
                        for location in possible_locations[0]:
                            try:
                                art_file_path = self.opl_dir.joinpath(
                                    "ART", location.split('/')[-1])
                                if not art_file_path.exists() or overwrite:
                                    with urlopen(location) as dl_art_file, \
                                            art_file_path.open('wb') as art_file:
                                        # If file download is successful, copy to ART directory resized
                                        art_file.write(self.resize_artwork(
                                            art_type, dl_art_file.read(), location).read())
                                        final_location = location
                                        break
                            except HTTPError:
                                pass
                        if final_location:
                            final_locations[art_type] = final_location
                    else:
                        found_locations: List[str] = []
                        count = 0

                        for possibilities in possible_locations:
                            found = False
                            # Try to find up to 2 screenshots or backgrounds from storage
                            for possibility in possibilities:
                                try:
                                    with urlopen(possibility) as dl_art_file:
                                        found_locations.append(possibility)
                                        file_extension = possibility.split(
                                            '.')[-1]
                                        dest_filename = f"{region_code}_{art_type}{'' if count == 0 else '2'}.{file_extension}"
                                        count += 1

                                        art_file_path = self.opl_dir.joinpath(
                                            "ART", dest_filename)

                                        if not art_file_path.exists() or overwrite:
                                            art_file = art_file_path.open('wb')

                                            art_file.write(self.resize_artwork(
                                                art_type, dl_art_file.read(), possibility).read())
                                            art_file.close()
                                            found = True
                                            break
                                except HTTPError:
                                    pass
                            if not found or len(found_locations) > 1:
                                break

                        for (i, location) in enumerate(found_locations):
                            final_locations[f"{art_type}{i+1}"] = location
                case self.OperationState.FILESYSTEM:
                    if art_type != "SCR" and art_type != "BG":
                        # Just find files and copy them to OPL dir
                        art_file = list(self.storage_location.joinpath("PS2", region_code)
                                        .glob(f"{region_code}_{art_type}.*"))
                        if art_file:
                            dest_file = self.opl_dir.joinpath(
                                "ART", art_file[0].name)

                            if not art_file_path.exists() or overwrite:
                                if not dest_file.exists():
                                    dest_file.touch()

                                dest_file = dest_file.open('wb')
                                art_file_obj = art_file[0].open('rb')
                                dest_file.write(self.resize_artwork(
                                    art_type, art_file_obj.read(), str(art_file[0])).read())
                                art_file_obj.close()
                                dest_file.close()

                                final_locations[art_type] = art_file[0]
                    else:
                        # Find up to 2 BG or SCR files, rename them to the proper format and copy them
                        art_file: List[Path] = list(self.storage_location.joinpath("PS2", region_code)
                                                    .glob(f"{region_code}_{art_type}_*"))
                        try:
                            for i in range(0, 2):
                                dest_filename = f"{region_code}_{art_type}{'' if i == 0 else '2'}{art_file[i].suffix}"
                                dest_file = self.opl_dir.joinpath(
                                    "ART", dest_filename)

                                if not art_file_path.exists() or overwrite:
                                    if not dest_file.exists():
                                        dest_file.touch()

                                    with dest_file.open("wb") as dest,\
                                            art_file[0].open("rb") as src:
                                        dest.write(self.resize_artwork(
                                            art_type, src.read(), str(art_file[i])).read())

                                    final_locations[f"{art_type}{'' if i == 0 else '2'}"] = art_file[i]
                        except IndexError:
                            pass
                case self.OperationState.DISABLED:
                    raise DisabledException(
                        "Storage features disabled, code should not have reached this point")

        return final_locations

    def get_game_title(self, region_code: str) -> str:
        match self.operation_state:
            case self.OperationState.ONLINE | self.OperationState.FILESYSTEM:
                if self.operation_state == self.OperationState.ONLINE:
                    game_CSV_location = f"{self.storage_location}PS1_LIST.CSV"
                else:
                    game_CSV_location = 'file://' + quote(str(self.storage_location.joinpath("PS1_LIST.CSV")))

                try:
                    # On the august backup the PS2 games are located in PS1_LIST.CSV....
                    processed_csv = self.process_game_list_csv(game_CSV_location)
                    return processed_csv[region_code]
                except HTTPError as e:
                    print("Cannot find game list in online storage, not retrieving name for " + region_code, file=stderr)
                except URLError as e:
                    print("Cannot find game list in storage, not retrieving name for " + region_code, file=stderr)
                except KeyError:
                    print("Cannot find game " + region_code + " in PS1_LIST.CSV in the storage, not retrieving name.", file=stderr)
            case self.OperationState.DISABLED:
                raise DisabledException(
                    "Storage features disabled, code should not have reached this point")


class DisabledException(Exception):
    pass
