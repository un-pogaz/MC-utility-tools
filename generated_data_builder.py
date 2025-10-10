import argparse
import glob
import os.path
import pathlib
from contextlib import suppress
from collections import OrderedDict, defaultdict
from typing import Callable
from tempfile import gettempdir

from common import (
    find_output, get_latest, version_path, hash_test, make_dirname,
    read_manifest_json, run_animation, safe_del, urlretrieve, urlopen,
    read_json, read_lines, read_text, write_json, write_lines, write_text,
)

VERSION = (0, 42, 0)

parser = argparse.ArgumentParser()
parser.add_argument('-v', '--version', help='Target version ; the version must be installed.\nr or release for the last release\ns or snapshot for the last snapshot.')

parser.add_argument('-q', '--quiet', help='Execute without any user interaction. Require --version or --manifest-json.', action='store_true')
parser.add_argument('-f', '--overwrite', help='Overwrite on the existing output folder.', action='store_true')

parser.add_argument('-z', '--zip', help='Empack the folder in a zip after it\'s creation', action='store_true', default=None)
parser.add_argument('--no-zip', dest='zip', help='Don\'t ask for empack the folder in a zip', action='store_false')

parser.add_argument('-o', '--output', help='Output folder', type=pathlib.Path)
parser.add_argument('--manifest-json', help='Local JSON manifest file of the target version.', type=pathlib.Path)

def parse_args():
    return parser.parse_args()

def main(args):
    from common import GITHUB_BUILDER, update_version_manifest, valide_output, valide_version, work_done
    
    update_version_manifest()
    
    print(f'--==| Minecraft: Generated data builder {VERSION} |==--')
    print()
    
    last, _versions, _versions_info = GITHUB_BUILDER.check_releases()
    if last > VERSION:
        print('A new version is available!')
        print()
    
    args.version = valide_version(args.version, args.quiet, args.manifest_json)
    
    valide_output(args)
    
    if args.zip is None:
        if args.quiet:
            args.zip = False
        else:
            print('Do you want to empack the Generated data folder in a ZIP file?')
            args.zip = input()[:1] == 'y'
    
    print()
    
    error = build_generated_data(args)
    work_done(error, args.quiet)
    return error

TEMP_DIR = os.path.abspath(os.path.join(gettempdir(), 'MC_Generated_data'))

def build_generated_data(args):
    import shutil
    import subprocess
    import zipfile
    from datetime import datetime
    
    version = get_latest(args.version, args.manifest_json)
    
    temp_root = os.path.join(TEMP_DIR, version)
    temp = os.path.join(temp_root, 'generated')
    os.makedirs(temp_root, exist_ok=True)
    
    
    manifest_json, manifest_url = read_manifest_json(temp_root, version, args.manifest_json)
    
    
    version_json = OrderedDict()
    version_json['id'] = manifest_json['id']
    version_json['type'] = manifest_json['type']
    version_json['time'] = manifest_json['time']
    version_json['releaseTime'] = manifest_json['releaseTime']
    version_json['url'] = manifest_url
    version_json['assets'] = manifest_json['assets']
    
    client_sha1 = None
    server_sha1 = None
    if 'assetIndex' in manifest_json:
        #minecraft/original manifest
        version_json['asset_index'] = manifest_json['assetIndex']['url']
        version_json['client'] = manifest_json['downloads']['client']['url']
        client_sha1 =            manifest_json['downloads']['client']['sha1']
        version_json['client_mappings'] = manifest_json['downloads'].get('client_mappings', {}).get('url', None)
        
        version_json['server'] = manifest_json['downloads'].get('server', {}).get('url', None)
        server_sha1 =            manifest_json['downloads'].get('server', {}).get('sha1', None)
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
        print(f'Imposible to build Generated data for {version}. The output "{output}" already exit and the overwrite is not enabled.')
        return -1
    
    
    print(f'Build Generated data for {version}')
    
    dt = datetime.fromisoformat(version_json['releaseTime'])
    
    print()
    
    client = os.path.join(temp_root, 'client.jar')
    async def client_dl():
        if not hash_test(client_sha1, client):
            safe_del(client)
            urlretrieve(version_json['client'], client)
    run_animation(client_dl, 'Downloading client.jar')
    
    
    if dt.year >= 2018:
        server = os.path.join(temp_root, 'server.jar')
        async def server_dl():
            if version_json['server'] and not hash_test(server_sha1, server):
                safe_del(server)
                urlretrieve(version_json['server'], server)
        run_animation(server_dl, 'Downloading server.jar')
        
        async def data_server():
            lst_cmd = (
                ('java', '-DbundlerMainClass=net.minecraft.data.Main', '-jar', 'server.jar', '--all'),
                ('java', '-cp', 'server.jar', 'net.minecraft.data.Main', '--all'),
            )
            
            for cmd in lst_cmd:
                subprocess.run(cmd, cwd=temp_root, shell=False, capture_output=False, stdout=subprocess.DEVNULL)
        run_animation(data_server, 'Extracting data server')
    
    
    async def data_client():
        with zipfile.ZipFile(client, mode='r') as zip:
            for entry in zip.filelist:
                if entry.filename.startswith('assets/') or entry.filename.startswith('data/'):
                    safe_del(os.path.join(temp, entry.filename))
                    zip.extract(entry.filename, temp)
            
            if not os.path.exists(os.path.join(temp, 'assets')):
                for entry in zip.filelist:
                    if entry.filename.endswith('.png') or entry.filename.endswith('.txt') or entry.filename.endswith('.lang'):
                        safe_del(os.path.join(temp, 'assets', entry.filename))
                        zip.extract(entry.filename, os.path.join(temp, 'assets'))
            else:
                # additional files to extract
                for name in ('pack.png', 'version.json'):
                    with suppress(KeyError):
                        zip.extract(name, temp)
            
    run_animation(data_client, 'Extracting data client')
    
    async def assets_dl():
        assets_json = {}
        assets_json['assets'] = version_json['assets']
        assets_json['asset_index'] = version_json['asset_index']
        write_json(os.path.join(temp, 'assets.json'), assets_json)
        downloading_assets_json(temp)
    run_animation(assets_dl, 'Downloading assets.json')
    
    async def assets_files_dl():
        downloading_assets_files(temp)
    run_animation(assets_files_dl, 'Downloading assets files')
    
    write_json(os.path.join(temp, version+'.json') , version_json)
    
    async def listing_various():
        tbl = [
            'libraries',
            'logs',
            'tmp',
            'versions',
            'generated/.cache',
            'generated/tmp',
            'generated/assets/.mcassetsroot',
            'generated/data/.mcassetsroot',
        ]
        for f in tbl:
            safe_del(os.path.join(temp_root, f))
        
        uniform_reports(temp)
        listing_various_data(temp)
    run_animation(listing_various, 'Generating /list/ folder')
    
    async def write_serialize():
        write_serialize_nbt(temp)
    run_animation(write_serialize, 'Generating NBT serialized')
    
    
    if args.zip:
        async def make_zip():
            zip_path = os.path.join(temp_root, 'zip.zip')
            zip_version_path = os.path.join(temp, version+'.zip')
            safe_del(zip_path)
            safe_del(zip_version_path)
            shutil.make_archive(os.path.splitext(zip_path)[0], 'zip', root_dir=temp)
            os.rename(zip_path, zip_version_path)
        run_animation(make_zip, 'Empack into a ZIP')
    
    async def move_generated_data():
        if os.path.exists(output):
            if args.overwrite:
                safe_del(output)
            else:
                print(f'The output at "{output}" already exit and the overwrite is not enable')
                return -1
        
        os.makedirs(output, exist_ok=True)
        for dir in os.listdir(temp):
            shutil.move(os.path.join(temp, dir), os.path.join(output, dir))
        
    run_animation(move_generated_data, f'Move generated data to "{output}"')

def downloading_assets_json(temp):
    import json
    
    assets_json = read_json(os.path.join(temp, 'assets.json'))
    custom_data = [
        'assets',
        'asset_index',
    ]
    assets_json = {k:assets_json[k] for k in custom_data}
    with urlopen(assets_json['asset_index']) as f:
        assets_file = json.load(f)
    
    for k,v in assets_file.items():
        assets_json[k] = v
    
    assets_json['objects'] = {k:assets_json['objects'][k] for k in sorted(assets_json['objects'].keys())}
    for a in assets_json['objects']:
        hash = assets_json['objects'][a]['hash']
        assets_json['objects'][a]['url'] = 'https://resources.download.minecraft.net/'+hash[0:2]+'/'+hash
    
    write_json(os.path.join(temp, 'assets.json'), assets_json)
    write_lines(os.path.join(temp, 'assets.txt'), sorted(assets_json['objects'].keys()))

def downloading_assets_files(temp):
    assets = read_json(os.path.join(temp, 'assets.json'))['objects']
    
    def write_asset(file):
        if file in assets:
            asset = assets[file]
            file = os.path.join(temp, 'assets', file)
            if not hash_test(asset['hash'], file):
                safe_del(file)
                make_dirname(file)
                urlretrieve(asset['url'], file)
    
    assets_dl = [
        'minecraft/sounds.json',
        'sounds.json',
        'pack.mcmeta',
    ]
    for a in assets_dl:
        write_asset(a)
    
    prefix_dl = [
        'minecraft/textures',
    ]
    for p in prefix_dl:
        for a in assets:
            if a.startswith(p):
                write_asset(a)


class TBLpool():
    def __init__(self):
        self.rolls = ''
        self.comment = ''
        self.entries :list[TBLentrie] = []
    
    def append(self, item):
        self.entries.append(item)
    
    def all_weight_groupes(self) -> list[int]:
        rslt = set()
        for e in self.entries:
            rslt.add(e.weight_groupe)
        return rslt
    
    def all_alternatives_groupes(self) -> list[int]:
        rslt = set()
        for e in self.entries:
            if e.alternatives_groupe:
                rslt.add(e.alternatives_groupe)
        return rslt

