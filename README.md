# libOPL - Python OPL-Manager & Library
This Repository containes the code for libopl. libopl is a simple Python implementation
of the "OPL Manager". While there is a cli frontend, it's sub-classes can also
be used as a library to parse the "ul.cfg", split games to ul-format, fix filenames, etc.

## Features
 - Add, remove and rename games in OPL-Drive 
   - Support for both ISO games and UL
 - Read, write & merge ul.cfg
 - List all games on a OPL-Drive
 - init OPL-Drive with all needed folders
 - Fix game names for all games on drive


## ToDo:
 - Creating a server for self-hosting game metadata and artwork/finding open APIs to get metadata and writing code to query said server
 - Support for adding PS1 games
    - cue/bin >> vcd
    - multitrack cue/bin >> merge to one bin >> vcd
 - Support for installing bin/cue games (convert to ISO)
  - Support for converting multitrack games to ISO (don't even know where to start with this one)
 - Might not work on Windows, i tried my best to make the code platform-independent but i have not tested it


## Installation
```
 pip3 install libopl
```

## Artwork and title database

Due to this being an open source project, a bit of "self hosting" is required to get these features that require storage to work

In order to have support for artwork downloading and game title fetching, you need to either download one of danielb's [OPLM monthly art database backups](https://oplmanager.com/site/?backups) (i tested this program on [OPLM_ART_2023_07.zip](https://archive.org/download/OPLM_ART_2023_07/OPLM_ART_2023_07.zip)) on your system or host the contents of a ZIP backup in a server (like Google cloud storage buckets, i like using Google cloud because of te free trails but you can place the files anywhere), and give this program the location where the backup is unzipped, and then you can download artwork and update titles for any installed game on your drive.

In order to be able to use storage features, you need to create a file named `libopl.ini` in your OPL directory, and insert your storage URL in there  just like in the file `example.libopl.ini` in the root of this repo.

## Usage
```
$ opl --help
usage: opl [-h] {list,add,rename,fix,init,delete} ...

positional arguments:
  {list,add,rename,fix,init,delete}
                        Choose your path...
    list                List Games on OPL-Drive
    add                 Add game to OPL-Drive
    rename              Given an opl_id, change the title of the game corresponding to that
                        ID in the opl_drive
    fix                 rename/fix ISO filenames and corrupted UL entries
    init                Initialize OPL-Drive folder-structure
    delete              Delete game from Drive

options:
  -h, --help            show this help message and exit
```
