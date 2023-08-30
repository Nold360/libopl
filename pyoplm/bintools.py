import subprocess
import pathlib

cue2pops_location = pathlib.Path(
    __file__).parent.joinpath("lib", "linux64", "cue2pops", "cue2pops")
bchunk_location = pathlib.Path(
    __file__).parent.joinpath("lib", "linux64", "bchunk", "bchunk")
binmerge_location = pathlib.Path(
    __file__).parent.joinpath("lib", "linux64", "binmerge", "binmerge")

def cue2pops(args):
    args_list = [cue2pops_location.absolute().as_posix(), args.input_file or '',
                 f"gap{args.gap}" if args.gap else '', 'vmode' if args.vmode else '', 'trainer' if args.trainer else '', args.output_file or '']
    args_list = list(filter(bool, args_list))
    subprocess.run(args_list)

def bchunk(args):
    args_list = [bchunk_location.absolute().as_posix(), '-p' if args.p else '', args.src_bin, args.src_cue, args.basedir]
    args_list = list(filter(bool, args_list))
    subprocess.run(args_list)

def binmerge(args):
    args_list = [binmerge_location.absolute().as_posix(), args.outdir or '', '-l' if args.license else '', '-s' if args.license else '',
                args.cuefile.absolute().as_posix(), args.basedir or '']
    args_list = list(filter(bool, args_list))
    subprocess.run(args_list)
