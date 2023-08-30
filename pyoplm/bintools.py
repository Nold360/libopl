import re
import subprocess
from collections import namedtuple
from pathlib import Path
import sys

BinMergeArgs = namedtuple("BinMergeArgs", ["outdir", "license", "split", "cuefile", "basename"])
Cue2PopsArgs = namedtuple("Cue2PopsArgs", ["input_file", "gap", "vmode", "trainer", "output_file"])
BChunkArgs = namedtuple("BChunkArgs", ["p", "src_bin", "src_cue", "basename"])

cue2pops_location = Path(
    __file__).parent.joinpath("lib", "linux64", "cue2pops", "cue2pops")
bchunk_location = Path(
    __file__).parent.joinpath("lib", "linux64", "bchunk", "bchunk")
binmerge_location = Path(
    __file__).parent.joinpath("lib", "linux64", "binmerge", "binmerge")

def cue2pops(args: Cue2PopsArgs):
    args_list = [cue2pops_location.absolute().as_posix(), args.input_file or '',
                 f"gap{args.gap}" if args.gap else '', 'vmode' if args.vmode else '', 'trainer' if args.trainer else '', args.output_file or '']
    args_list = list(filter(bool, args_list))
    complete = subprocess.run(args_list)
    return complete.returncode

def bchunk(args: BChunkArgs, outdir=None):
    args_list = [bchunk_location.absolute().as_posix(), '-p' if args.p else '', args.src_bin, args.src_cue, args.basename]
    args_list = list(filter(bool, args_list))
    complete = subprocess.run(args_list, cwd=None)
    return complete.returncode

def binmerge(args: BinMergeArgs):
    args_list = [binmerge_location.absolute().as_posix(), ('-o' + args.outdir) or '', '-l' if args.license else '', '-s' if args.split else '',
                args.cuefile.absolute().as_posix(), args.basename or '']
    args_list = list(filter(bool, args_list))
    complete = subprocess.run(args_list)
    return complete.returncode


