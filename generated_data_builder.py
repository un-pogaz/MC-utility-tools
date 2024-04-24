VERSION = (0, 19, 0)

import argparse
import glob
import os.path
import pathlib
from collections import OrderedDict, defaultdict
from typing import Callable

from common import (
    find_output, get_latest, hash_test, make_dirname, read_json, read_lines,
    read_manifest_json, run_animation, safe_del, urlretrieve, version_path,
    write_json, write_lines,
)

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
    from common import GITHUB_BUILDER, valide_output, valide_version, work_done
    
    print(f'--==| Minecraft: Generated data builder {VERSION} |==--')
    print()
    
    last, _, _ = GITHUB_BUILDER.check_releases()
    if last > VERSION:
        print('A new version is available!')
        print()
    
    args.version = valide_version(args.version, args.quiet, args.manifest_json)
    
    valide_output(args)
    
    if args.zip == None:
        if args.quiet:
            args.zip = False
        else:
            print('Do you want to empack the Generated data folder in a ZIP file?')
            args.zip = input()[:1] == 'y'
    
    print()
    
    error = build_generated_data(args)
    work_done(error, args.quiet)
    return error


def build_generated_data(args):
    import shutil
    import subprocess
    import zipfile
    from datetime import datetime
    from tempfile import gettempdir
    
    version = get_latest(args.version, args.manifest_json)
    
    temp_root = os.path.join(gettempdir(), 'MC Generated data', version)
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
    asset_sha1 = None
    if 'assetIndex' in manifest_json:
        #minecraft/original manifest
        version_json['asset_index'] = manifest_json['assetIndex']['url']
        asset_sha1                  = manifest_json['assetIndex']['sha1']
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
    
    global assets, assets_json
    assets = assets_json = {}
    
    def write_asset(file):
        if file in assets:
            asset = assets[file]
            file = os.path.join(temp,'assets',file)
            if not hash_test(asset['hash'], file):
                safe_del(file)
                make_dirname(file)
                urlretrieve(asset['url'], file)
    
    async def assets_dl():
        global assets, assets_json
        assets_json['assets'] = version_json['assets']
        assets_json['asset_index'] = version_json['asset_index']
        
        assets_file = os.path.join(temp_root, 'assets.json')
        if not hash_test(asset_sha1, assets_file):
            safe_del(assets_file)
            urlretrieve(version_json['asset_index'], assets_file)
        
        for k,v in read_json(assets_file).items():
            if k == 'objects':
                assets = v
            else:
                assets_json[k] = v
        
        assets = {k:assets[k] for k in sorted(assets.keys())}
        for a in assets:
            hash = assets[a]['hash']
            assets[a]['url'] = 'https://resources.download.minecraft.net/'+hash[0:2]+'/'+hash
        
        assets_json['objects'] = assets
        
    run_animation(assets_dl, 'Downloading assets.json')
    
    
    if dt.year >= 2018:
        server = os.path.join(temp_root, 'server.jar')
        async def server_dl():
            if version_json['server'] and not hash_test(server_sha1, server):
                safe_del(server)
                urlretrieve(version_json['server'], server)
        run_animation(server_dl, 'Downloading server.jar')
        
        async def data_server():
            for cmd in ['-DbundlerMainClass=net.minecraft.data.Main -jar server.jar --all', '-cp server.jar net.minecraft.data.Main --all']:
                subprocess.run('java ' + cmd, cwd=temp_root, shell=False, capture_output=False, stdout=subprocess.DEVNULL)
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
                pass
            
            for a in ['minecraft/sounds.json', 'sounds.json', 'pack.mcmeta']:
                write_asset(a)
            
            for a in assets:
                if a.startswith('minecraft/textures'):
                    write_asset(a)
            
    run_animation(data_client, 'Extracting data client')
    
    
    write_json(os.path.join(temp, version+'.json') , version_json)
    write_json(os.path.join(temp, 'assets.json'), assets_json)
    
    async def listing_various():
        for f in ['libraries', 'logs', 'tmp', 'versions', 'generated/.cache', 'generated/tmp', 'generated/assets/.mcassetsroot', 'generated/data/.mcassetsroot']:
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


