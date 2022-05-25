import sys

print('--==| Minecraft: Build latest Generated data |==--')
print()

from generated_data_builder import args, build_generated_data

args.manifest_json = None
args.overwrite = False
args.output = '..'
args.quiet = True
args.zip = False

args.version = 'l'
build_generated_data(args)

print()
print('Latest => Done')