VERSION = (0, 2, 0)

import sys, argparse, os.path, json, io, glob, time
import pathlib, urllib.request, shutil, hashlib
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
    from common import run_animation, read_json, write_json, write_lines, safe_del
    from common import find_output, get_latest, read_manifest_json, version_path, hash_file, make_dirname
    
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
    
    output = os.path.join(args.output, version) if args.output else find_output(version) or version_path(version) or os.path.join(version_json['type'], version)
    
    
    if os.path.exists(output) and not args.overwrite:
        prints(f'Imposible to build Generated data for {version}. The output "{output}" already exit and the overwrite is not enabled.')
        return -1
    
    
    prints(f'Build Generated data for {version}')
    
    dt = datetime.fromisoformat(version_json['releaseTime'])
    
    prints()
    
    client = os.path.join(temp, 'client.jar')
    async def client_dl():
        if not os.path.exists(client):
            urllib.request.urlretrieve(version_json['client'], client)
    run_animation(client_dl, 'Downloading client.jar', '> OK')
    
    global assets, assets_json
    assets = assets_json = {}
    
    def write_asset(file):
        if file in assets:
            asset = assets[file]
            file = os.path.join(temp,'generated/assets',file)
            if hash_file(hashlib.sha1(), file) != asset['hash']:
                safe_del(file)
                make_dirname(file)
                urllib.request.urlretrieve(asset['url'], file)
    
    async def assets_dl():
        global assets, assets_json
        assets_json['assets'] = version_json['assets']
        assets_json['asset_index'] = version_json['asset_index']
        
        assets_file = os.path.join(temp, 'assets.json')
        if not os.path.exists(assets_file):
            urllib.request.urlretrieve(version_json['asset_index'], assets_file)
        
        for k,v in read_json(assets_file).items():
            if k == 'objects':
                assets = v
            else:
                assets_json[k] = v
        
        assets = {k:assets[k] for k in sorted(assets.keys())}
        for a in assets:
            hash = assets[a]['hash']
            assets[a]['url'] = 'http://resources.download.minecraft.net/'+hash[0:2]+'/'+hash
        
        assets_json['objects'] = assets
        
    run_animation(assets_dl, 'Downloading assets', '> OK')
    
    
    if dt.year >= 2018:
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
            
            for a in ['minecraft/sounds.json', 'sounds.json', 'pack.mcmeta']:
                write_asset(a)
            
    run_animation(data_client, 'Extracting data client', '> OK')
    
    
    write_json(os.path.join(temp, 'generated',version+'.json') , version_json)
    write_json(os.path.join(temp, 'generated','assets.json'), assets_json)
    
    async def listing_various():
        
        for f in ['libraries', 'logs', 'tmp', 'versions', 'generated/.cache', 'generated/tmp', 'generated/assets/.mcassetsroot', 'generated/data/.mcassetsroot']:
            safe_del(os.path.join(temp, f))
        
        registries = [k for k in read_json(os.path.join(temp, 'generated/reports/registries.json')).keys()]
        registries.sort()
        if registries:
            write_lines(os.path.join(temp, 'generated/lists/registries.txt'), registries)
        
        blockstates = {}
        
        # blocks
        for k,v in read_json(os.path.join(temp, 'generated/reports/blocks.json')).items():
            name = k.split(':', maxsplit=2)[1]
            
            states = []
            for bs in v.pop('states', {}):
                default = bs.get('default', False)
                properties = bs.get('properties', {})
                if properties:
                    states.append(','.join(['='.join(s) for s in properties.items()]) + ('  [default]' if default else ''))
            
            if states:
                write_lines(os.path.join(temp, 'generated/lists/blocks/states', name+'.txt') , states)
            
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
        
        # structures.nbt
        dir = os.path.join(temp, 'generated/data/minecraft/structures')
        if not os.path.exists(dir):
            dir = os.path.join(temp, 'generated/assets/minecraft/structures') # old
        nbt = ['minecraft:'+j[:-4].replace('\\', '/') for j in glob.glob('**/*.nbt', root_dir=dir, recursive=True)]
        nbt.sort()
        if nbt:
            write_lines(os.path.join(temp, 'generated/lists', 'structures.nbt.txt'), nbt)
        
        # loot_tables
        dir = os.path.join(temp, 'generated/data/minecraft/loot_tables')
        if not os.path.exists(dir):
            dir = os.path.join(temp, 'generated/assets/minecraft/loot_tables') # old
        for loot in glob.glob('**/*.json', root_dir=dir, recursive=True):
            if loot == 'empty.json':
                continue
            table = read_json(os.path.join(dir, loot))
            simple = []
            
            def test_type(name, target):
                return name == target or name == 'minecraft:'+target
            
            if loot.startswith('blocks'):
                continue
            else:
                
                for l in table.get('pools', {}):
                    if 'items' in l:
                        for e in l['items']:
                            simple.append(e.get('item', 'minecraft:empty'))
                    elif 'entries' in l:
                        for e in l['entries']:
                            t = e['type']
                            if test_type(t, 'empty'):
                                simple.append('minecraft:empty')
                            elif test_type(t, 'item'):
                                simple.append(e['name'])
                            elif test_type(t, 'tag'):
                                simple.append('#'+e['name'])
                            elif test_type(t, 'loot_table'):
                                simple.append('loot_table[]'+e['name'])
                            else:
                                raise TypeError("Unknow type '{}' in loot_tables '{}'".format(t,loot))
                    
                    simple.append('')
            
            while simple and not simple[-1]:
                simple.pop(-1)
            
            write_lines(os.path.join(temp, 'generated/lists/loot_tables', os.path.splitext(loot)[0]+'.txt'), simple)
        
        
        # commands
        for k,v in read_json(os.path.join(temp, 'generated/reports/commands.json')).get('children', {}).items():
            write_json(os.path.join(temp, 'generated/lists/commands/', k+'.json') , v)
        
        
        # registries
        def enum_json(dir):
            return [j[:-5].replace('\\', '/') for j in glob.iglob('**/*.json', root_dir=dir, recursive=True)]
        
        for k,v in read_json(os.path.join(temp, 'generated/reports/registries.json')).items():
            name = k.split(':', maxsplit=2)[1]
            
            tags = os.path.join(temp,'generated/data/minecraft/tags', name)
            if not os.path.exists(tags):
                tags = tags + 's'
            
            entries = [k for k in v['entries'].keys()]
            tags = ['#minecraft:'+j for j in enum_json(tags)]
            entries.sort()
            tags.sort()
            write_lines(os.path.join(temp, 'generated/lists', name +'.txt'), entries + tags)
        
        
        # worldgen
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
            write_lines(os.path.join(temp, 'generated/lists/worldgen', 'biome.txt'), sorted(['minecraft:'+b for b in enum_json(dir)]))
        
        
        # sounds
        for sounds in ['minecraft/sounds.json', 'sounds.json']:
            sounds = os.path.join(temp,'generated/assets',sounds)
            if os.path.exists(sounds):
                for k,v in read_json(sounds).items():
                    write_json(os.path.join(temp,'generated/lists/sounds/', k+'.json'), v)
                    
                    lines = v['sounds']
                    for idx,v in enumerate(lines):
                        if isinstance(v, dict):
                            lines[idx] = v['name']
                    write_lines(os.path.join(temp,'generated/lists/sounds/', k+'.txt'), lines)
                
                break
        
        
        # languages
        pack_mcmeta = os.path.join(temp,'generated/assets','pack.mcmeta')
        src_lang = read_json(pack_mcmeta).get('language', None)
        if src_lang:
            languages = {}
            for en in ['en_us', 'en_US']:
                if en in src_lang:
                    languages['en_us'] = src_lang.pop(en)
            languages.update({l.lower():src_lang[l] for l in sorted(src_lang.keys())})
            write_json(os.path.join(temp,'generated/lists', 'languages.json'), languages)
        
        safe_del(pack_mcmeta)
        
    
    run_animation(listing_various, 'Listing elements and various', '> OK')
    
    
    if args.zip:
        async def make_zip():
            zip_path = os.path.join(temp, 'zip.zip')
            zip_version_path = os.path.join(temp, 'generated', version+'.zip')
            safe_del(zip_path)
            safe_del(zip_version_path)
            shutil.make_archive(os.path.splitext(zip_path)[0], 'zip', root_dir=os.path.join(temp, 'generated'))
            os.rename(zip_path, zip_version_path)
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