class TBLpool():
    def __init__(self):
        self.rolls = ''
        self.comment = ''
        self.entries :list[TBLentrie] = []
    
    def __iter__(self):
        return iter(self.entries)
    
    def append(self, item):
        self.entries.append(item)
    
    def all_weight_levels(self):
        rslt = set()
        for e in self:
            rslt.add(e.weight_level)
        return rslt

class TBLentrie():
    def __init__(self, pool: TBLpool, weight_level: int = 0):
        self.pool = pool
        self.name = ''
        self.count = '1'
        self.weight = 1
        self.weight_level = weight_level
        self.comment = ''
    
    def total_weight_entries(self):
        rslt = 0
        for e in self.pool:
            if e.weight_level == self.weight_level:
                rslt += e.weight
        return rslt
    
    @property
    def chance(self) -> float:
        return (self.weight/self.total_weight_entries())*100
    
    @property
    def propabilty(self) -> str:
        tw = self.total_weight_entries()
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
                if d: rslt[i][y] = '"'+d+'"'
            rslt[i] = ','.join(rslt[i])
        elif rslt[i] is None:
            rslt[i] = ','.join('——' for _ in head_tbl)
        else:
            rslt[i] = ','*(len(head_tbl)-1)
    
    write_lines(path, rslt)

def write_tbl_md(path, head_tbl, lines_tbl):
    from copy import deepcopy
    
    col_len = [len(i) for i in head_tbl]
    for i in range(len(lines_tbl)):
        if lines_tbl[i]:
            for y in range(len(lines_tbl[i])):
                l = len(lines_tbl[i][y])
                if l > col_len[y]:
                    col_len[y] = l
    
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


def get_datapack_paths(temp) -> list[tuple[str,str]]:
    sub_datapacks = 'data/minecraft/datapacks'
    rslt = ['']
    for dp in glob.glob('*/', root_dir=os.path.join(temp, sub_datapacks), recursive=False):
        rslt.append(os.path.join(sub_datapacks, dp))
    return rslt

def get_structures_dir(temp) -> str:
    dir = 'data/minecraft/structures'
    if not os.path.exists(os.path.join(temp, dir)):
        dir = 'assets/minecraft/structures' # old
    return dir

def write_serialize_nbt(temp):
    from common import serialize_nbt
    
    # structures.snbt
    dir = get_structures_dir(temp)
    for dp in get_datapack_paths(temp):
        for f in glob.iglob('**/*.nbt', root_dir=os.path.join(temp, dir, dp), recursive=True):
            serialize_nbt(os.path.join(temp, dir, dp, f))


def flatering(name) -> str:
    return name.split(':', maxsplit=2)[-1].replace('\\', '/')
def filename(name) -> str:
    return flatering(os.path.splitext(name)[0])
def namespace(name, ns=None) -> str:
    ns = (ns or 'minecraft').lower()
    if ':' in name:
        ns = name.split(':', maxsplit=2)[0]
    return ns+':'+flatering(name)

def test_n(entry, n, target_type) -> bool:
    return namespace(entry[n]) == namespace(target_type)
def test_type(entry, target_type) -> bool:
    return test_n(entry,'type', namespace(target_type))

def unquoted_json(obj) -> str:
    import json
    import re
    # remove the quote around the name of the propety {name: "Value"}
    return re.sub(r'"([^":\\/]+)":', r'\1:', json.dumps(obj, indent=None))

def enum_json(dir, is_tag=False, ns=None) -> list[str]:
    return [('#' if is_tag else '')+ namespace(filename(j), ns=ns) for j in glob.iglob('**/*.json', root_dir=dir, recursive=True)]

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
    for l in read_lines(path):
        if '=' not in l:
            continue
        split = l.split('=',1)
        rslt[split[0]] = split[1]
    return rslt

def parse_json_text(json_text, languages_json=None) -> str:
    if isinstance(json_text, str):
        return json_text
    
    if isinstance(json_text, dict):
        if 'translate' in json_text:
            translate = json_text['translate']
            return (languages_json or {}).get(translate, translate)
        
        if 'text' in json_text:
            return json_text['text']
    
    if isinstance(json_text, list):
        return ''.join([parse_json_text(e) for e in json_text])
    
    raise ValueError('Unknow json_text format')

