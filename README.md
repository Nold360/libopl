# libOPL - Poor-Python OPL-Manager & Library
This Repository containes the code for "popl". Popl is a simple Python implementation
of the "OPL Manager". While popl is the cli frontend, it's sub-classes can also
be used as a library to parse the "ul.cfg", split games to ul-format, download artwork, fix filenames, etc.

## Features
 - Add game images (iso's) to OPL-Drive 
   - Split them to UL-Format if needed/wanted
 - Read, write & merge ul.cfg
 - Download artwork for all games on drive from open API
 - List all games on a OPL-Drive
 - init OPL-Drive with all needed folders
 - Fix game names & artwork for all games on drive


## ToDo / Limitations / Known Bugs:
 - Fix "fix" function - lol
 - Lots of cleanup & error handling
 - Very buggy, alpha state code by a bad non-coder
 - Currently only available for Linux (port yourself)


## Installation
On Linux:
```
 pip3 install libopl
```


## Usage
```
$ libopl/opl.py  --help
usage: opl.py [-h] [-f] {list,add,artwork,fix,init} ...

positional arguments:
  {list,add,artwork,fix,init}
                        Choose your path...
    list                List Games on OPL-Drive
    add                 Add Media Image to OPL-Drive
    artwork             Download Artwork onto opl_drive
    fix                 rename/fix media filenames
    init                Initialize OPL-Drive folder-structure

optional arguments:
  -h, --help            show this help message and exit
  -f, --foo
```
