VERSION = (0, 2, 0)

import sys, argparse, os.path, json, io, glob, time
import pathlib, urllib.request, shutil
from collections import OrderedDict

from common import prints


parser = argparse.ArgumentParser()
parser.add_argument('-v', '--version', help='Target version ; the version must be installed.\nr or release for the last release\ns or snapshot for the last snapshot.')

parser.add_argument('-q', '--quiet', help='Execute without any user interaction. Require --version or --manifest-json.', action='store_true')
parser.add_argument('-f', '--overwrite', help='Overwrite on the existing output folder.', action='store_true')

parser.add_argument('-z', '--zip', help='Empack the folder in a zip after it\'s creation', action='store_true', default=None)
parser.add_argument('--no-zip', dest='zip', help='Don\'t ask for empack the folder in a zip', action='store_false')

parser.add_argument('-o', '--output', help='Output folder', type=pathlib.Path)
parser.add_argument('--manifest-json', help='Local JSON manifest file of the target version.', type=pathlib.Path)

args = parser.parse_args()

def main():
    from common import GITHUB_BUILDER, valide_version, valide_output, work_done
    
    prints(f'--==| Minecraft: Generated data builder {VERSION} |==--')
    prints()
    
    last, _, _ = GITHUB_BUILDER.check_releases()
    if last > VERSION:
        prints('A new version is available!')
        prints()
    
    args.version = valide_version(args.version, args.quiet, args.manifest_json)
    
    valide_output(args)
    
    if args.zip == None:
        if args.quiet:
            args.zip = False
        else:
            prints('Do you want to empack the Generated data folder in a ZIP file?')
            args.zip = input()[:1] == 'y'
    
    prints()
    
    error = build_generated_data(args)
    work_done(error, args.quiet)
    return error