def strip_list(lst: list):
    while lst and not lst[-1]:
        lst.pop(-1)

def _get_sub_folder(temp, subdir, exlude=[]) -> tuple[list[str], list[str]]:
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

def get_sub_folder_assets(temp) -> tuple[list[str], list[str]]:
    lst_exlude = [
        'advancements',
        'lang',
        'shaders',
    ]
    return _get_sub_folder(temp, 'assets', lst_exlude)

def get_sub_folder_data(temp) -> tuple[list[str], list[str]]:
    lst_exlude = [
        'advancements',
        'datapacks',
        'loot_tables',
        'tags',
        'worldgen',
    ]
    return _get_sub_folder(temp, 'data', lst_exlude)

def uniform_reports(temp):
    items_json = os.path.join(temp, 'reports/items.json')
    j = read_json(items_json)
    for k in j.keys():
        if 'components' in j[k]:
            j[k]['components'] = list(sorted(j[k]['components'], key=lambda x: x['type']))
    if j:
        write_json(items_json, j)
    
    for j in glob.iglob('reports/*.json', root_dir=temp, recursive=False):
        j = os.path.join(temp, j)
        write_lines(j, read_lines(j))


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
        write_lines(os.path.join(temp, 'lists', 'structures.nbt.txt'), sorted(lines))

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
                if k == 'experience':
                    if v:
                        lst.append(str(v)+' xp')
                    continue
                if k == 'recipes':
                    lst.extend('recipe()'+namespace(l) for l in v)
                    continue
                if k == 'loot':
                    lst.extend('loot_table[]'+namespace(l) for l in v)
                    continue
                raise ValueError(f'Unknow rewards keys "{k}"')
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
    dir = 'data/minecraft/advancements'
    if not os.path.exists(os.path.join(temp, dir)):
        dir = 'assets/minecraft/advancements' # old
    entries: dict[str, Advancement] = {}
    tree_child = defaultdict(list)
    recipes = set()
    tags = set()
    for dp in get_datapack_paths(temp):
        root_dir = os.path.join(temp, dp, dir)
        for j in glob.iglob('**/*.json', root_dir=root_dir, recursive=True):
            advc = Advancement(j, read_json(os.path.join(root_dir, j)))
            if advc.path.startswith('recipes/'):
                recipes.add(advc.full_name)
                continue
            
            entries[advc.full_name] = advc
            tree_child[advc.parent].append(advc.full_name)
        
        tags.update(enum_json(os.path.join(temp, dp, 'data/minecraft/tags/advancements'), is_tag=True))
    
    lines = sorted(entries.keys()) + sorted(tags)
    if lines:
        write_lines(os.path.join(temp, 'lists', 'advancements.txt'), sorted(lines))
    if recipes:
        write_lines(os.path.join(temp, 'lists', 'advancements.recipes.txt'), sorted(recipes))
    
    # advancement.tree
    lines = []
    tree = {}
    
    indent_line  = '│ '
    indent_child = '└>'
    indent_space = '  '
    
    languages_json = get_languages_json(temp)
    
    for k in tree_child.keys():
        tree_child[k].sort()
    
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
        write_lines(os.path.join(temp, 'lists', 'advancements.tree.txt'), lines)
    if tree:
        write_json(os.path.join(temp, 'lists', 'advancements.tree.json'), tree)

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
        dir = 'reports/'+ subdir +'/minecraft' # root
        if not os.path.exists(os.path.join(temp, dir)):
            dir = 'reports/'+ subdir # alt root
            if not os.path.exists(os.path.join(temp, dir)):
                dir = 'reports/minecraft/'+ subdir # old
                if not os.path.exists(os.path.join(temp, dir)):
                    dir = 'reports/worldgen/minecraft/'+ subdir # legacy
        
        lines.update(enum_json(os.path.join(temp, dir)))
        if lines:
            write_lines(os.path.join(temp, 'lists', subdir+'.txt'), sorted(lines))

