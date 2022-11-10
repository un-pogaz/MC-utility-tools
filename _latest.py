import sys

print('--==| Minecraft: Build latest Generated data |==--')
print()

from common import get_latest
from generated_data_builder import args, build_generated_data

args.manifest_json = None
args.overwrite = False
args.output = None
args.quiet = True
args.zip = True

version = get_latest('l')
args.version = version
build_generated_data(args)

print('Latest => Done')
