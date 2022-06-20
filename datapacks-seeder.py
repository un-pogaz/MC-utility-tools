import sys, argparse, os.path, json, time
import pathlib, shutil, zipfile
from collections import OrderedDict

from common import prints


parser = argparse.ArgumentParser()
parser.add_argument('-s', '--seed', help='Seed to set', required=False)
parser.add_argument('datapack', help='Target Worldgen datapack.', type=pathlib.Path, nargs='?')
args = parser.parse_args()

def main():
    prints(f'--==| Minecraft: Datapack Seeder |==--')
    prints('         for 1.16.2 to 1.18.2')
    prints()
    
    datapack = None
    seed = None
    
    if not args.datapack:
        prints('Enter a ZIP datapack:')
        datapack = input()
        if datapack[0] == '"' and datapack[-1] == '"':
            datapack = datapack.strip('"')
        
    else:
        datapack = args.datapack
    
    msg = None
    if not os.path.exists(datapack):
        msg = 'the path does\'t exist.'
    if not os.path.isfile(datapack):
        msg = 'it not a file.'
    if not zipfile.is_zipfile(datapack):
        msg = 'is not a ZIP.'
    
    if msg:
        prints('Invalide target datapack,', msg)
        return -1
    
    if args.seed == None and not args.datapack:
        prints('Enter a seed (blanck to random):')
        args.seed = input()
        if not args.seed.strip(): args.seed = None
    
    if args.seed == None:
        import random
        args.seed = random.getrandbits(64)
        prints('Random seed generated:', str(args.seed))
    
    seed = args.seed
    if isinstance(seed, str):
        try:
            seed = int(seed.strip())
        except:
            prints('Invalid seed, must be a integer.')
    
    datapack_out = os.path.splitext(datapack)[0] +'-'+ str(seed) +'.zip'
    dimensions = {}
    
    with zipfile.ZipFile(datapack, mode='r') as zip:
        for file in zip.filelist:
            if file.filename.startswith('data/minecraft/dimension') and os.path.splitext(file.filename)[1] == '.json':
                with zip.open(file) as zi:
                    dimension = json.load(zi)
                
                old_seed = dimension.get('generator', {}).get('seed', None)
                
                if old_seed != None:
                    dimension['generator']['seed'] = seed
                    dimensions[file.filename] = json.dumps(dimension, indent=2, ensure_ascii=False)
    
    if dimensions:
        with zipfile.ZipFile(datapack, 'r') as zin:
            with zipfile.ZipFile(datapack_out, 'w') as zout:
                zout.comment = zin.comment # preserve the comment
                for item in zin.infolist():
                    if item.filename in dimensions:
                        zout.writestr(item, dimensions[item.filename].encode('utf-8'))
                    else:
                        zout.writestr(item, zin.read(item.filename))
        
        prints(f'The Worldgen datapack "{datapack}" has now set to {seed} seed.')
    else:
        prints(f'The "{datapack}" datapack has no world seed to edit.')

if __name__ == "__main__":
    main()