def listing_special_subdir(temp):
    # special subdir (not in registries)
    lst_namespace, lst_subdir = get_sub_folder_data(temp)
    
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
    
    def test_function(entry, target_type):
        return test_n(entry,'function', namespace(target_type))
    def test_condition(entry, target_type):
        return test_n(entry,'condition', namespace(target_type))
    
    dir = 'data/minecraft/loot_tables'
    if not os.path.exists(os.path.join(temp, 'data/minecraft/loot_tables')):
        dir = 'assets/minecraft/loot_tables' # old
    
    def get_simple(name, entry):
        def convert(item):
            item = namespace(item)
            if item == 'minecraft:book':
                for f in entry.get('functions', []):
                    for ef in ['enchant_randomly', 'enchant_with_levels', 'set_enchantments']:
                        if test_function(f, ef):
                            return namespace('enchanted_book')
            
            if item == 'minecraft:golden_apple':
                for f in entry.get('functions', []):
                    if test_function(f, 'set_data') and f['data'] == 1:
                        return namespace('enchanted_golden_apple')
            
            if item == 'minecraft:map':
                for f in entry.get('functions', []):
                    if test_function(f, 'exploration_map'):
                        return namespace('explorer_map')
            
            return item
        
        if 'type' not in entry:
            if 'item' in entry:
                return convert(entry['item'])
            else:
                return 'empty'
        
        if test_type(entry, 'item'):
            return convert(entry['name'])
        if test_type(entry, 'empty'):
            return 'empty'
        if test_type(entry, 'tag'):
            return '#'+namespace(entry['name'])
        if test_type(entry, 'loot_table'):
            v = entry.get('value') or entry['name']
            if isinstance(v, str):
                return 'loot_table[]'+namespace(v)
            if isinstance(v, dict):
                return 'loot_table[]'
            raise TypeError("Unknow loot_table[] format in loot_tables '{}'".format(name))
        
        raise TypeError("Unknow type '{}' in loot_tables '{}'".format(entry['type'], name))
    
    def no_end_0(num):
        return str(num).removesuffix('.0')
    def mcrange(name, entry, limit=None):
        if isinstance(entry, dict):
            
            if 'type' not in entry and 'min' in entry and 'max' in entry:
                entry['type'] = 'uniform'
            
            if test_type(entry, 'uniform'):
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
                
                if min != max:
                    return no_end_0(min) +'..'+ no_end_0(max)
                else:
                    return no_end_0(min)
            
            if test_type(entry, 'constant') or ('value' in entry):
                return no_end_0(entry['value'])
            
            raise TypeError("Unknow range type '{}' in loot_tables '{}'".format(entry['type'], name))
        
        else:
            return no_end_0(entry)
    
    def lootcount(name, entry):
        count = 1
        limit = None
        for e in entry.get('functions', []):
            if test_function(e, 'set_count'):
                count = e.get('count', 1)
            if test_function(e, 'limit_count'):
                limit = e.get('limit', None)
        
        return mcrange(name, count, limit)
    
    def lootcomment(name, entry):
        comment = []
        for e in entry.get('functions', []):
            if test_function(e, 'furnace_smelt'):
                comment.append('furnace smelt')
            if test_function(e, 'explosion_decay'):
                comment.append('explosion decay')
            
            if test_function(e, 'enchant_randomly'):
                enchantments = e.get('enchantments', None)
                if enchantments is None:
                    enchantments = '*'
                elif len(enchantments) == 1:
                    enchantments = flatering(enchantments[0])
                else:
                    enchantments = '['+', '.join(flatering(echt) for echt in enchantments)+']'
                comment.append('enchantments: '+ enchantments)
            if test_function(e, 'enchant_with_levels'):
                levels = []
                range = mcrange(name, e['levels'])
                try:
                    levels.append('level: '+str(int(range)))
                except:
                    levels.append('levels: '+str(range))
                if e.get('treasure', False):
                    levels.append('treasure: true')
                comment.append('enchantments: '+ '{'+ ', '.join(levels) +'}')
            if test_function(e, 'set_enchantments'):
                enchantments = e.get('enchantments', None)
                if not enchantments:
                    pass
                else:
                    comment.append('enchantments: '+ ', '.join(flatering(k) for k,v in enchantments.items() if v))
            
            if test_function(e, 'exploration_map'):
                comment.append('destination: '+ '#'+namespace(e.get('destination', 'on_treasure_maps')))
            
            if test_function(e, 'set_potion'):
                if not test_n(e, 'id', 'empty'):
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
            
            if test_function(e, 'set_nbt'):
                from nbtlib import parse_nbt
                j = parse_nbt(e['tag']).unpack(json=True)
                if 'Potion' in j:
                    comment.append(flatering(j['Potion']))
        
        for e in entry.get('conditions', []):
            if test_condition(e, 'killed_by_player'):
                comment.append('killed by player')
            if test_condition(e, 'random_chance') or test_condition(e, 'random_chance_with_looting'):
                comment.append('random chance: '+no_end_0(e['chance'])+'%')
        
        
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
    
    def add_entrie(tbl_pool, weight_level, e):
        tbl_entrie = TBLentrie(tbl_pool, weight_level)
        tbl_entrie.name = get_simple(name, e)
        tbl_entrie.weight = e.get('weight', 1)
        tbl_pool.append(tbl_entrie)
        
        if tbl_entrie.name == 'loot_table[]':
            tbl_entrie.count = get_rolls(pool)
            tbl_entrie.comment = get_poolcomment(pool)
            weight_level = len(tbl_pool.all_weight_levels())
            sub_table = e.get('value') or e['name']
            for sub_pool in sub_table.get('pools', {}):
                iter_pool(sub_pool, weight_level, tbl_pool)
            return
        
        if tbl_entrie.name == 'empty':
            tbl_entrie.count = ''
        else:
            tbl_entrie.count = lootcount(name, e)
        tbl_entrie.comment = lootcomment(name, e)
    
    def iter_pool(pool, weight_level, tbl_pool):
        if 'items' in pool:
            for e in pool['items']:
                add_entrie(tbl_pool, weight_level, e)
        elif 'entries' in pool:
            for e in pool['entries']:
                add_entrie(tbl_pool, weight_level, e)
        else:
            raise TypeError("Invalid input pool")
    
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
                    
                    weight_level = len(tbl_pool.all_weight_levels())
                    iter_pool(pool, weight_level, tbl_pool)
            
            lines_txt = []
            lines_tbl = []
            
            head_tbl = ['Name', 'Count', 'Chance', 'Weight', 'Comment']
            for l in rslt_tbl:
                lines_tbl.append([l.rolls,'--','--','--',l.comment])
                
                use_weight_level = len(l.all_weight_levels()) > 1
                
                for e in l:
                    c = e.chance
                    if c < 1:
                        c = str(round(c, 2))
                    else:
                        c = no_end_0(round(c, 1))
                    if use_weight_level:
                        groupe = '['+str(e.weight_level+1)+']'
                        prefix, suffix = groupe+' ',' '+groupe
                    else:
                        prefix, suffix = '',''
                    lines_txt.append(prefix+e.name)
                    lines_tbl.append([prefix+e.name, e.count, c+'%' + suffix, e.propabilty + suffix, e.comment])
                
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
                        if d: lines_tbl[i][y] = no_end_0(d)
            
            write_tbl_csv(os.path.join(temp, 'lists/loot_tables', name+'.csv'), head_tbl, lines_tbl)
            write_tbl_md(os.path.join(temp, 'lists/loot_tables', name+'.md'), head_tbl, lines_tbl)