def build_generated_data(args):
    from common import run_animation, read_json, write_json, write_lines, safe_del, find_output, get_latest, read_manifest_json
    
    import subprocess, zipfile
    from tempfile import gettempdir
    from datetime import datetime
    
    version = get_latest(args.version, args.manifest_json)
    
    temp = os.path.join(gettempdir(), 'MC Generated data', version)
    os.makedirs(temp, exist_ok=True)
    
    
    manifest_json, manifest_url = read_manifest_json(temp, version, args.manifest_json)
    
    
    version_json = OrderedDict()
    version_json['id'] = manifest_json['id']
    version_json['type'] = manifest_json['type']
    version_json['time'] = manifest_json['time']
    version_json['releaseTime'] = manifest_json['releaseTime']
    version_json['url'] = manifest_url
    version_json['assets'] = manifest_json['assets']
    
    if 'assetIndex' in manifest_json:
        #minecraft/original manifest
        version_json['asset_index'] = manifest_json['assetIndex']['url']
        version_json['client'] = manifest_json['downloads']['client']['url']
        version_json['client_mappings'] = manifest_json['downloads'].get('client_mappings', {}).get('url', None)
        version_json['server'] = manifest_json['downloads'].get('server', {}).get('url', None)
        version_json['server_mappings'] = manifest_json['downloads'].get('server_mappings', {}).get('url', None)
    else:
        #mc Generated data manifest
        version_json['asset_index'] = manifest_json['asset_index']
        version_json['client'] = manifest_json['client']
        version_json['client_mappings'] = manifest_json['client_mappings']
        version_json['server'] = manifest_json['server']
        version_json['server_mappings'] = manifest_json['server_mappings']
    
    def build_path():
        from common import VERSION_MANIFEST
        for k,v in VERSION_MANIFEST['versioning'].items():
            if k == 'special':
                if version in v:
                    return os.path.join('special', version)
            else:
                if version in v.get('releases', []):
                    return os.path.join('releases', version)
                
                for kk,vv in v.items():
                    if version in vv:
                        return os.path.join('snapshots', k, kk, version)
    
    output = os.path.join(args.output, version) if args.output else find_output(version) or build_path() or os.path.join(version_json['type'], version)
    
    
    if os.path.exists(output) and not args.overwrite:
        prints(f'Imposible to build Generated data for {version}. The output "{output}" already exit and the overwrite is not enabled.')
        return -1
    
    
    prints(f'Build Generated data for {version}')
    
    fix = datetime.fromisoformat('2021-09-21T14:36:06+00:00')
    dt = datetime.fromisoformat(version_json['releaseTime'])
    
    prints()
    
    client = os.path.join(temp, 'client.jar')
    async def client_dl():
        if not os.path.exists(client):
            urllib.request.urlretrieve(version_json['client'], client)
    run_animation(client_dl, 'Downloading client.jar', '> OK')
    
    server = os.path.join(temp, 'server.jar')
    async def server_dl():
        if version_json['server'] and not os.path.exists(server):
            urllib.request.urlretrieve(version_json['server'], server)
    run_animation(server_dl, 'Downloading server.jar', '> OK')
    
    async def data_server():
        for cmd in ['-DbundlerMainClass=net.minecraft.data.Main -jar server.jar --all', '-cp server.jar net.minecraft.data.Main --all']:
            subprocess.run('java ' + cmd, cwd=temp, shell=False, capture_output=False, stdout=subprocess.DEVNULL)
    run_animation(data_server, 'Extracting data server', '> OK')
    
    
    async def data_client():
        with zipfile.ZipFile(client, mode='r') as zip:
            for entry in zip.filelist:
                if entry.filename.startswith('assets/') or entry.filename.startswith('data/'):
                    safe_del(os.path.join(temp, 'generated', entry.filename))
                    zip.extract(entry.filename, os.path.join(temp, 'generated'))
            
            if not os.path.exists(os.path.join(temp, 'generated', 'assets')):
                for entry in zip.filelist:
                    if entry.filename.endswith('.png') or entry.filename.endswith('.txt') or entry.filename.endswith('.lang'):
                        safe_del(os.path.join(temp, 'generated/assets', entry.filename))
                        zip.extract(entry.filename, os.path.join(temp, 'generated/assets'))
                pass
            
    run_animation(data_client, 'Extracting data client', '> OK')
    
    
    write_json(os.path.join(temp, 'generated', version+'.json') , version_json)
    
    async def listing_various():
        
        for dir in ['libraries', 'logs', 'tmp', 'versions', 'generated/.cache', 'generated/assets/.mcassetsroot', 'generated/data/.mcassetsroot']:
            safe_del(os.path.join(temp, dir))
        
        registries = [k for k in read_json(os.path.join(temp, 'generated/reports/registries.json')).keys()]
        registries.sort()
        if registries:
            write_lines(os.path.join(temp, 'generated/lists/registries.txt'), registries)
        
        blockstates = {}
        
        for k,v in read_json(os.path.join(temp, 'generated/reports/blocks.json')).items():
            name = k.split(':', maxsplit=2)[-1]
            v.pop('states', None)
            write_json(os.path.join(temp, 'generated/lists/blocks', name+'.json') , v)
            
            for vk in v:
                if vk not in blockstates:
                    blockstates[vk] = {}
                
                for vs in v[vk]:
                    if vs not in blockstates[vk]:
                        blockstates[vk][vs] = {}
                    
                    for vv in v[vk][vs]:
                        if vv not in blockstates[vk][vs]:
                            blockstates[vk][vs][vv] = []
                        
                        blockstates[vk][vs][vv].append(k)
        
        for k,v in blockstates.items():
            if k == 'properties':
                for kk,vv in v.items():
                    for zk,zv in vv.items():
                        write_lines(os.path.join(temp, 'generated/lists/blocks/properties', kk+'='+zk+'.txt') , sorted(zv))
            else:
                for kk,vv in v.items():
                    write_json(os.path.join(temp, 'generated/lists/blocks/', k, kk+'.json'), vv)
        
        nbt = ['minecraft:'+j[:-4].replace('\\', '/') for j in glob.glob(f'**/*.nbt', root_dir=os.path.join(temp, 'generated/data/minecraft/structures'), recursive=True)]
        nbt.sort()
        if nbt:
            write_lines(os.path.join(temp, 'generated/lists', 'structures.nbt.txt'), nbt)
        
        for k,v in read_json(os.path.join(temp, 'generated/reports/commands.json')).get('children', {}).items():
            write_json(os.path.join(temp, 'generated/lists/commands/', k+'.json') , v)
        
        def enum_json(dir):
            return [j[:-5].replace('\\', '/') for j in glob.glob(f'**/*.json', root_dir=dir, recursive=True)]
        
        for k,v in read_json(os.path.join(temp, 'generated/reports/registries.json')).items():
            name = k.split(':', maxsplit=2)[-1]
            
            tags = os.path.join(temp,'generated/data/minecraft/tags', name)
            if not os.path.exists(tags):
                tags = tags + 's'
            
            entries = [k for k in v['entries'].keys()]
            tags = ['#minecraft:'+j for j in enum_json(tags)]
            entries.sort()
            tags.sort()
            write_lines(os.path.join(temp, 'generated/lists', name +'.txt'), entries + tags)
        
        dir = os.path.join(temp, 'generated/data/minecraft/worldgen')
        if not os.path.exists(dir):
            dir = os.path.join(temp, 'generated/reports/minecraft/worldgen') # old
            if not os.path.exists(dir):
                dir = os.path.join(temp, 'generated/reports/worldgen/minecraft/worldgen') # legacy
        
        if os.path.exists(dir):
            for dir in os.scandir(dir):
                if dir.is_dir:
                    folder = ['minecraft:'+j for j in enum_json(dir.path)]
                    tags = ['#minecraft:'+j for j in enum_json(os.path.join(temp,'generated/data/minecraft/tags/worldgen', dir.name))]
                    folder.sort()
                    tags.sort()
                    write_lines(os.path.join(temp, 'generated/lists/worldgen', dir.name +'.txt'), folder + tags)
        
        dir = os.path.join(temp, 'generated/reports/biomes') #legacy
        if os.path.exists(dir):
            write_lines(os.path.join(temp, 'generated/lists/worldgen', 'biomes.txt'), sorted(['minecraft:'+b for b in enum_json(dir)]))
        
    
    run_animation(listing_various, 'Listing elements and various', '> OK')
    
    
    if args.zip:
        async def make_zip():
            zip_path = os.path.join(temp, 'zip.zip')
            safe_del(zip_path)
            shutil.make_archive(os.path.splitext(zip_path)[0], 'zip', root_dir=os.path.join(temp, 'generated'))
            os.rename(zip_path, os.path.join(temp, 'generated', version+'.zip'))
        run_animation(make_zip, 'Empack into a ZIP', '> OK')
    
    async def move_generated_data():
        if os.path.exists(output):
            if args.overwrite:
                safe_del(output)
            else:
                prints(f'The output at "{output}" already exit and the overwrite is not enable')
                return -1
        
        os.makedirs(output, exist_ok=True)
        for dir in os.listdir(os.path.join(temp, 'generated')):
            shutil.move(os.path.join(temp, 'generated', dir), os.path.join(output, dir))
        
    run_animation(move_generated_data, f'Move generated data to "{output}"', '> OK')
    



if __name__ == "__main__":
    main()