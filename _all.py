import sys

print('--==| Minecraft: Build all Generated data |==--')
print()
print('It can be a lot of files, are you sure to do it?')
if not input()[:1] == 'y': sys.exit()

from generated_data_builder import args, build_generated_data
from common import VERSION_MANIFEST

args.manifest_json = None
args.overwrite = False
args.output = None
args.quiet = True
args.zip = True

for version in VERSION_MANIFEST['versions']:
    print()
    args.version = version['id']
    print(args)
    
    build_generated_data(args)
    if args.version == '1.0':
        break

print('All => Done')