def listing_worldgen(temp):
    dir = 'data/minecraft/worldgen'
    if not os.path.exists(os.path.join(temp, dir)):
        dir = 'reports/minecraft/worldgen' # old
        if not os.path.exists(os.path.join(temp, dir)):
            dir = 'reports/worldgen/minecraft/worldgen' # legacy
    
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
    blockstates = defaultdict(dict)
    rj = read_json(os.path.join(temp, 'reports/blocks.json'))
    if rj:
        write_lines(os.path.join(temp, 'lists', 'block.txt'), sorted(rj.keys()))
    for k,v in rj.items():
        name = flatering(k)
        
        lines = []
        for bs in v.pop('states', {}):
            default = bs.get('default', False)
            properties = bs.get('properties', {})
            if properties:
                lines.append(','.join(['='.join(s) for s in properties.items()]) + ('  [default]' if default else ''))
        
        write_json(os.path.join(temp, 'lists/blocks', name+'.json'), v)
        
        if lines:
            write_lines(os.path.join(temp, 'lists/blocks/states', name+'.txt'), lines)
        
        for vk in v:
            if vk == 'properties':
                for vs in v[vk]:
                    for vv in v[vk][vs]:
                        if vs not in blockstates[vk]:
                            blockstates[vk][vs] = defaultdict(list)
                        
                        blockstates[vk][vs][vv].append(namespace(k))
            elif vk in ['definition']:
                blockstates[vk][name] = v[vk]
            else:
                raise NotImplementedError(f'BlockStates "{vk}" not implemented.')
    
    for k,v in blockstates.items():
        for kk,vv in v.items():
            if k == 'properties':
                lines = []
                for zk,zv in vv.items():
                    lines.extend(zv)
                    write_lines(os.path.join(temp, 'lists/blocks/properties', kk+'='+zk+'.txt'), sorted(set(zv)))
                write_lines(os.path.join(temp, 'lists/blocks/properties', kk+'.txt'), sorted(set(lines)))
            else:
                write_json(os.path.join(temp, 'lists/blocks', k, kk+'.json'), vv, sort_keys=True)

