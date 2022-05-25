VERSION = (1, 0, 0)

import sys, argparse, os.path, json, io, glob, time
import pathlib, urllib.request, shutil
from collections import OrderedDict

from common import prints


parser = argparse.ArgumentParser()
parser.add_argument('-v', '--version', help='Target version ; the version must be installed.\nr or release for the last release\ns or snapshot for the last snapshot.')

parser.add_argument('-q', '--quiet', help='Execute without any user interaction. Require --version or --manifest-json.', action='store_true')
parser.add_argument('-f', '--overwrite', help='Overwrite on the existing output folder.', action='store_true')

parser.add_argument('-o', '--output', help='Output folder', type=pathlib.Path)
parser.add_argument('--manifest-json', help='Local JSON manifest file of the target version.', type=pathlib.Path)

args = parser.parse_args()

def main():
    from common import valide_version, find_output, valide_output, work_done
    
    prints(f'--==| Minecraft: Assets Unindexer |==--')
    prints()
    
    args.version = valide_version(args.version, args.quiet, args.manifest_json)
    
    valide_output(args)
    
    prints()
    
    error = unindex_assets(args)
    work_done(error, args.quiet)
    return error


def unindex_assets(args):
    from common import run_animation, make_dirname, read_json, write_json, write_lines, safe_del, find_output, get_latest, read_manifest_json
    
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
        prints(f'Imposible to unindex assets for {version}. The output "{output}" already exit and the overwrite is not enabled.')
        return -1
    
    temp = os.path.join(gettempdir(), 'MC Assets data', version)
    assets_json_path = os.path.join(temp, version+'.json')
    make_dirname(assets_json_path)
    
    
    async def index_dl():
        urllib.request.urlretrieve(assets_json['asset_index'], assets_json_path)
        pass
    run_animation(index_dl, 'Downloading index.json', '> OK')
    
    for k,v in read_json(assets_json_path).items():
        assets_json[k] = v
    
    write_json(assets_json_path, assets_json)
    
    
    async def assets_dl():
        import hashlib
        from common import hash_file
        
        def link_asset(hash):
            return 'http://resources.download.minecraft.net/'+hash[0:2]+'/'+hash
        
        for name,v in assets_json['objects'].items():
            path = os.path.join(temp, name)
            hash = v['hash']
            
            hash2 = hash_file(hashlib.sha1(), path)
            
            if hash != hash2:
                safe_del(path)
                make_dirname(path)
                urllib.request.urlretrieve(link_asset(hash), path)
        
    run_animation(assets_dl, 'Downloading assets', '> OK')
    
    
    async def list_assets():
        jr = None
        for p in ['minecraft/sounds.json', 'sounds.json']:
            jr = os.path.join(temp, p)
            if os.path.exists(jr):
                break
        
        for k,v in read_json(os.path.join(temp, jr)).items():
            write_json(os.path.join(temp, 'lists/sounds/', k+'.json'), v)
            
            lines = v['sounds']
            for idx,v in enumerate(lines):
                try:
                    lines[idx] = v['name']
                except:
                    pass
            write_lines(os.path.join(temp, 'lists/sounds/', k+'.txt'), lines)
        
    run_animation(list_assets, 'List assets', '> OK')
    
    
    async def copy_assets_data():
        if os.path.exists(output):
            if args.overwrite:
                safe_del(output)
            else:
                prints(f'The output at "{output}" already exit and the overwrite is not enable')
                return -1
        
        shutil.copytree(temp, output)
        
    run_animation(copy_assets_data, f'Move generated data to "{output}"', '> OK')
    



if __name__ == "__main__":
    main()