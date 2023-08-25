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