def listing_items(temp):
    itemstates = defaultdict(dict)
    rj = read_json(os.path.join(temp, 'reports/items.json'))
    if rj:
        write_lines(os.path.join(temp, 'lists', 'item.txt'), sorted(rj.keys()))
    for k,v in rj.items():
        name = flatering(k)
        
        v.pop('protocol_id', None)
        if v:
            vc = list(sorted(v.get('components', []), key=lambda x: x['type']))
            if vc:
                v['components'] = vc
            write_json(os.path.join(temp, 'lists/items', name+'.json'), v)
        
        for vk in v:
            if vk == 'components':
                for vs in v[vk]:
                    type = flatering(vs['type'])
                    if type not in itemstates[vk]:
                        itemstates[vk][type] = defaultdict(dict)
                    
                    itemstates[vk][type][namespace(k)] = vs['value']
            else:
                raise NotImplementedError(f'ItemStates "{vk}" not implemented.')
    
    def _one_key_dict(value):
        if len(value) == 1:
            return list(value.keys())[0]
        return None
    
    def _test_value(value):
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
                return bool(value)
        return False
    
    def _text_value(value):
        rslt = None
        if not isinstance(value, (dict, list)):
            if isinstance(value, bool) or value:
                rslt = str(value)
        if isinstance(value, dict):
            sub_key = _one_key_dict(value)
            if sub_key and not isinstance(value[sub_key], (dict, list)):
                rslt = unquoted_json(value)
        
        if rslt:
            return '  = ' + rslt
        return ''
    
    default_components = [
        'lore',
        'enchantments',
        'repair_cost',
        'attribute_modifiers',
    ]
    
    components_grouped_value = [
        'max_stack_size',
        'rarity',
    ]
    
    for k,v in itemstates.items():
        if k == 'components':
            for t,e in v.items():
                if t in default_components:
                    lines = [n + _text_value(v) for n,v in e.items() if _test_value(v)]
                else:
                    lines = [n + _text_value(v) for n,v in e.items()]
                if lines:
                    write_lines(os.path.join(temp, 'lists/items/components', t+'.txt'), sorted(lines))
                
                if t in components_grouped_value:
                    dic = defaultdict(list)
                    for n,v in e.items():
                        dic[v].append(n)
                    for v,n in dic.items():
                        write_lines(os.path.join(temp, 'lists/items/components', t, str(v)+'.txt'), sorted(set(n)))
                else:
                    for n,v in e.items():
                        if _test_value(v):
                            write_json(os.path.join(temp, 'lists/items/components', t, flatering(n)+'.json'), v)

