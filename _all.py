import sys

print('--==| Minecraft: Build all Generated data |==--')
print()
print('It can be a lot of files, are you sure to do it?')
if not input()[:1] == 'y': sys.exit()

from builder.generated_data_builder import args, build_generated_data, version_manifest


args.manifest_json = None
args.overwrite = False
args.output = None
args.quiet = True
args.zip = True

for version in version_manifest["paths"]:
    args.version = version
    print(args)
    
    build_generated_data(args)

print('All => Done')