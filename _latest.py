import sys

print('--==| Minecraft: Build latest Generated data |==--')
print()

from common import get_latest
from generated_data_builder import args, build_generated_data

LATEST = get_latest('l')
print('\tthe latest version is '+ LATEST)

args.manifest_json = None
args.overwrite = False
args.output = None
args.quiet = True
args.zip = True

args.version = LATEST
build_generated_data(args)

print()
print('Latest => Done')