def listing_commands(temp):
    lines = set()
    
    def get_argument(value, entry):
        if test_type(entry, 'literal'):
            return value
        elif test_type(entry, 'argument') or test_type(entry, 'unknown'):
            if test_type(entry, 'unknown') and value not in ['dimension', 'angle']:
                # raise error if unknown specific case
                raise TypeError("Unknow type '{}' in commands '{}'".format(entry['type'], name))
            
            type = entry.get('parser', '')
            if type:
                type = namespace(type)
                lines.add(type)
                type = ' '+type
            
            properties = []
            for k,v in entry.get('properties', {}).items():
                properties.append(k+'="'+str(v)+'"')
            
            if properties:
                properties = '['+', '.join(properties)+']'
            else:
                properties = ''
            
            return '<'+value+type+properties+'>'
        
        else:
            raise TypeError("Unknow type '{}' in commands '{}'".format(entry['type'], name))
    
    def get_syntaxes(base, entry):
        rslt = []
        
        if entry.get('executable', False):
            rslt.append(base)
        
        if 'redirect' in entry:
            rslt.append(base +' >>redirect{'+ ', '.join(entry['redirect']) +'}')
        
        elif entry.get('type') == 'literal' and len(entry) == 1:
            rslt.append(base +' >>redirect{*}')
        
        elif 'children' in entry:
            for k,v in entry['children'].items():
                build = base +' '+ get_argument(k, v)
                rslt.extend(get_syntaxes(build, v))
        
        for k in entry.keys():
            if k not in ['type', 'executable', 'children', 'parser', 'properties', 'redirect']:
                raise TypeError("Additional key '{}' in commands '{}'".format(k, name))
        
        return rslt
    
    for k,v in read_json(os.path.join(temp, 'reports/commands.json')).get('children', {}).items():
        name = flatering(k)
        write_json(os.path.join(temp, 'lists/commands', name+'.json'), v)
        write_lines(os.path.join(temp, 'lists/commands', name+'.txt'), get_syntaxes(name, v))
    
    if lines:
        write_lines(os.path.join(temp, 'lists', 'command_argument_type.txt'), sorted(lines))

def listing_registries(temp):
    lines = [namespace(k) for k in read_json(os.path.join(temp, 'reports/registries.json')).keys()]
    if lines:
        write_lines(os.path.join(temp, 'lists', 'registries.txt'), sorted(lines))
    
    lst_namespace, _ = get_sub_folder_data(temp)
    
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
        languages.update({l.lower():src_lang[l] for l in sorted(src_lang.keys())})
        write_json(os.path.join(temp, 'lists', 'languages.json'), languages)
    
    safe_del(pack_mcmeta)

def listing_assets_txt(temp):
    lst_assets = read_json(os.path.join(temp, 'assets.json')).get('objects', {})
    if lst_assets:
        write_lines(os.path.join(temp, 'assets.txt'), sorted(lst_assets.keys()))

def listing_assets(temp):
    lst_namespace, lst_subdir = get_sub_folder_assets(temp)
    
    lst_ext = ['json', 'txt', 'png']
    
    def get_lines_assets(dir, ext):
        rslt = []
        for ns in lst_namespace:
            root = os.path.join(temp, 'assets', ns, dir)
            for f in glob.iglob('**/*.'+ext, root_dir=root, recursive=True):
                l = namespace(filename(f), ns=ns)
                if ext == 'png':
                    if os.path.exists(os.path.join(root, f +'.mcmeta')):
                        l = l+ '  [mcmeta]'
                rslt.append(l)
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

listing_various_functions: list[Callable[[str], None]] = [
    listing_builtit_datapacks,
    listing_structures,
    listing_advancements,
    listing_subdir_reports,
    listing_special_subdir,
    listing_loot_tables,
    listing_worldgen,
    listing_blocks,
    listing_items,
    listing_commands,
    listing_registries,
    listing_tags,
    listing_sounds,
    listing_sounds,
    listing_languages,
    listing_languages,
    listing_assets_txt,
    listing_assets,
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
            write_lines(path, read_lines(path))
    
    for func in listing_various_functions:
        if func in exclude_funcs:
            continue
        func(temp)


if __name__ == "__main__":
    main()