class TBLentrie():
    def __init__(self, pool: TBLpool, weight_groupe: int = 0, alternatives_groupe: int = 0):
        self.pool = pool
        self.name = ''
        self.count = '1'
        self.weight = 1
        self.weight_groupe = weight_groupe
        self.alternatives_groupe = alternatives_groupe
        self.comment = ''
    
    @property
    def total_weight(self) -> int:
        rslt = 0
        for e in self.pool.entries:
            if not self.alternatives_groupe and e.weight_groupe == self.weight_groupe:
                rslt += e.weight
        return rslt
    
    @property
    def chance(self) -> float:
        if not self.weight:
            return None
        return (self.weight/self.total_weight)*100
    
    @property
    def propabilty(self) -> str:
        if not self.weight:
            return ''
        tw = self.total_weight
        if self.weight == 1 and tw == 1:
            return '1'
        return str(self.weight) +'/'+ str(tw)


def write_tbl_csv(path, head_tbl, lines_tbl):
    from copy import deepcopy
    
    rslt = deepcopy(lines_tbl)
    rslt.insert(0, head_tbl.copy())
    rslt.insert(1, '')
    
    for i in range(len(rslt)):
        if rslt[i]:
            for y in range(len(rslt[i])):
                d = str(rslt[i][y])
                if d:
                    rslt[i][y] = '"'+d+'"'
            rslt[i] = ','.join(rslt[i])
        elif rslt[i] is None:
            rslt[i] = ','.join('——' for _ in head_tbl)
        else:
            rslt[i] = ','*(len(head_tbl)-1)
    
    write_lines(path, rslt)

