import sys, os.path as path

print('--==| Minecraft: Update all Generated data |==--')
print()
print('It can be a lot of files, are you sure to do it?')
if not input()[:1].lower() == 'y': sys.exit()

from common import VERSION_MANIFEST, version_path, run_command
from generated_data_builder import args, build_generated_data

args.manifest_json = None
args.overwrite = False
args.output = None
args.quiet = True
args.zip = True


versions = []
for version in VERSION_MANIFEST['versions']:
    versions.append(version['id'])
    if versions[-1] == '1.0':
        break
versions.reverse()
version_path = {v:version_path(v) for v in versions}

for version,dir in version_path.items():
    if not path.exists(dir):
        args.version = version
        build_generated_data(args)

print('All => Done')
