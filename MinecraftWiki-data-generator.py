
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
args.add_argument('-o', '--output', default=DEFAULT_FOLDER, type=str, help=f'Output folder to write the files. Deault: {DEFAULT_FOLDER}')
args.add_argument('-s', '--silent', action='store_true', help='Reduce the printed output messages.')
args.add_argument('-l', '--langs', '--languages', nargs='+', help='Languages to extract/work.')

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


def translation_test(work_dir, output_dir, languages: list[str]=None, *, version_target=None):
    '''
    Create a page for Testing Translation and English Redirection
    '''
    
    lang_dir = os.path.join(work_dir, 'assets/minecraft/lang')
    if not languages:
        languages = []
    if isinstance(languages, str):
        languages = [languages]
    languages.append('en_us')
    def _parse_lang(langs: list[str]) -> list[str]:
        for x in langs:
            if ',' in x:
                yield from _parse_lang(x.split(','))
            else:
                yield x.strip().lower()
    languages = list(sorted(set(_parse_lang(languages))))
    
    if len(languages) <= 1:
        return
    
    languages_name: dict[str, str] = {}
    languages_data = defaultdict(dict[str, str])
    
    for x in languages:
        languages_name[x] = x
    
    def lang_name(key, data):
        return f"{data[key]['name']} ({data[key]['region']}) [{key}]"
    
    if os.path.exists(os.path.join(work_dir, 'assets.json')):
        assets = read_json(os.path.join(work_dir, 'assets.json'))
        assets = assets.get('objects', assets)
        def load_asset(name):
            import json
            import urllib.request
            try:
                hash = assets[name.replace('\\', '/')]['hash']
            except KeyError:
                return None
            with urllib.request.urlopen(f'https://resources.download.minecraft.net/{hash[:2]}/{hash}') as f:
                return json.loads(f.read())
        mcmeta = load_asset('pack.mcmeta')['language']
        for x in languages:
            languages_name[x] = lang_name(x, mcmeta)
            languages_data[x] = load_asset(f'minecraft/lang/{x}.json')
    
    if os.path.exists(os.path.join(work_dir, 'pack.mcmeta')):
        mcmeta = read_json(os.path.join(work_dir, 'pack.mcmeta'))['language']
        for x in languages:
            languages_name[x] = lang_name(x, mcmeta)
    
    if os.path.exists(os.path.join(work_dir, 'lists/languages')):
        data = read_json(os.path.join(work_dir, 'lists/languages'))
        for x in languages:
            languages_name[x] = lang_name(x, data)
    
    for x in glob.iglob('*.json', root_dir=lang_dir):
        name = os.path.splitext(x)[0].lower()
        if name in languages:
            languages_data[name] = read_json(os.path.join(lang_dir, x))
    
    
    rslt = defaultdict(lambda: defaultdict(set[str]))
    rslt.update(COMMENT_INFO)
    rslt['__comment_data'] = 'Testing Translation and English Redirection.'
    if version_target:
        rslt['__comment_version'] = version_target
    
    def analyze_data(lang):
        data = defaultdict(lambda: defaultdict(dict[str, tuple[str, str]]))
        
        for k,v in languages_data[lang].items():
            kk = k.split('.')
            vv = languages_data['en_us'][k], v
            
            if len(kk) == 3 and kk[1] == 'minecraft':
                data[kk[0]][kk[2]] = vv
            
            if kk[0] == 'advancements' and kk[-1] == 'title':
                data['advancement'][kk[-2]] = vv
            
            if kk[0] == 'attribute' and kk[1] == 'name':
                data['attribute'][kk[-1]] = vv
            
            if kk[0] == 'gamerule' and len(kk) == 2:
                data['gamerule'][kk[1]] = []
        
        data.pop('jukebox_song', None)
        data.pop('stat', None)
        data.pop('stat_type', None)
        data.pop('instrument', None)
        data['_name'] = languages_name[lang]
        rslt[lang] = data
    
    languages.remove('en_us')
    for lang in languages:
        analyze_data(lang)
    
    write_json(os.path.join(output_dir, 'Translation_Test.json'), rslt, sort_keys=True)
    
    #######
    # build wiki page sample
    with open(os.path.join(output_dir, 'Translation_Test.wiki'), 'wt', encoding='utf-8', newline='\n') as f:
        def write(args):
            if isinstance(args, str):
                args = [args]
            print(*args, file=f)
        
        # build lead
        write('{{TOC|right}}')
        write('')
        for k,v in rslt.items():
            if not k.startswith('__'):
                continue
            if k not in ('__comment_data', '__comment_version'):
                write(v)
        write('')
        write(';'+rslt['__comment_data'])
        if '__comment_version' in rslt:
            write('')
            write('version:'+rslt['__comment_version'])
        
        # build content
        def make_link(name):
            return '[['+name+']] ([{{canonicalurl:'+name+'|redirect=no}} direct])'
        for lang,content in rslt.items():
            if lang.startswith('_'):
                continue
            
            write('')
            name = content['_name'] or lang
            write(f'== {name} ==')
            for type,data in content.items():
                if type.startswith('_'):
                    continue
                write('')
                write(f'=== {make_link(type)} ===')
                write('{| class="mw-collapsible mw-collapsed wikitable sortable"')
                write('! key')
                write('! english')
                write('! name')
                write('! ')
                for k,v in data.items():
                    write('|-')
                    write(f'! {make_link(k)}')
                    write(f'| {make_link(v[0])}')
                    write(f'| {make_link(v[1])}')
                write('|}')


def main(
    path: str,
    output: str=None,
    *,
    silent=False,
    version_target: str=None,
    languages: list[str]=None,
    ):
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
    del path
    
    if not work_dir:
        args_error('The target path was not recognized.')
    
    os.makedirs(output, exist_ok=True)
    
    prints('Module:Tag_list_generator...')
    tag_list_generator(work_dir, output, version_target=version_target)
    
    prints('Translation Test...')
    translation_test(work_dir, output, languages, version_target=version_target)
    
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
        languages=args.langs,
    )