def write_tbl_md(path, head_tbl, lines_tbl):
    from copy import deepcopy
    
    col_len = [[len(h)] for h in head_tbl]
    for line in lines_tbl:
        for y,data in enumerate(line or []):
            col_len[y].append(len(data))
    col_len = [max(c) for c in col_len]
    
    def concatline(line):
        return '| '+ ' | '.join(line) +' |'
    def calcspace(line, col):
        return ' '*(col_len[col] - len(line[col]))
    rslt = []
    rslt.append(concatline([head_tbl[i]+calcspace(head_tbl, i) for i in range(len(head_tbl))]))
    rslt.append(concatline(['-'*i for i in col_len]))
    empty_line = concatline([' '*i for i in col_len])
    separator_line = concatline(['– '*(i//2) + ('–' if i % 2 != 0 else '') for i in col_len])
    for line in deepcopy(lines_tbl):
        if line:
            line[0] = line[0]+calcspace(line, 0)
            for idx in range(1, len(line)-1):
                line[idx] = calcspace(line, idx)+line[idx]
            idx = len(line)-1
            line[idx] = line[idx]+calcspace(line, idx)
            rslt.append(concatline(line))
        elif line is None:
            rslt.append(separator_line)
        else:
            rslt.append(empty_line)
    
    write_lines(path, rslt)


def match_dir(temp, dirs) -> str:
    rslt = None
    for rslt in dirs:
        if os.path.exists(os.path.join(temp, rslt)):
            break
    return rslt


def get_datapack_paths(temp) -> list[tuple[str,str]]:
    sub_datapacks = 'data/minecraft/datapacks'
    rslt = ['']
    for dp in glob.glob('*/', root_dir=os.path.join(temp, sub_datapacks), recursive=False):
        rslt.append(os.path.join(sub_datapacks, dp))
    return rslt

def get_structures_dir(temp) -> str:
    return match_dir(temp, [
        'data/minecraft/structure',
        'data/minecraft/structures', # old
        'assets/minecraft/structures', # legacy
    ])

def write_serialize_nbt(temp):
    from common import serialize_nbt
    
    # structures.snbt
    dir = get_structures_dir(temp)
    dir_snbt = dir+'.snbt'
    for dp in get_datapack_paths(temp):
        for f in glob.iglob('**/*.nbt', root_dir=os.path.join(temp, dp, dir), recursive=True):
            serialize_nbt(
                file=os.path.join(temp, dp, dir, f),
                output_file=os.path.join(temp, dp, dir_snbt, os.path.splitext(f)[0]+'.snbt')
            )
            write_text(
                os.path.join(temp, dp, dir_snbt, '!!readme.txt'),
                SERIALIZE_NBT_README.format(os.path.basename(dir_snbt))
            )

SERIALIZE_NBT_README = """\
Attention! The folder /{}/ is not present in the original data files of Minecraft.
This folder, and the files inside, have been created to facilitate comparison between different versions of the game.
"""


def flatering(name) -> str:
    return ('#' if name.startswith('#') else '')+name.split(':', maxsplit=1)[-1].replace('\\', '/')
def filename(name) -> str:
    return flatering(os.path.splitext(name)[0])
def namespace(name, ns=None) -> str:
    ns = (ns or 'minecraft').lower()
    if ':' in name:
        split = name.split(':', maxsplit=1)
        ns = split[0]
        name = split[1]
    return ns+':'+flatering(name)

def flat_n(entry, name) -> str:
    return flatering(entry[name])
def flat_type(entry) -> str:
    return flat_n(entry, 'type')
def flat_function(entry):
    return flat_n(entry, 'function')

def unquoted_json(obj) -> str:
    import json
    import re
    # remove the quote around the name of the propety {name: "Value"}
    return re.sub(r'"([^":\\/]+)":', r'\1:', json.dumps(obj, indent=None))

def str_to_json(text) -> dict|list:
    import json
    return json.loads(text)

def enum_json(dir, is_tag=False, ns=None) -> list[str]:
    lst = glob.iglob('**/*.json', root_dir=dir, recursive=True)
    return [('#' if is_tag else '')+namespace(filename(j), ns=ns) for j in lst]

def get_languages_json(temp) -> dict[str, str]:
    path = os.path.join(temp, 'assets/minecraft/lang/en_us.json')
    if os.path.exists(path):
        return read_json(path)
    
    path = os.path.join(temp, 'assets/minecraft/lang/en_us.lang')
    if os.path.exists(path):
        return parse_languages_lang(path)
    
    path = os.path.join(temp, 'assets/lang/en_us.lang')
    if os.path.exists(path):
        return parse_languages_lang(path)
    
    return None

def parse_languages_lang(path) -> dict[str, str]:
    rslt = {}
    for x in read_lines(path):
        if '=' not in x:
            continue
        split = x.split('=',1)
        rslt[split[0]] = split[1]
    return rslt

def parse_json_text(json_text, languages_json) -> str|None:
    if json_text is None or isinstance(json_text, str):
        return json_text
    
    if isinstance(json_text, dict):
        if 'translate' in json_text:
            translate = json_text['translate']
            return languages_json.get(translate) or json_text.get('fallback') or translate
        
        if 'text' in json_text:
            return json_text['text']
    
    if isinstance(json_text, list):
        return ''.join([parse_json_text(e, languages_json) for e in json_text])
    
    raise ValueError('parse_json_text(): Unknow json_text format.')

def no_end_0(num):
    return str(num).removesuffix('.0')

def seconds_to_human_duration(seconds):
    seconds = round(seconds)
    if seconds < 1:
        return '>1s'
    
    hour = int(seconds // 3600)
    if hour:
        seconds = seconds - (3600 * hour)
    minute = int(seconds // 60)
    if minute:
        seconds = seconds - (60 * minute)
    seconds = int(seconds)
    
    tbl = []
    if hour:
        tbl.append(f'{hour}h')
    if minute:
        tbl.append(f'{minute}m')
    if seconds:
        tbl.append(f'{seconds}s')
    return ' '.join(tbl)

def human_duration_from_assets(temp, file):
    from mutagen.oggvorbis import OggVorbis
    
    assets = read_json(os.path.join(temp, 'assets.json'))['objects']
    def cache_asset(file):
        if file in assets:
            asset = assets[file]
            file = os.path.join(TEMP_DIR, 'cache/assets', asset['hash'])
            if not hash_test(asset['hash'], file):
                safe_del(file)
                make_dirname(file)
                urlretrieve(asset['url'], file)
            return file
        return None
    
    with open(cache_asset(file), 'rb') as f:
        ogg = OggVorbis(f)
        return seconds_to_human_duration(ogg.info.length)

def strip_list(lst: list):
    while lst and not lst[-1]:
        lst.pop(-1)

def _get_sub_folders(temp, subdir, exlude=[]) -> tuple[list[str], list[str]]:
    if os.path.exists(os.path.join(temp, subdir, 'minecraft')):
        rslt_namespaces = [flatering(d).strip('/') for d in glob.iglob('*/', root_dir=os.path.join(temp, subdir), recursive=False)]
        rslt_dirs = set()
        for ns in rslt_namespaces:
            rslt_dirs.update([flatering(d).strip('/') for d in glob.iglob('*/', root_dir=os.path.join(temp, subdir, ns), recursive=False)])
        
        rslt_dirs = list(sorted(rslt_dirs.difference(exlude)))
    else:
        rslt_namespaces = []
        rslt_dirs = []
    
    return rslt_namespaces, rslt_dirs

def get_sub_folders_assets(temp) -> tuple[list[str], list[str]]:
    lst_exlude = [
        'structures.snbt',
        'advancements',
        'lang',
        'loot_tables',
        'shaders',
    ]
    return _get_sub_folders(temp, 'assets', lst_exlude)

def get_sub_folders_data(temp) -> tuple[list[str], list[str]]:
    lst_exlude = [
        'structures.snbt',
        'advancements',
        'advancement',
        'datapacks',
        'datapack',
        'loot_tables',
        'loot_table',
        'tags',
        'worldgen',
    ]
    return _get_sub_folders(temp, 'data', lst_exlude)

def uniform_reports(temp):
    do_uniform = False
    
    items_json = os.path.join(temp, 'reports/items.json')
    if os.path.exists(items_json) and '"components": [' in read_text(items_json):
        j = read_json(items_json)
        for k in j.keys():
            if 'components' in j[k] and isinstance(j[k]['components'], list):
                j[k]['components'] = list(sorted(j[k]['components'], key=lambda x: x['type']))
        write_json(items_json, j)
        do_uniform = True
    
    if do_uniform:
        for j in glob.iglob('reports/*.json', root_dir=temp, recursive=False):
            j = os.path.join(temp, j)
            write_text(j, read_text(j))


def listing_builtit_datapacks(temp):
    lines = [namespace(os.path.basename(dp.strip('\\/'))) for dp in get_datapack_paths(temp)[1:]]
    if lines:
        write_lines(os.path.join(temp, 'lists', 'datapacks.txt'), sorted(lines))

def listing_structures(temp):
    dir = get_structures_dir(temp)
    lines = set()
    for dp in get_datapack_paths(temp):
        lines.update([namespace(filename(j)) for j in glob.iglob('**/*.nbt', root_dir=os.path.join(temp, dir, dp), recursive=True)])
    if lines:
        write_lines(os.path.join(temp, 'lists', os.path.basename(dir)+'.nbt.txt'), sorted(lines))

class Advancement():
    def __init__(self, file: str, json: dict):
        self.full_name = namespace(filename(file))
        self.namespace = self.full_name.split(':')[0]
        self.path = self.full_name.split(':')[1]
        
        self.json = json
        
        self.parent = json.get('parent')
        if self.parent:
            self.parent = namespace(self.parent)
        else:
            self.parent = None
        
        self.rewards = json.get('rewards')
        if self.rewards:
            lst = []
            for k,v in self.rewards.items():
                match k:
                    case 'experience':
                        if v:
                            lst.append(str(v)+' xp')
                        continue
                    case 'recipes':
                        lst.extend('recipe()'+namespace(n) for n in v)
                        continue
                    case 'loot':
                        lst.extend('loot_table[]'+namespace(n) for n in v)
                        continue
                    case _:
                        raise ValueError(f'Unknow rewards keys {k!r} in the Advancement {self.full_name!r}.')
            self.rewards = ', '.join(sorted(lst))
        else:
            self.rewards = None
        
        display = json.get('display', {})
        icon = display.get('icon', {})
        if isinstance(icon, str):
            self.icon = icon
        else:
            self.icon = icon.get('id') or icon.get('item')
        if self.icon:
            self.icon = namespace(self.icon)
        self.title = display.get('title')
        self.frame = display.get('frame', 'task')
        
        self.description = display.get('description')
        self.background = display.get('background')
        if self.background:
            self.background = namespace(filename(self.background)).replace('minecraft:textures/', 'minecraft:')
        else:
            self.background = None
        
        self.show_toast = display.get('show_toast', True)
        self.announce_to_chat = display.get('announce_to_chat', True)
        self.hidden = display.get('hidden', False)

def listing_advancements(temp):
    dir = match_dir(temp, [
        'data/minecraft/advancement',
        'data/minecraft/advancements', # old
        'assets/minecraft/advancements', # legacy
    ])
    
    lst_namespace, _dirs = get_sub_folders_data(temp)
    entries = set()
    tags = set()
    entries.update(enum_json(os.path.join(temp, 'assets/minecraft/advancements')))
    for ns in lst_namespace:
        for dp in get_datapack_paths(temp):
            entries.update(enum_json(os.path.join(temp, dp, 'data', ns, 'advancement'), ns=ns))
            tags.update(enum_json(os.path.join(temp, dp, 'data', ns, 'tags/advancement'), ns=ns, is_tag=True))
            # legacy
            entries.update(enum_json(os.path.join(temp, dp, 'data', ns, 'advancements'), ns=ns))
            tags.update(enum_json(os.path.join(temp, dp, 'data', ns, 'tags/advancements'), ns=ns, is_tag=True))
    
    recipes = set(e for e in entries if ':recipes/' in e)
    entries.difference_update(recipes)
    tags_recipes = set(e for e in tags if ':recipes/' in e)
    tags.difference_update(tags_recipes)
    
    if entries:
        write_lines(os.path.join(temp, 'lists', os.path.basename(dir)+'.txt'), sorted(entries) + sorted(tags))
    if recipes:
        write_lines(os.path.join(temp, 'lists', os.path.basename(dir)+'.recipes.txt'), sorted(recipes) + sorted(tags_recipes))
    
    entries: dict[str, Advancement] = {}
    tree_child = defaultdict(set)
    for dp in get_datapack_paths(temp):
        root_dir = os.path.join(temp, dp, dir)
        for j in glob.iglob('**/*.json', root_dir=root_dir, recursive=True):
            advc = Advancement(j, read_json(os.path.join(root_dir, j)))
            if advc.path.startswith('recipes/'):
                continue
            entries[advc.full_name] = advc
            tree_child[advc.parent].add(advc.full_name)
    
    # advancement.tree
    lines = []
    tree = {}
    
    indent_line  = '│ '
    indent_child = '└>'
    indent_space = '  '
    
    languages_json = get_languages_json(temp)
    
    for k in tree_child.keys():
        tree_child[k] = list(sorted(tree_child[k]))
    
    def read_tree(full_name: str, parent_tree: dict):
        advc = entries[full_name]
        parent_tree[full_name] = entry = {}
        entry['icon'] = advc.icon
        entry['title'] = parse_json_text(advc.title, languages_json)
        if advc.description:
            entry['description'] = parse_json_text(advc.description, languages_json)
        if advc.background:
            entry['background'] = advc.background
        entry['frame'] = advc.frame
        if advc.rewards:
            entry['rewards'] = advc.rewards
        if advc.hidden:
            entry['hidden'] = advc.hidden
        
        child_count = len(tree_child[full_name])
        if child_count:
            entry['childs'] = child_tree = {}
        for child in tree_child[full_name]:
            read_tree(child, child_tree)
    
    def tree_text(pre: str, full_name: str, last_child: bool):
        lines.append(pre+(indent_child if last_child is not None else '')+filename(full_name))
        
        if last_child is None:
            pre = ''
        if last_child is True:
            pre += indent_line
        if last_child is False:
            pre += indent_space
        
        child_count = len(tree_child[full_name])
        for idx,child in enumerate(tree_child[full_name], 1):
            tree_text(pre, child, (idx != child_count))
    
    for r in tree_child[None]:
        read_tree(r, tree)
        tree_text('', r, None)
        lines.append('')
    
    strip_list(lines)
    
    if lines:
        write_lines(os.path.join(temp, 'lists', os.path.basename(dir)+'.tree.txt'), lines)
    if tree:
        write_json(os.path.join(temp, 'lists', os.path.basename(dir)+'.tree.json'), tree)

def listing_subdir_reports(temp):
    # subdir /reports/
    lst_subdir = [
        'dimension',
        'dimension_type',
        'biome_parameters',
        'chat_type',
    ]
    for subdir in lst_subdir:
        lines = set()
        dir = match_dir(temp, [
            'reports/'+ subdir +'/minecraft', # root
            'reports/'+ subdir, # alt root
            'reports/minecraft/'+ subdir, # old
            'reports/worldgen/minecraft/'+ subdir, # legacy
        ])
        
        lines.update(enum_json(os.path.join(temp, dir)))
        if lines:
            write_lines(os.path.join(temp, 'lists', subdir+'.txt'), sorted(lines))

def listing_special_subdirs(temp):
    # special subdir (not in registries)
    lst_namespace, lst_subdir = get_sub_folders_data(temp)
    
    for subdir in lst_subdir:
        entries = set()
        tags = set()
        for ns in lst_namespace:
            for dp in get_datapack_paths(temp):
                entries.update(enum_json(os.path.join(temp, dp, 'data', ns,         subdir), ns=ns))
                tags.update(   enum_json(os.path.join(temp, dp, 'data', ns, 'tags', subdir), ns=ns, is_tag=True))
        lines = sorted(entries) + sorted(tags)
        if lines:
            write_lines(os.path.join(temp, 'lists', subdir+'.txt'), lines)

def listing_loot_tables(temp):
    
    dir = match_dir(temp, [
        'data/minecraft/loot_table',
        'data/minecraft/loot_tables', # old
        'assets/minecraft/loot_tables', # legacy
    ])
    
    lst_namespace, _dirs = get_sub_folders_data(temp)
    entries = set()
    tags = set()
    entries.update(enum_json(os.path.join(temp, 'assets/minecraft/loot_tables')))
    for ns in lst_namespace:
        for dp in get_datapack_paths(temp):
            entries.update(enum_json(os.path.join(temp, dp, 'data', ns, 'loot_table'), ns=ns))
            tags.update(enum_json(os.path.join(temp, dp, 'data', ns, 'tags/loot_table'), ns=ns, is_tag=True))
            # legacy
            entries.update(enum_json(os.path.join(temp, dp, 'data', ns, 'loot_tables'), ns=ns))
            tags.update(enum_json(os.path.join(temp, dp, 'data', ns, 'tags/loot_tables'), ns=ns, is_tag=True))
    
    entries.discard('minecraft:empty')
    blocks = set(e for e in entries if ':blocks/' in e)
    entries.difference_update(blocks)
    tags_blocks = set(e for e in tags if ':blocks/' in e)
    tags.difference_update(tags_blocks)
    
    if entries:
        write_lines(os.path.join(temp, 'lists', os.path.basename(dir)+'.txt'), sorted(entries) + sorted(tags))
    if blocks:
        write_lines(os.path.join(temp, 'lists', os.path.basename(dir)+'.blocks.txt'), sorted(blocks) + sorted(tags_blocks))
    
    def get_simple(name, entry):
        def convert(item):
            item = namespace(item)
            functions = set(flat_function(f) for f in entry.get('functions', []))
            match flatering(item):
                case 'book':
                    if functions.intersection({'enchant_randomly', 'enchant_with_levels', 'set_enchantments'}):
                        return namespace('enchanted_book')
                
                case 'golden_apple':
                    for f in entry.get('functions', []):
                        if flat_function(f) == 'set_data' and f['data'] == 1:
                            return namespace('enchanted_golden_apple')
                
                case 'map':
                    if 'exploration_map' in functions:
                        return namespace('explorer_map')
            
            return item
        
        if 'type' not in entry:
            if 'item' in entry:
                return convert(entry['item'])
            else:
                return 'empty'
        
        type_name = flat_type(entry)
        match type_name:
            case 'item':
                return convert(entry['name'])
            case 'empty':
                return 'empty'
            case 'tag':
                return '#'+namespace(entry['name'])
            case 'loot_table':
                v = entry.get('value') or entry['name']
                if isinstance(v, str):
                    return 'loot_table[]'+namespace(v)
                if isinstance(v, dict):
                    return 'loot_table[]'
                raise ValueError(f'listing_loot_tables().get_simple(): Unknow loot_table[] format in loot_tables {name!r}.')
            case 'alternatives':
                return '{}alternatives'
            case _:
                raise ValueError(f'listing_loot_tables().get_simple(): Unknow type {type_name!r} in loot_tables {name!r}.')
    
    def mcrange(name, entry, limit=None):
        if isinstance(entry, dict):
            
            if 'type' not in entry:
                if 'min' in entry and 'max' in entry:
                    entry['type'] = 'uniform'
                else:
                    raise ValueError(f'listing_loot_tables().mcrange(): A range cannot be converted in loot_tables {name!r}.')
            
            type_name = flat_type(entry)
            match type_name:
                case 'uniform':
                    min = entry['min']
                    max = entry['max']
                    
                    if limit:
                        if isinstance(limit, dict):
                            if 'min' in limit:
                                min = limit['min']
                            if 'max' in limit:
                                max = limit['max']
                        else:
                            max = limit
                    
                    if min < 0:
                        min = 0
                    if min != max:
                        return no_end_0(min) +'..'+ no_end_0(max)
                    else:
                        return no_end_0(min)
                
                case 'constant':
                    return no_end_0(entry['value'])
                case _:
                    if 'value' in entry:
                        return no_end_0(entry['value'])
                    raise ValueError(f'listing_loot_tables().mcrange(): Unknow range type {type_name!r} in loot_tables {name!r}.')
        
        else:
            return no_end_0(entry)
    
    def lootcount(name, entry):
        count = 1
        limit = None
        for e in entry.get('functions', []):
            match flat_function(e):
                case 'set_count':
                    count = e.get('count', 1)
                case 'limit_count':
                    limit = e.get('limit', None)
        
        return mcrange(name, count, limit)
    
    def lootcomment(name, entry):
        comment = []
        for e in entry.get('functions', []):
            match flat_function(e):
                case 'furnace_smelt':
                    comment.append('furnace smelt')
                case 'explosion_decay':
                    comment.append('explosion decay')
                
                case 'enchant_randomly':
                    enchantments = e.get('options') or e.get('enchantments', '*')
                    if isinstance(enchantments, str):
                        enchantments = [enchantments]
                    enchantments = [flatering(x) for x in enchantments]
                    if len(enchantments) == 1:
                        enchantments = enchantments[0]
                    else:
                        enchantments = '['+', '.join(enchantments)+']'
                    comment.append('enchantments: '+ enchantments)
                case 'enchant_with_levels':
                    levels = []
                    range = mcrange(name, e['levels'])
                    try:
                        levels.append('level: '+str(int(range)))
                    except Exception:
                        levels.append('levels: '+str(range))
                    if e.get('treasure', False):
                        levels.append('treasure: true')
                    enchantments = e.get('options')
                    if enchantments is not None:
                        if isinstance(enchantments, str):
                            enchantments = [enchantments]
                        enchantments = [flatering(x) for x in enchantments]
                        if len(enchantments) == 1:
                            levels.append(enchantments[0])
                        else:
                            levels.append('['+', '.join(enchantments)+']')
                    comment.append('enchantments: '+ '{'+ ', '.join(levels) +'}')
                case 'set_enchantments':
                    enchantments = e.get('enchantments', None)
                    if not enchantments:
                        pass
                    else:
                        comment.append('enchantments: '+ ', '.join(flatering(k) for k,v in enchantments.items() if v))
                
                case 'looting_enchant' | 'enchanted_count_increase':
                    comment.append('add drop: '+ mcrange(name, e['count'])+' * level {enchantment: '+flatering(e.get('enchantment', 'looting'))+'}')
                
                case 'exploration_map':
                    comment.append('destination: '+ '#'+namespace(e.get('destination', 'on_treasure_maps')))
                
                case 'set_instrument':
                    comment.append('instrument: '+ e['options'])
                
                case 'set_potion':
                    if not flat_n(e, 'id') == 'empty':
                        id = flatering(e['id'])
                        m = []
                        modifer = [
                            'strong',
                            'long',
                        ]
                        for k in modifer:
                            p = k+'_'
                            if p in id:
                                id = id.replace(p,'')
                                m.append(k)
                        
                        if m:
                            id = id + ' ('+ ', '.join(m) +')'
                        comment.append(id)
                
                case 'set_nbt':
                    from nbtlib import parse_nbt
                    j = parse_nbt(e['tag']).unpack(json=True)
                    if 'Potion' in j:
                        comment.append(flatering(j['Potion']))
        
        for e in entry.get('conditions', []):
            condition_type = flatering(e['condition'])
            match condition_type:
                case 'killed_by_player':
                    comment.append('killed by player')
                case 'random_chance':
                    comment.append('random chance: '+mcrange(name, e['chance'])+'%')
                case 'random_chance_with_looting':
                    unenchanted_chance = no_end_0(e['chance'])+'%'
                    chance = no_end_0(e['chance']+e['looting_multiplier'])+'% + '+no_end_0(e['looting_multiplier'])+'%*(level-1)'
                    comment.append('random chance: '+unenchanted_chance+'|{enchantment: looting}: '+ chance)
                case 'random_chance_with_enchanted_bonus':
                    chance = e.get('enchanted_chance') or e['chance']
                    chance_type = flat_type(chance)
                    match chance_type:
                        case 'linear':
                            chance = no_end_0(chance['base'])+'% + '+no_end_0(chance['per_level_above_first'])+'%*(level-1)'
                        case _:
                            raise ValueError(f'listing_loot_tables().lootcomment(): Unknow level-based value type {chance_type!r} in loot_tables {name!r}.')
                    unenchanted_chance = no_end_0(e.get('unenchanted_chance') or e.get('chance', {}).get('base', 0))+'%'
                    comment.append('random chance: '+unenchanted_chance+'|{enchantment: '+flatering(e['enchantment'])+'}: '+ chance)
                case 'killer_main_hand_tool':
                    value = e['value'].get('items') or e['value']['id']
                    comment.append('killed with main_hand tool: '+ value)
                
                case 'entity_properties':
                    predicate = e['predicate']
                    entity_origin = e['entity']
                    match entity_origin:
                        case 'attacker' | 'killer':
                            if 'type' in predicate:
                                comment.append('killed by '+predicate['type'])
                            else:
                                raise ValueError(f'listing_loot_tables().lootcomment(): entity_properties contain unsuported data {name!r}.')
                        
                        case 'this':
                            components = predicate.pop('components', {})
                            tropical_fish = {}
                            for type_name,value in components.items():
                                type_name = flatering(type_name)
                                match type_name:
                                    case ('axolotl/variant' |
                                          'cat/variant' |
                                          'chicken/variant' |
                                          'fox/variant' |
                                          'frog/variant' |
                                          'horse/variant' |
                                          'llama/variant' |
                                          'painting/variant' |
                                          'parrot/variant' |
                                          'pig/variant' |
                                          'mooshroom/variant' |
                                          'rabbit/variant' |
                                          'villager/variant' |
                                          'wolf/variant' |
                                          'mooshroom/variant'):
                                        comment.append(f'is {value} variant')
                                    case 'cat/collar' | 'wolf/collar':
                                        comment.append(f'have {value} collar')
                                    case 'salmon/size':
                                        comment.append(f'is size {value}')
                                    case 'sheep/color' | 'shulker/color':
                                        comment.append(f'is {value}')
                                    case 'tropical_fish/base_color' | 'tropical_fish/pattern_color' | 'tropical_fish/pattern':
                                        tropical_fish[type_name.removeprefix('tropical_fish/')] = value
                                    case _:
                                        raise ValueError(f'listing_loot_tables().lootcomment(): Unknow entity component {type_name!r} in loot_tables {name!r}.')
                            
                            if tropical_fish:
                                color = ''
                                pattern = tropical_fish.get('pattern', '')
                                base_color = tropical_fish.get('base_color', '')
                                pattern_color = tropical_fish.get('pattern_color', '')
                                if base_color and pattern_color:
                                    color = f'{base_color}-{pattern_color}'
                                elif base_color:
                                    color = f'base {base_color}'
                                elif pattern_color:
                                    color = f'pattern {base_color}'
                                comment.append(' '.join([color, pattern]).strip())
                            
                            def type_specific(type_name, predicate):
                                match type_name:
                                    case 'raider':
                                        if predicate['is_captain'] is True:
                                            comment.append('is captain raider')
                                    case 'slime':
                                        v = predicate['size']
                                        if isinstance(v, int):
                                            comment.append(f'size is {v}')
                                        if isinstance(v, dict):
                                            min = v.get('min')
                                            max = v.get('max')
                                            if min == max:
                                                comment.append(f'size is {min}')
                                            else:
                                                if min is not None and max is not None:
                                                    msg = f'size is between {min} and {max}'
                                                if max is None:
                                                    msg = f'size is inferior {min}'
                                                if min is None:
                                                    msg = 'size is superior {max}'
                                            comment.append(f'{msg} (inclusive)')
                                    case 'fishing_hook':
                                        if predicate['in_open_water'] is True:
                                            comment.append('is on open water')
                                    case 'sheep':
                                        msg = []
                                        if 'color' in predicate:
                                            msg.append('is '+predicate['color'])
                                        if predicate.get('sheared') is True:
                                            msg.append('is sheared')
                                        if predicate.get('sheared') is False:
                                            msg.append('is not sheared')
                                        comment.append(' and '.join(msg))
                                    case 'mooshroom':
                                        comment.append('is '+predicate['variant']+' variant')
                                    case 'vehicle':
                                        comment.append('is riding a '+ flatering(predicate['type']))
                                    case 'flags':
                                        if predicate.pop('is_baby', None):
                                            comment.append('is a baby')
                                        if predicate:
                                            ValueError(f'listing_loot_tables().lootcomment(): Unknow flags predicate {list(predicate.keys())} in loot_tables {name!r}.')
                                    case 'type':
                                        comment.append('is a '+ flatering(predicate))
                                    case _:
                                        raise ValueError(f'listing_loot_tables().lootcomment(): Unknow type_specific {type_name!r} in loot_tables {name!r}.')
                            
                            if 'type_specific' in predicate:
                                value = predicate['type_specific']
                                type_specific(flat_type(value), value)
                            elif predicate:
                                for type_name,value in predicate.items():
                                    type_specific(type_name, value)
                        
                        case _:
                            raise ValueError(f'listing_loot_tables().lootcomment(): Unknow entity origin {entity_origin!r} in loot_tables {name!r}.')
                
                case 'damage_source_properties':
                    predicate = e['predicate']
                    if predicate.pop('is_direct', False):
                        comment.append('Is direct damage')
                    entitys = set()
                    for k in ['source_entity', 'direct_entity']:
                        type = predicate.pop(k, {}).pop('type', None)
                        if type:
                            entitys.add(flatering(type))
                    tags = set()
                    for v in predicate.pop('tags', []):
                        if isinstance(v, str):
                            tags.add('#'+flatering(v))
                        elif v.get('expected', True):
                            tags.add('#'+flatering(v['id']))
                    
                    for k in ['is_explosion',  'is_fire', 'is_magic', 'is_projectile', 'is_lightning',
                                'bypasses_armor', 'bypasses_invulnerability', 'bypasses_magic']:
                        if predicate.pop(k, False):
                            comment.append(f'Damaged by: {k!r}')
                    
                    if predicate:
                        raise ValueError(f'listing_loot_tables().lootcomment(): Unknow damage source {list(predicate.keys())} in loot_tables {name!r}.')
                    
                    rslt = sorted(entitys) + sorted(tags)
                    if rslt:
                        if len(rslt) == 1:
                            comment.append(f'Damaged by: {rslt[0]}')
                        else:
                            comment.append('Damaged by: ['+ ', '.join(rslt) +']')
        
        return ', '.join(comment)
    
    
    def get_rolls(pool):
        value = mcrange(name, pool.get('rolls', 1))
        if '..' in value:
            return ' to '.join(value.split('..', 1))+' time'
        else:
            return value+' time'
    
    def get_poolcomment(pool):
        bonus = pool.get('bonus_rolls', 0)
        if bonus:
            bonus = 'bonus rolls: '+ no_end_0(bonus)
        comment = lootcomment(name, pool)
        return ', '.join([e for e in [bonus, comment] if e])
    
    def add_entrie(tbl_pool, e, weight_groupe, alternatives_groupe = 0):
        tbl_entrie = TBLentrie(tbl_pool, weight_groupe, alternatives_groupe)
        tbl_entrie.name = get_simple(name, e)
        tbl_entrie.comment = lootcomment(name, e)
        if alternatives_groupe > 0:
            tbl_entrie.weight = 0
        else:
            tbl_entrie.weight = e.get('weight', 1)
        tbl_pool.append(tbl_entrie)
        
        if tbl_entrie.name == '{}alternatives':
            alternatives_groupe = len(tbl_pool.all_alternatives_groupes())+1
            tbl_entrie.name = '{'+str(alternatives_groupe)+'}alternatives'
            tbl_entrie.count = ''
            for c in e['children']:
                add_entrie(tbl_pool, c, weight_groupe, alternatives_groupe)
            return
        
        if tbl_entrie.name == 'loot_table[]':
            tbl_entrie.count = get_rolls(pool)
            tbl_entrie.comment = get_poolcomment(pool)
            weight_groupe = len(tbl_pool.all_weight_groupes())
            sub_table = e.get('value') or e['name']
            for sub_pool in sub_table.get('pools', {}):
                iter_pool(tbl_pool, sub_pool, weight_groupe)
            return
        
        if tbl_entrie.name == 'empty':
            tbl_entrie.count = ''
        else:
            tbl_entrie.count = lootcount(name, e)
    
    def iter_pool(tbl_pool, pool, weight_groupe):
        if 'items' in pool:
            for e in pool['items']:
                add_entrie(tbl_pool, e, weight_groupe)
        elif 'entries' in pool:
            for e in pool['entries']:
                add_entrie(tbl_pool, e, weight_groupe)
        else:
            raise ValueError('listing_loot_tables(): Invalid input pool.')
    
    for dp in get_datapack_paths(temp):
        for loot in glob.iglob('**/*.json', root_dir=os.path.join(temp, dp, dir), recursive=True):
            if loot == 'empty.json':
                continue
            table = read_json(os.path.join(temp, dp, dir, loot))
            name = filename(loot)
            
            rslt_tbl :list[TBLpool] = []
            
            if name.startswith('blocks'):
                continue
            else:
                for pool in table.get('pools', {}):
                    tbl_pool = TBLpool()
                    tbl_pool.rolls = get_rolls(pool)
                    tbl_pool.comment = get_poolcomment(pool)
                    
                    rslt_tbl.append(tbl_pool)
                    
                    weight_groupe = len(tbl_pool.all_weight_groupes())
                    iter_pool(tbl_pool, pool, weight_groupe)
            
            lines_txt = []
            lines_tbl = []
            
            head_tbl = ['Name', 'Count', 'Chance', 'Weight', 'Comment']
            for r in rslt_tbl:
                lines_tbl.append([r.rolls,'--','--','--',r.comment])
                
                use_weight_groupe = len(r.all_weight_groupes()) > 1
                
                for e in r.entries:
                    c = e.chance
                    
                    if c is None:
                        c = ''
                    elif c < 1:
                        c = str(round(c, 2))+'%'
                    else:
                        c = no_end_0(round(c, 1))+'%'
                    
                    if use_weight_groupe or e.alternatives_groupe:
                        groupe = ' '.join([
                            ('{'+str(e.alternatives_groupe)+'}') if e.alternatives_groupe else '',
                            ('['+str(e.weight_groupe+1)+']') if use_weight_groupe else '',
                        ]).strip()
                        prefix, suffix = groupe+' ',' '+groupe
                    else:
                        prefix, suffix = '',''
                    lines_txt.append(prefix+e.name)
                    lines_tbl.append([
                        prefix+e.name,
                        e.count + (suffix if e.count else ''),
                        c + (suffix if c else ''),
                        e.propabilty + (suffix if e.propabilty else ''),
                        e.comment,
                    ])
                
                lines_txt.append('')
                lines_tbl.append(None)
            
            strip_list(lines_txt)
            if not lines_txt:
                lines_txt.append('empty')
            write_lines(os.path.join(temp, 'lists/loot_tables', name+'.txt'), lines_txt)
            
            
            strip_list(lines_tbl)
            if not lines_tbl:
                lines_tbl.append(['empty','','100%','1',''])
            
            for i in range(len(lines_tbl)):
                if lines_tbl[i]:
                    for y in range(len(lines_tbl[i])):
                        d = str(lines_tbl[i][y])
                        if d:
                            lines_tbl[i][y] = no_end_0(d)
            
            write_tbl_csv(os.path.join(temp, 'lists/loot_tables', name+'.csv'), head_tbl, lines_tbl)
            write_tbl_md(os.path.join(temp, 'lists/loot_tables', name+'.md'), head_tbl, lines_tbl)

def listing_worldgens(temp):
    dir = match_dir(temp, [
        'data/minecraft/worldgen',
        'reports/minecraft/worldgen', # old
        'reports/worldgen/minecraft/worldgen', # legacy
    ])
    
    lines = set()
    for dp in get_datapack_paths(temp):
        world_preset_dir = os.path.join(temp, dir, dp, 'world_preset')
        for j in glob.iglob('**/*.json', root_dir=world_preset_dir, recursive=True):
            lines.update([namespace(e) for e in read_json(os.path.join(world_preset_dir, j)).get('dimensions', {}).keys()])
    
    if lines:
        write_lines(os.path.join(temp, 'lists', 'dimension.txt'), sorted(lines))
    
    def biomes_list(dir):
        no_features = False
        for path in glob.iglob('**/*.json', root_dir=dir, recursive=True):
            j = read_json(os.path.join(dir, path))
            path = filename(path)
            
            lines = []
            dic = defaultdict(list)
            for k,v in j.get('spawners', {}).items():
                for e in v:
                    lines.append(e['type'])
                    dic[k].append(e)
            
            if not lines:
                lines.append('[]')
            
            dic = {k:sorted(dic[k], key=lambda x: x['type']) for k in dic.keys()}
            lines = sorted(set(lines))
            write_json(os.path.join(temp, 'lists/worldgen/biome/mobs', path+'.json'), dic, sort_keys=True)
            write_lines(os.path.join(temp, 'lists/worldgen/biome/mobs', path+'.txt'), lines)
            
            lines = []
            for v in j.get('features', []):
                if lines is None or no_features:
                    break
                if isinstance(v, str):
                    lines.append(v)
                elif isinstance(v, list):
                    if not v:
                        lines.append('[]')
                    for e in v:
                        if isinstance(e, dict):
                            lines = None
                            break
                        lines.append(e)
                
                if lines is None:
                    break
                lines.append('')
            
            if lines is None or no_features:
                no_features = True
                path = os.path.join(temp, 'lists/worldgen/biome/features')
                if os.path.exists(path):
                    import shutil
                    shutil.rmtree(path)
            else:
                strip_list(lines)
                if not lines:
                    lines.append('[]')
                
                write_lines(os.path.join(temp, 'lists/worldgen/biome/features', path+'.txt'), lines)
    
    for subdir in glob.iglob('*/', root_dir=os.path.join(temp, dir), recursive=False):
        subdir = subdir.strip('/\\')
        entries = set()
        tags = set()
        for dp in get_datapack_paths(temp):
            entries.update(enum_json(os.path.join(temp, dp, dir,                            subdir)))
            tags.update(   enum_json(os.path.join(temp, dp, 'data/minecraft/tags/worldgen', subdir), is_tag=True))
            biomes_list(os.path.join(temp, dp, dir, 'biome'))
        write_lines(os.path.join(temp, 'lists/worldgen', subdir +'.txt'), sorted(entries) + sorted(tags))
    
    dir = os.path.join(temp, 'reports/biomes') #legacy
    if os.path.exists(dir):
        write_lines(os.path.join(temp, 'lists/worldgen', 'biome.txt'), sorted(enum_json(dir)))
        biomes_list(dir)

def listing_blocks(temp):
    def mcrange(name, entry):
        type_name = flat_type(entry)
        match type_name:
            case 'constant':
                return no_end_0(entry['value'])
            case 'uniform':
                min = entry.get('min_inclusive')
                if min is None:
                    min = entry['value']['min_inclusive']
                max = entry.get('max_inclusive')
                if max is None:
                    max = entry['value']['max_inclusive']
                return no_end_0(min)+'..'+no_end_0(max)
            case _:
                raise ValueError(f'listing_blocks(): Block definition of {name!r} has not implemented {type_name!r} type value.')
    def parse_value(block_name, name, value):
        value_error = ValueError(f'Block definition of {block_name!r} has not implemented {name!r} properties.')
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, (str, int, float)):
            return no_end_0(value)
        
        match name:
            case 'experience':
                return mcrange(name, value)
            case 'base_state':
                if len(value) != 1:
                    raise value_error
                return value['Name']
            case 'suspicious_stew_effects':
                return ', '.join('{} ({} ticks)'.format(e['id'], e.get('duration', 160)) for e in value)
            case 'properties':
                if value:
                    raise value_error
                else:
                    return
            case 'particle' | 'leaf_particle':
                return unquoted_json(value)
            case _:
                raise value_error
    
    blockstates = defaultdict(lambda:defaultdict(set))
    definitions = defaultdict(dict)
    
    rj = read_json(os.path.join(temp, 'reports/blocks.json'))
    if rj:
        write_lines(os.path.join(temp, 'lists', 'block.txt'), sorted(rj.keys()))
    for name,content in rj.items():
        name = flatering(name)
        lines = []
        for bs in content.pop('states', []):
            properties = bs.get('properties', {})
            if properties:
                lines.append(','.join(['='.join(s) for s in properties.items()]) + ('  [default]' if bs.get('default', False) else ''))
        if lines:
            write_lines(os.path.join(temp, 'lists/blocks/states', name+'.txt'), lines)
        
        write_json(os.path.join(temp, 'lists/blocks', name+'.json'), content)
        
        for content_type,content_value in content.items():
            match content_type:
                case 'properties':
                    for k,v in content_value.items():
                        for vv in v:
                            blockstates[k][vv].add(namespace(name))
                case 'definition':
                    write_json(os.path.join(temp, 'lists/blocks/definition', name+'.json'), content_value, sort_keys=True)
                    for k,v in content_value.items():
                        value = parse_value(name, k, v)
                        if value is not None:
                            definitions[k][namespace(name)] = value
                case _:
                    raise ValueError(f'listing_blocks(): Block element {content_type!r} not implemented.')
    
    for k,v in blockstates.items():
        lines = set()
        for kk,vv in v.items():
            lines.update(vv)
            write_lines(os.path.join(temp, 'lists/blocks/properties', k+'='+kk+'.txt'), sorted(vv))
        write_lines(os.path.join(temp, 'lists/blocks/properties', k+'.txt'), sorted(lines))
    
    grouped = [
        'aabb_offset',
        'block_set_type',
        'color',
        'fire_damage',
        'height',
        'interactions',
        'kind',
        'max_weight',
        'precipitation',
        'ticks_to_stay_pressed',
        'weathering_state',
        'wood_type',
        'spawn_particles',
    ]
    all_blocks = [
        'type',
    ]
    for k,v in definitions.items():
        if k in grouped or k in all_blocks:
            if k in grouped:
                write_lines(os.path.join(temp, 'lists/blocks/definition/groups', k+'.txt'), sorted(v.keys()))
            dic = defaultdict(set)
            for kk,vv in v.items():
                dic[vv].add(kk)
            for kk,vv in dic.items():
                if k in all_blocks:
                    write_lines(os.path.join(temp, 'lists/blocks/definition', k, flatering(kk)+'.txt'), sorted(vv))
                else:
                    write_lines(os.path.join(temp, 'lists/blocks/definition/groups', k+'='+kk+'.txt'), sorted(vv))
        else:
            lines = [f'{kk}  = {vv}' for kk,vv in v.items()]
            write_lines(os.path.join(temp, 'lists/blocks/definition/values', k+'.txt'), sorted(lines))

def listing_items(temp):
    languages_json = get_languages_json(temp)
    itemstates = defaultdict(lambda:defaultdict(dict))
    rj = read_json(os.path.join(temp, 'reports/items.json'))
    if rj:
        write_lines(os.path.join(temp, 'lists', 'item.txt'), sorted(rj.keys()))
    for k,v in rj.items():
        name = flatering(k)
        
        v.pop('protocol_id', None)
        if v:
            vc = v.get('components', None)
            if isinstance(vc, list):
                v['components'] = list(sorted(vc, key=lambda x: x['type']))
            write_json(os.path.join(temp, 'lists/items', name+'.json'), v)
        
        for vk in v:
            if vk == 'components':
                if isinstance(v[vk], list):
                    for vs in v[vk]:
                        type = flatering(vs['type'])
                        itemstates[vk][type][namespace(k)] = vs['value']
                else:
                    for type,value in v[vk].items():
                        type = flatering(type)
                        itemstates[vk][type][namespace(k)] = value
            else:
                raise ValueError(f'listing_items(): ItemStates {vk!r} not implemented.')
    
    def _one_key_dict(value):
        if len(value) == 1:
            return list(value.keys())[0]
        return None
    
    def component_test_value(value, is_file: bool):
        if value:
            if isinstance(value, dict):
                sub_key = _one_key_dict(value)
                if sub_key:
                    if isinstance(value[sub_key], (dict, list)):
                        return bool(value[sub_key])
                    else:
                        return False
                
                return bool(value)
            
            if isinstance(value, list):
                if is_file and len(value) == 1 and isinstance(value[0], (int, float, bool, str)):
                    return False
                return bool(value)
            if isinstance(value, str):
                return bool(value)
        return False
    
    def component_text_value(value, allow_inline: bool):
        rslt = None
        if isinstance(value, (int, float, bool)):
            rslt = str(value)
        if isinstance(value, str):
            if value:
                rslt = value
            else:
                rslt = '""'
        if isinstance(value, list):
            if value:
                rslt = '[[value]]'
            else:
                rslt = '[]'
            if allow_inline and len(value) == 1 and isinstance(value[0], (int, float, bool, str)):
                rslt = unquoted_json(value)
        if isinstance(value, dict):
            if value:
                rslt = '{{value}}'
            else:
                rslt = '{}'
            sub_key = _one_key_dict(value)
            if allow_inline and sub_key:
                if isinstance(value[sub_key], (dict, list)):
                    if not value[sub_key]:
                        rslt = unquoted_json(value)
                else:
                    rslt = unquoted_json(value)
        
        if not rslt:
            raise ValueError(f'listing_items(): component with a unknow type to retrive value {type(value)!r}.')
        return '  = ' + rslt
    
    def _quote_str(value):
        return '"'+value.replace('"', '\\"')+'"'
    
    default_components = [
        'lore',
        'enchantments',
        'repair_cost',
        'attribute_modifiers',
        'tooltip_display',
        'swing_animation',
        'use_effects',
    ]
    components_grouped_value = [
        'max_stack_size',
        'rarity',
        'break_sound',
    ]
    components_always_json_value = [
        'tool',
        'food',
        'consumable',
        'equippable',
        'death_protection',
        'weapon',
    ]
    json_text_components = [
        'item_name',
    ]
    
    for k,kv in itemstates.items():
        match k:
            case 'components':
                for c,e in kv.items():
                    if c in json_text_components:
                        for n,v in e.items():
                            if isinstance(v, str):
                                v = str_to_json(v)
                            e[n] = _quote_str(parse_json_text(v, languages_json))
                    
                    if c in default_components:
                        lines = [n + component_text_value(v, allow_inline=True) for n,v in e.items() if component_test_value(v, is_file=False)]
                    elif c in components_always_json_value:
                        lines = [n + component_text_value(v, allow_inline=False) for n,v in e.items()]
                    else:
                        lines = [n + component_text_value(v, allow_inline=True) for n,v in e.items()]
                    if lines:
                        write_lines(os.path.join(temp, 'lists/items/components', c+'.txt'), sorted(lines))
                    
                    if c in components_grouped_value:
                        dic = defaultdict(list)
                        for n,v in e.items():
                            if isinstance(v, str) and ':' in v:
                                v = flatering(v)
                            dic[v].append(n)
                        for v,n in dic.items():
                            write_lines(os.path.join(temp, 'lists/items/components', c, str(v)+'.txt'), sorted(set(n)))
                    else:
                        for n,v in e.items():
                            if not isinstance(v, (dict, list)):
                                continue
                            if component_test_value(v, is_file=True) or (c in components_always_json_value and v):
                                write_json(os.path.join(temp, 'lists/items/components', c, flatering(n)+'.json'), v)
            case _:
                raise ValueError(f'listing_items(): Unknow item states {k!r}.')

def listing_packets(temp):
    for k,tv in read_json(os.path.join(temp, 'reports/packets.json')).items():
        for t,v in tv.items():
            write_lines(os.path.join(temp, 'lists/packets', k, t+'.txt'), sorted([namespace(e) for e in v.keys()]))

def listing_datapacks(temp):
    values = defaultdict(set)
    
    for k,tv in read_json(os.path.join(temp, 'reports/datapack.json')).items():
        for t,v in tv.items():
            t = namespace(t)
            values['all'].add(t)
            values[k].add(t)
            name = filename(t)
            for kk,vv in v.items():
                if isinstance(vv, bool):
                    values['value/'+kk+'='+str(vv).lower()].add(t)
                elif isinstance(vv, str):
                    values['value/'+kk].add(f'{t}  = {vv}')
                else:
                    raise ValueError('listing_datapacks(): The value {kk!r} of {name!r} is a unknow type.')
            write_json(os.path.join(temp, 'lists/datapacks', k, name)+'.json', v)
    
    for k,v in values.items():
        write_lines(os.path.join(temp, 'lists/datapacks', k)+'.txt', sorted(v))

def listing_commands(temp):
    argument_type = set()
    
    def get_argument(value, entry):
        type_name = flat_type(entry)
        match type_name:
            case 'literal':
                return value
            case 'argument' | 'unknown':
                if type_name == 'unknown' and value not in ['dimension', 'angle']:
                    # raise error if unknown specific case
                    raise ValueError(f'listing_commands(): Type {type_name!r} with invalide value in commands {name!r}.')
                
                type = entry.get('parser', '')
                if type:
                    type = namespace(type)
                    argument_type.add(type)
                    type = ' '+type
                
                properties = []
                for k,v in entry.get('properties', {}).items():
                    properties.append(k+'="'+str(v)+'"')
                
                if properties:
                    properties = '['+', '.join(properties)+']'
                else:
                    properties = ''
                
                return '<'+value+type+properties+'>'
            
            case _:
                raise ValueError(f'listing_commands(): Unknow type {type_name!r} in commands {name!r}.')
    
    def parse_permissions(entry, parent_level):
        rslt = parent_level
        if 'required_level' in entry:
            rslt = entry['required_level']
        if 'permissions' in entry:
            p = entry['permissions']
            error = ValueError(f'Invalid permissions entry: {p}')
            if len(p) != 2 or 'permission' not in p or flat_type(p) != 'require':
                raise error
            p = p['permission']
            if len(p) != 2 or 'level' not in p or flat_type(p) != 'command_level':
                raise error
            rslt = p['level']
        return rslt
    
    def get_syntaxes(base, entry, parent_level):
        rslt = []
        
        level = parse_permissions(entry, parent_level)
        
        if entry.get('executable', False):
            rslt.append((level, base))
        
        if 'redirect' in entry:
            rslt.append((level, base +' >>redirect{'+ '|'.join(entry['redirect']) +'}'))
        
        elif entry.get('type') == 'literal' and len(entry) == 1:
            rslt.append((level, base +' >>redirect{*}'))
        elif entry.get('type') == 'literal' and len(entry) == 2 and 'required_level' in entry:
            rslt.append((level, base +' >>redirect{*}'))
        elif entry.get('type') == 'literal' and len(entry) == 2 and 'permissions' in entry:
            rslt.append((level, base +' >>redirect{*}'))
        
        elif 'children' in entry:
            for k,v in entry['children'].items():
                build = base +' '+ get_argument(k, v)
                rslt.extend(get_syntaxes(build, v, level))
        
        for k in entry.keys():
            if k not in ['type', 'executable', 'children', 'parser', 'properties', 'redirect', 'required_level', 'permissions']:
                raise ValueError(f'listing_commands(): Additional key {k!r} in commands {name!r}.')
        
        return rslt
    
    src_json = read_json(os.path.join(temp, 'reports/commands.json'))
    base_level = None
    prefix_level = None
    for v in src_json.get('children', {}).values():
        if 'required_level' in v:
            prefix_level = 'required_level'
            base_level = 0
            break
        if 'permissions' in v:
            prefix_level = 'permissions'
            base_level = 'players'
            break
    
    for k,v in src_json.get('children', {}).items():
        name = flatering(k)
        write_json(os.path.join(temp, 'lists/commands', name+'.json'), v)
        lines = []
        level_prev = None
        for level, line in get_syntaxes(name, v, base_level):
            if level_prev != level:
                lines.append(f'(({prefix_level}: {level}))')
                level_prev = level
            lines.append(line)
        write_lines(os.path.join(temp, 'lists/commands', name+'.txt'), lines)
    
    if argument_type:
        write_lines(os.path.join(temp, 'lists', 'command_argument_type.txt'), sorted(argument_type))

def listing_registries(temp):
    lines = [namespace(k) for k in read_json(os.path.join(temp, 'reports/registries.json')).keys()]
    if lines:
        write_lines(os.path.join(temp, 'lists', 'registries.txt'), sorted(lines))
    
    lst_namespace, _dirs = get_sub_folders_data(temp)
    
    for k,v in read_json(os.path.join(temp, 'reports/registries.json')).items():
        name = flatering(k)
        
        entries = set()
        tags = set()
        entries.update([namespace(k) for k in v['entries'].keys()])
        
        for ns in lst_namespace:
            for dp in get_datapack_paths(temp):
                entries.update(enum_json(os.path.join(temp, dp, 'data', ns,         name), ns=ns))
                tags.update(   enum_json(os.path.join(temp, dp, 'data', ns, 'tags', name), ns=ns, is_tag=True))
                # legacy
                entries.update(enum_json(os.path.join(temp, dp, 'data', ns,         name+'s'), ns=ns))
                tags.update(   enum_json(os.path.join(temp, dp, 'data', ns, 'tags', name+'s'), ns=ns, is_tag=True))
        
        write_lines(os.path.join(temp, 'lists', name +'.txt'), sorted(entries) + sorted(tags))

def listing_paintings(temp):
    languages_json = get_languages_json(temp)
    lst_namespace, _dirs = get_sub_folders_data(temp)
    paintings = defaultdict(lambda:defaultdict(set))
    for ns in lst_namespace:
        for dp in get_datapack_paths(temp):
            dir = os.path.join(temp, dp, 'data', ns, 'painting_variant')
            for file in glob.iglob('**/*.json', root_dir=dir, recursive=True):
                name = filename(file)
                ns_name = namespace(name, ns=ns)
                lng_id = '.'.join(['painting', ns, name])
                j = read_json(os.path.join(dir, file))
                title = parse_json_text(j.get('title'), languages_json) or languages_json.get(lng_id+'.title') or lng_id+'.title'
                author = parse_json_text(j.get('author'), languages_json) or languages_json.get(lng_id+'.author') or lng_id+'.author'
                size = '{}x{}'.format(j['width'], j['height'])
                paintings['authors'][author].add(ns_name)
                paintings['sizes'][size].add(ns_name)
                lines = []
                lines.append('texture: '+ namespace(j['asset_id']))
                lines.append('name: '+ title)
                lines.append('author: '+ author)
                lines.append('size: '+ size)
                write_lines(os.path.join(temp, 'lists/paintings', name)+'.txt', lines)
    
    for k,v in paintings.items():
        for kk,vv in v.items():
            write_lines(os.path.join(temp, 'lists/paintings', k, kk)+'.txt', sorted(vv))

def listing_jukebox_songs(temp):
    languages_json = get_languages_json(temp)
    lst_namespace, _dirs = get_sub_folders_data(temp)
    jukebox_songs = defaultdict(lambda:defaultdict(set))
    all_names = set()
    
    for ns in lst_namespace:
        for dp in get_datapack_paths(temp):
            dir = os.path.join(temp, dp, 'data', ns, 'jukebox_song')
            for file in glob.iglob('**/*.json', root_dir=dir, recursive=True):
                name = filename(file)
                ns_name = namespace(name, ns=ns)
                lng_id = '.'.join(['jukebox_song', ns, name])
                j = read_json(os.path.join(dir, file))
                desc = parse_json_text(j.get('description'), languages_json) or languages_json.get(lng_id) or lng_id
                all_names.add(desc)
                author, _, title = desc.partition(' - ')
                if not title:
                    raise ValueError(f"listing_jukebox_songs(): The jukebox_song {name!r} don't use 'author - title' pairs.")
                jukebox_songs['authors'][author].add(ns_name)
                jukebox_songs['comparator_output'][str(j['comparator_output'])].add(ns_name)
                lines = []
                lines.append('sound_event: '+ namespace(j['sound_event']))
                lines.append('title: '+ title)
                lines.append('author: '+ author)
                lines.append('length: '+ seconds_to_human_duration(j['length_in_seconds']))
                write_lines(os.path.join(temp, 'lists/jukebox_songs', name)+'.txt', lines)
    
    for k,v in jukebox_songs.items():
        for kk,vv in v.items():
            write_lines(os.path.join(temp, 'lists/jukebox_songs', k, kk)+'.txt', sorted(vv))
    if all_names:
        write_lines(os.path.join(temp, 'lists/jukebox_songs.names.txt'), sorted(all_names))

def listing_instruments(temp):
    languages_json = get_languages_json(temp)
    lst_namespace, _dirs = get_sub_folders_data(temp)
    all_names = set()
    
    for ns in lst_namespace:
        for dp in get_datapack_paths(temp):
            dir = os.path.join(temp, dp, 'data', ns, 'instrument')
            for file in glob.iglob('**/*.json', root_dir=dir, recursive=True):
                name = filename(file)
                lng_id = '.'.join(['instrument', ns, name])
                j = read_json(os.path.join(dir, file))
                desc = parse_json_text(j.get('description'), languages_json) or languages_json.get(lng_id) or lng_id
                all_names.add(desc)
                lines = []
                lines.append('sound_event: '+ namespace(j['sound_event']))
                lines.append('description: '+ desc)
                lines.append('range: '+ no_end_0(j['range'])+ ' block')
                lines.append('length: '+ seconds_to_human_duration(j['use_duration']))
                write_lines(os.path.join(temp, 'lists/instruments', name)+'.txt', lines)
    
    if all_names:
        write_lines(os.path.join(temp, 'lists/instruments.names.txt'), sorted(all_names))

def listing_tags(temp):
    entries = set()
    for dp in get_datapack_paths(temp):
        dir = os.path.join(temp, dp, 'data/minecraft/tags')
        entries.update(flatering(j) for j in glob.iglob('**/*.json', root_dir=dir, recursive=True))
    
    for name in entries:
        lines = []
        for dp in get_datapack_paths(temp):
            j = os.path.join(temp, dp, 'data/minecraft/tags', name)
            for v in read_json(j).get('values', []):
                if v not in lines:
                    lines.append(v)
        
        write_lines(os.path.join(temp, 'lists/tags', filename(name)+'.txt'), lines)

def listing_sounds(temp):
    full_lines = set()
    for sounds in ['sounds.json'] + glob.glob('*/sounds.json', root_dir=os.path.join(temp, 'assets'), recursive=False):
        sounds = os.path.join(temp, 'assets', sounds)
        if os.path.exists(sounds):
            for k,v in read_json(sounds).items():
                name = flatering(k)
                write_json(os.path.join(temp, 'lists/sounds', name+'.json'), v)
                
                lines = v['sounds']
                for idx,v in enumerate(lines):
                    if isinstance(v, dict):
                        lines[idx] = v['name']
                    lines[idx] = namespace(lines[idx])
                full_lines.update(lines)
                write_lines(os.path.join(temp, 'lists/sounds', name+'.txt'), lines)
    
    if full_lines:
        write_lines(os.path.join(temp, 'lists', 'sounds.ogg.txt'), sorted(full_lines))

def listing_musics(temp):
    languages_json = get_languages_json(temp)
    musics = defaultdict(lambda:defaultdict(set))
    all_events = defaultdict(set)
    sound_events = defaultdict(list)
    musics['sound_events'] = defaultdict(list)
    all_names = set()
    
    for k,v in read_json(os.path.join(temp, 'assets/minecraft', 'sounds.json')).items():
        if k.startswith('music.'):
            for n in v.get('sounds', []):
                if isinstance(n, dict):
                    n = n['name']
                all_events[namespace(n)].add(namespace(k))
                sound_events[flatering(k)].append(namespace(n))
    
    for k,v in all_events.items():
        all_events[k] = sorted(v)
    
    for k,desc in languages_json.items():
        if k.startswith('music.'):
            musics['sound_events'] = sound_events
            name = k.removeprefix('music.')
            ns_name = namespace(k.replace('.', '/'))
            ogg_file = 'minecraft/sounds/' + k.replace('.', '/') + '.ogg'
            all_names.add(desc)
            author, _, title = desc.partition(' - ')
            if not title:
                raise ValueError(f"listing_musics(): The musics {k!r} don't use 'author - title' pairs.")
            musics['authors'][author].add(ns_name)
            events = all_events[ns_name]
            lines = []
            lines.append('assets: '+ ns_name)
            lines.append('title: '+ title)
            lines.append('author: '+ author)
            lines.append('length: '+ human_duration_from_assets(temp, ogg_file))
            if not events:
                lines.append('sound_event:')
            else:
                for e in events:
                    lines.append(f'sound_event: {e}')
            write_lines(os.path.join(temp, 'lists/musics', name)+'.txt', lines)
    
    for k,v in musics.items():
        for kk,vv in v.items():
            if isinstance(vv, set):
                musics[k][kk] = sorted(vv)
    
    for k,v in musics.items():
        for kk,vv in v.items():
            write_lines(os.path.join(temp, 'lists/musics', k, kk)+'.txt', vv)
    if all_names:
        write_lines(os.path.join(temp, 'lists/musics.names.txt'), sorted(all_names))

def listing_languages(temp):
    src_lang = {}
    search_term = ['language.code', 'language.name', 'language.region']
    for lang in glob.iglob('assets/lang/*.lang', root_dir=temp, recursive=False):
        # old format
        lang = parse_languages_lang(os.path.join(temp, lang))
        new_lang = {st:lang[st] for st in search_term if st in lang}
        if len(search_term) == len(new_lang):
            src_lang[new_lang['language.code']] = {'region':new_lang['language.region'],'name':new_lang['language.name']}
    
    pack_mcmeta = os.path.join(temp, 'assets', 'pack.mcmeta')
    if not src_lang:
        src_lang = read_json(pack_mcmeta).get('language', None)
    
    if src_lang:
        # actual format
        languages = {}
        for en in ['en_us', 'en_US']:
            if en in src_lang:
                languages['en_us'] = src_lang.pop(en)
        languages.update({x.lower():src_lang[x] for x in sorted(src_lang.keys())})
        write_json(os.path.join(temp, 'lists', 'languages.json'), languages)
    
    safe_del(pack_mcmeta)

def listing_assets(temp):
    lst_namespace, lst_subdir = get_sub_folders_assets(temp)
    
    lst_ext = ['json', 'txt', 'png']
    
    def get_lines_assets(dir, ext):
        rslt = []
        for ns in lst_namespace:
            root = os.path.join(temp, 'assets', ns, dir)
            for f in glob.iglob('**/*.'+ext, root_dir=root, recursive=True):
                n = namespace(filename(f), ns=ns)
                if ext == 'png':
                    if os.path.exists(os.path.join(root, f +'.mcmeta')):
                        n = n+ '  [mcmeta]'
                rslt.append(n)
        return rslt
    
    for dir in lst_subdir:
        for ext in lst_ext:
            lines = get_lines_assets(dir, ext)
            if lines:
                txt_path = dir + ('' if ext == 'json' else '.'+ext) +'.txt'
                write_lines(os.path.join(temp, 'lists', txt_path), sorted(lines))
    
    lines = {}
    shaders_dir = os.path.join(temp, 'assets', 'shaders')
    for f in glob.iglob('**/*', root_dir=shaders_dir, recursive=True):
        if os.path.isdir(os.path.join(shaders_dir, f)):
            continue
        name, ext = os.path.splitext(f)
        name = flatering(name)
        ext = ext.strip('.').lower()
        if name not in lines:
            lines[name] = set()
        lines[name].add(ext)
    
    if lines:
        lines = [k +'  ['+ ','.join(sorted(v))+']' for k,v in lines.items()]
        write_lines(os.path.join(temp, 'lists', 'shaders.txt'), sorted(lines))
    
    if not lst_subdir:
        # old /assets/
        for name, ext in [('textures','png'), ('texts','txt')]:
            lines = [namespace(filename(f)) for f in glob.iglob('**/*.'+ext, root_dir=os.path.join(temp, 'assets'), recursive=True)]
            if lines:
                txt_path = name + '.'+ext +'.txt'
                write_lines(os.path.join(temp, 'lists', txt_path), sorted(lines))


def listing_rpc_api_schema(temp):
    rj = read_json(os.path.join(temp, 'reports/json-rpc-api-schema.json'))
    if not rj:
        return
    lines = [
        'title: ' + rj['info']['title'],
        'version: ' + rj['info']['version'],
        'openrpc: ' + rj['openrpc'],
    ]
    write_lines(os.path.join(temp, 'lists/json-rpc-api-schema/info.txt'), lines)
    rj.pop('info')
    rj.pop('openrpc')
    
    lines = set()
    for method in rj.pop('methods'):
        name = method['name']
        lines.add(namespace(name))
        write_json(os.path.join(temp, 'lists/json-rpc-api-schema/methods', flatering(name)+'.json'), method)
    if lines:
        write_lines(os.path.join(temp, 'lists/json-rpc-api-schema/methods.txt'), sorted(lines))
    
    components = rj.pop('components')
    schemas = components.pop('schemas')
    if components:
        raise ValueError('rpc_api_schema(): unknow data inside the "components"', *(repr(k) for k in components.keys()))
    lines = set()
    for name, data in schemas.items():
        lines.add(name)
        write_json(os.path.join(temp, 'lists/json-rpc-api-schema/components', name+'.json'), data)
    if lines:
        write_lines(os.path.join(temp, 'lists/json-rpc-api-schema/components.txt'), sorted(lines))
    
    if rj:
        raise ValueError('rpc_api_schema(): unknow data inside the rpc-api-schema', *(repr(k) for k in rj.keys()))


listing_various_functions: list[Callable[[str], None]] = [
    listing_builtit_datapacks,
    listing_structures,
    listing_advancements,
    listing_subdir_reports,
    listing_special_subdirs,
    listing_loot_tables,
    listing_worldgens,
    listing_blocks,
    listing_items,
    listing_packets,
    listing_datapacks,
    listing_paintings,
    listing_jukebox_songs,
    listing_instruments,
    listing_commands,
    listing_registries,
    listing_tags,
    listing_sounds,
    listing_musics,
    listing_languages,
    listing_assets,
    listing_assets,
    listing_rpc_api_schema,
]
def listing_various_data(temp):
    for func in listing_various_functions:
        func(temp)

def listing_various_data_alt(version, temp):
    # internal function
    # private use for Github update script
    
    exclude_funcs = {
        '24w14potato': [listing_loot_tables],
    }
    exclude_funcs = exclude_funcs.get(version, [])
    
    ## update the 'last edit' attribut of the files to the last parsing
    rewrite_files = [
        os.path.join(temp, 'lists', 'languages.json')
    ]
    if exclude_funcs:
        for path in glob.iglob('lists/**/*.*', root_dir=temp, recursive=True):
            rewrite_files.append(os.path.join(temp, path))
    
    for path in rewrite_files:
        if os.path.exists(path) and os.path.isfile(path):
            write_text(path, read_text(path))
    
    for func in listing_various_functions:
        if func in exclude_funcs:
            continue
        func(temp)


if __name__ == "__main__":
    main(parse_args())
