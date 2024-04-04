VERSION = (1, 0, 1)

import argparse
import os.path
import pathlib
import shutil
from collections import OrderedDict

from common import (
    find_output, get_latest, hash_test, make_dirname, read_json,
    read_manifest_json, run_animation, safe_del, urlretrieve,
    valide_output, valide_version, work_done, write_json, write_lines,
)

parser = argparse.ArgumentParser()
parser.add_argument('-v', '--version', help='Target version ; the version must be installed.\nr or release for the last release\ns or snapshot for the last snapshot.')

parser.add_argument('-q', '--quiet', help='Execute without any user interaction. Require --version or --manifest-json.', action='store_true')
parser.add_argument('-f', '--overwrite', help='Overwrite on the existing output folder.', action='store_true')

parser.add_argument('-o', '--output', help='Output folder', type=pathlib.Path)
parser.add_argument('--manifest-json', help='Local JSON manifest file of the target version.', type=pathlib.Path)

args = parser.parse_args()

def main():
    print(f'--==| Minecraft: Assets Unindexer |==--')
    print()
    
    args.version = valide_version(args.version, args.quiet, args.manifest_json)
    
    valide_output(args)
    
    print()
    
    error = unindex_assets(args)
    work_done(error, args.quiet)
    return error


def unindex_assets(args):
    from tempfile import gettempdir
    
    version = get_latest(args.version, args.manifest_json)
    
    
    temp = os.path.join(gettempdir(), 'MC Assets data')
    if not os.path.exists(temp):
        os.makedirs(temp)
    
    
    manifest_json, manifest_url = read_manifest_json(temp, version, args.manifest_json)
    
    
    assets_json = OrderedDict()
    assets_json['assets'] = version = manifest_json['assets']
    
    if 'assetIndex' in manifest_json:
        assets_json['asset_index'] = manifest_json['assetIndex']['url']
    else:
        assets_json['asset_index'] = manifest_json['asset_index']
    
    output = os.path.join(args.output, version) if args.output else find_output('assets/assets-'+version) or 'assets/assets-'+version
    
    if os.path.exists(output) and not args.overwrite:
        print(f'Imposible to unindex assets for {version}. The output "{output}" already exit and the overwrite is not enabled.')
        return -1
    
    temp = os.path.join(gettempdir(), 'MC Assets data', version)
    assets_json_path = os.path.join(temp, version+'.json')
    make_dirname(assets_json_path)
    
    
    async def index_dl():
        urlretrieve(assets_json['asset_index'], assets_json_path)
        pass
    run_animation(index_dl, 'Downloading index.json')
    
    for k,v in read_json(assets_json_path).items():
        assets_json[k] = v
    
    for k,v in assets_json['objects'].items():
        hash = v['hash']
        v['url'] = 'http://resources.download.minecraft.net/'+hash[0:2]+'/'+hash
    
    write_json(assets_json_path, assets_json)
    
    
    async def assets_dl():
        for name,asset in assets_json['objects'].items():
            file = os.path.join(temp, name)
            
            if not hash_test(asset['hash'], file):
                safe_del(file)
                make_dirname(file)
                urlretrieve(asset['url'], file)
        
    run_animation(assets_dl, 'Downloading assets')
    
    
    async def list_assets():
        for sounds in ['minecraft/sounds.json', 'sounds.json']:
            sounds = os.path.join(temp, sounds)
            if os.path.exists(sounds):
                for k,v in read_json(sounds).items():
                    write_json(os.path.join(temp,'lists/sounds', k+'.json'), v)
                    
                    lines = v['sounds']
                    for idx,v in enumerate(lines):
                        if isinstance(v, dict):
                            lines[idx] = v['name']
                    write_lines(os.path.join(temp,'lists/sounds', k+'.txt'), lines)
                
                break
        
        src_lang = read_json(os.path.join(temp,'pack.mcmeta')).get('language', None)
        if src_lang:
            languages = {}
            for en in ['en_us', 'en_US']:
                if en in src_lang:
                    languages['en_us'] = src_lang.pop(en)
            languages.update({l.lower():src_lang[l] for l in sorted(src_lang.keys())})
            write_json(os.path.join(temp,'lists', 'languages.json'), languages)
        
        
    run_animation(list_assets, 'List assets')
    
    
    async def copy_assets_data():
        if os.path.exists(output):
            if args.overwrite:
                safe_del(output)
            else:
                print(f'The output at "{output}" already exit and the overwrite is not enable')
                return -1
        
        shutil.copytree(temp, output)
        
    run_animation(copy_assets_data, f'Move generated data to "{output}"')


if __name__ == "__main__":
    main()
