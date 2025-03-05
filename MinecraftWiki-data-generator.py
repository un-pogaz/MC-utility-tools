
# Small utility tool to generate data from the game jar,
# for the use of various MinecraftWiki module and template.
# Caution, it recommends to use this tool only on release versions.

__license__   = 'GPL v3'

import argparse
import glob
import os
import shutil
import zipfile
from collections import defaultdict
from tempfile import gettempdir


COMMENT_INFO = {
    '__comment1': 'This file was generated by MinecraftWiki-data-generator.py from the Github repository un-pogaz/MC-utility-tools.',
    '__comment2': 'It recomanded to update this file only for each release version.'
}

DEFAULT_FOLDER = 'MinecraftWiki-data-generator'

args = argparse.ArgumentParser(description=('Small utility tool to generate data from the game jar, for the use of various MinecraftWiki module and template. '
                                            'Caution, it recommends to use this tool only on release versions.'))
args.add_argument('path', type=str, help='Game jar or folder to analyze')
args.add_argument('--output', default=DEFAULT_FOLDER, type=str, help=f'Output folder to write the files. Deault: {DEFAULT_FOLDER}')
args.add_argument('--silent', action='store_true', help='Reduce the printed output messages.')

args_error = args.error


def read_json(path) -> dict:
    import json
    with open(path, 'rt', newline='\n', encoding='utf-8') as f:
        return json.loads(f.read())

def write_json(path, obj, sort_keys: bool=False):
    import json
    with open(path, 'wt', newline='\n', encoding='utf-8') as f:
        f.write(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=sort_keys))


def iglob(pathname: str, recursive: bool, root_dir: str):
    for path in glob.iglob(pathname, recursive=recursive, root_dir=root_dir):
        yield path.replace('\\', '/').strip('/')


def tag_list_generator(work_dir, output_dir, *, version_target=None):
    '''
    Module:Tag_list_generator
    Module:Tag_list_generator/data.json
    '''
    
    rslt = defaultdict(lambda: defaultdict(set[str]))
    rslt.update(COMMENT_INFO)
    rslt['__comment_module1'] = 'data for Module:Tag_list_generator'
    rslt['__comment_module2'] = 'listing of tag used in others tags'
    if version_target:
        rslt['__comment_version'] = version_target
    
    tags_dir = os.path.join(work_dir, 'data/minecraft/tags')
    types = []
    types.extend(iglob('*/', False, tags_dir))
    types.remove('worldgen')
    types.extend(iglob('worldgen/*/', False, tags_dir))
    
    for type in types:
        for tag in iglob('**/*.json', True, os.path.join(tags_dir, type)):
            name = os.path.splitext(tag)[0]
            for e in read_json(os.path.join(tags_dir, type, tag)).get('values', []):
                if e.startswith('#'):
                    rslt[type][e[1:].replace('minecraft:', '')].add(name)
    
    for type,content in list(rslt.items()):
        if not isinstance(content, dict):
            continue
        for tag,values in content.items():
            content[tag] = list(sorted(values))
        if '/' in type:
            rslt[type.rsplit('/', maxsplit=1)[1]] = content
    
    write_json(os.path.join(output_dir, 'Tag_list_generator.json'), rslt, sort_keys=True)


def main(path: str, output: str=None, *, silent=False, version_target=None):
    if not output:
        output = DEFAULT_FOLDER
    
    path = os.path.abspath(path)
    output = os.path.abspath(output)
    
    def prints(*args, **kargs):
        if not silent:
            print(*args, **kargs)
    
    if not os.path.exists(path):
        args_error("Target path don't exist.")
    
    temp_root = None
    work_dir = None
    if os.path.isfile(path):
        if not zipfile.is_zipfile(path):
            args_error('Target file is not a valid zip file.')
        
        prints('Extraction of content...')
        temp_root = os.path.join(gettempdir(), DEFAULT_FOLDER)
        try:
            shutil.rmtree(temp_root)
        except Exception:
            pass
        with zipfile.ZipFile(path) as zip:
            for info in zip.filelist:
                if info.filename.startswith(('assets/', 'data/')):
                    zip.extract(info, temp_root)
        work_dir = temp_root
    
    if os.path.isdir(path):
        work_dir = path
    
    if not work_dir:
        args_error('The target path was not recognized.')
    
    os.makedirs(output, exist_ok=True)
    
    prints('Module:Tag_list_generator...')
    tag_list_generator(work_dir, output, version_target=version_target)
    
    ## clean-up
    try:
        shutil.rmtree(temp_root)
    except Exception:
        pass


if __name__ == '__main__':
    args = args.parse_args()
    main(
        path=args.path,
        output=args.output,
        silent=args.silent,
    )