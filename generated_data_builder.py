VERSION = (0, 13, 0)

import sys, argparse, os.path, glob, json, re
import pathlib
from collections import OrderedDict, defaultdict

from common import prints, urlretrieve


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
    import shutil
    from common import run_animation, read_json, write_json, write_lines, safe_del
    from common import find_output, get_latest, read_manifest_json, version_path, make_dirname, hash_test
    
    import subprocess, zipfile
    from tempfile import gettempdir
    from datetime import datetime
    
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
        prints(f'Imposible to build Generated data for {version}. The output "{output}" already exit and the overwrite is not enabled.')
        return -1
    
    
    prints(f'Build Generated data for {version}')
    
    dt = datetime.fromisoformat(version_json['releaseTime'])
    
    prints()
    
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
        
        listing_various_data(temp)
    run_animation(listing_various, 'Listing elements and various')
    
    
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
                prints(f'The output at "{output}" already exit and the overwrite is not enable')
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
    
    def total_weight_entries(self):
        rslt = 0
        for e in self:
            rslt += e.weight
        return rslt

class TBLentrie():
    def __init__(self, pool: TBLpool):
        self.pool = pool
        self.name = ''
        self.count = '1'
        self.weight = 1
        self.comment = ''
    
    @property
    def chance(self) -> float:
        return (self.weight/self.pool.total_weight_entries())*100
    
    @property
    def propabilty(self) -> str:
        tw = self.pool.total_weight_entries()
        if self.weight == 1 and tw == 1:
            return '1'
        return str(self.weight) +'/'+ str(tw)


def write_tbl_csv(path, head_tbl, lines_tbl):
    from copy import deepcopy
    from common import write_lines
    
    rslt = deepcopy(lines_tbl)
    rslt.insert(0, head_tbl.copy())
    rslt.insert(1, None)
    
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
    from common import write_lines
    
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


def listing_various_data(temp):
    from common import read_json, write_json, read_lines, write_lines, safe_del, serialize_nbt
    
    def flatering(name):
        return name.split(':', maxsplit=2)[-1].replace('\\', '/')
    def filename(name):
        return flatering(os.path.splitext(name)[0])
    def namespace(name, ns=None):
        ns = (ns or 'minecraft').lower()
        if ':' in name:
            ns = name.split(':', maxsplit=2)[0]
        return ns+':'+flatering(name)
    
    def test_n(entry, n, target_type):
        return namespace(entry[n]) == namespace(target_type)
    def test_type(entry, target_type):
        return test_n(entry,'type', namespace(target_type))
    def test_function(entry, target_type):
        return test_n(entry,'function', namespace(target_type))
    def test_condition(entry, target_type):
        return test_n(entry,'condition', namespace(target_type))
    
    def unquoted_json(obj):
        # remove the quote around the name of the propety {name: "Value"}
        return re.sub(r'"([^"]+)":', r'\1:', json.dumps(obj, indent=None))
    
    def enum_json(dir, is_tag=False):
        return [('#' if is_tag else '')+ namespace(filename(j)) for j in glob.iglob('**/*.json', root_dir=dir, recursive=True)]
    
    sub_datapacks = 'data/minecraft/datapacks'
    
    lines = []
    data_paths = [('','')]
    for dp in glob.glob('*/', root_dir=os.path.join(temp, sub_datapacks), recursive=False):
        data_paths.append((dp, os.path.join(sub_datapacks, dp)))
        lines.append(namespace(dp.strip('\\').strip('//')))
    if lines:
        write_lines(os.path.join(temp, 'lists', 'datapacks.txt'), sorted(lines))
    
    
    # structures.nbt
    dir = 'data/minecraft/structures'
    if not os.path.exists(os.path.join(temp, dir)):
        dir = 'assets/minecraft/structures' # old
    lines = set()
    for dp, p in data_paths:
        lines.update([namespace(filename(j)) for j in glob.iglob('**/*.nbt', root_dir=os.path.join(temp, dir, p), recursive=True)])
    if lines:
        write_lines(os.path.join(temp, 'lists', 'structures.nbt.txt'), sorted(lines))
    
    # structures.snbt
    for dp, p in data_paths:
        for f in glob.iglob('**/*.nbt', root_dir=os.path.join(temp, dir, p), recursive=True):
            serialize_nbt(os.path.join(temp, dir, p, f))
    
    # advancements
    dir = 'data/minecraft/advancements'
    if not os.path.exists(os.path.join(temp, dir)):
        dir = 'assets/minecraft/advancements' # old
    entries = set()
    recipes = set()
    tags = set()
    for dp, p in data_paths:
        for j in glob.iglob('**/*.json', root_dir=os.path.join(temp, p, dir), recursive=True):
            j = filename(j)
            if j.startswith('recipes/'):
                t = recipes
            else:
                t = entries
            t.add(namespace(j))
        
        tags.update(enum_json(os.path.join(temp, p, 'data/minecraft/tags/advancements'), is_tag=True))
    
    lines = sorted(entries) + sorted(tags)
    if lines:
        write_lines(os.path.join(temp, 'lists', 'advancements.txt'), sorted(lines))
    if recipes:
        write_lines(os.path.join(temp, 'lists', 'advancements.recipes.txt'), sorted(recipes))
    
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
    
    # special subdir (not in registries)
    lst_subdir = [
        'dimension',
        'dimension_type',
        'biome_parameters',
        'chat_type',
        
        'recipes',
        'trim_material',
        'trim_pattern',
        'damage_type',
    ]
    for subdir in lst_subdir:
        entries = set()
        tags = set()
        for dp, p in data_paths:
            entries.update(enum_json(os.path.join(temp, p, 'data/minecraft',      subdir)))
            tags.update(   enum_json(os.path.join(temp, p, 'data/minecraft/tags', subdir), is_tag=True))
        lines = sorted(entries) + sorted(tags)
        if lines:
            write_lines(os.path.join(temp, 'lists', subdir+'.txt'), lines)
    
    
    # loot_tables
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
            return 'loot_table[]'+namespace(entry['name'])
        
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
                TypeError("Unsupported function '{}' in loot_tables '{}'".format('set_enchantments', name))
            
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
    
    for dp, p in data_paths:
        for loot in glob.iglob('**/*.json', root_dir=os.path.join(temp, p, dir), recursive=True):
            if loot == 'empty.json':
                continue
            table = read_json(os.path.join(temp, p, dir, loot))
            name = filename(loot)
            
            rslt_tbl :list[TBLpool] = []
            
            if name.startswith('blocks'):
                continue
            else:
                
                for pool in table.get('pools', {}):
                    tbl_pool = TBLpool()
                    tbl_pool.rolls = mcrange(name, pool.get('rolls', 1))
                    
                    bonus = pool.get('bonus_rolls', 0)
                    if bonus:
                        bonus = 'bonus rolls: '+ no_end_0(bonus)
                    comment = lootcomment(name, pool)
                    
                    tbl_pool.comment = ', '.join([e for e in [bonus, comment] if e])
                    
                    rslt_tbl.append(tbl_pool)
                    
                    def addentrie(e):
                        tbl_entrie = TBLentrie(tbl_pool)
                        tbl_entrie.name = get_simple(name, e)
                        tbl_entrie.weight = e.get('weight', 1)
                        if tbl_entrie.name == 'empty':
                            tbl_entrie.count = ''
                        else:
                            tbl_entrie.count = lootcount(name, e)
                        tbl_entrie.comment = lootcomment(name, e)
                        tbl_pool.append(tbl_entrie)
                    
                    if 'items' in pool:
                        for e in pool['items']:
                            addentrie(e)
                    elif 'entries' in pool:
                        for e in pool['entries']:
                            addentrie(e)
                    else:
                        raise TypeError("Invalid input pool")
            
            lines_txt = []
            lines_tbl = []
            
            head_tbl = ['Name', 'Count', 'Chance', 'Weight', 'Comment']
            for l in rslt_tbl:
                if '..' in l.rolls:
                    roll = ' to '.join(l.rolls.split('..', 1))+' time'
                else:
                    roll = l.rolls+' time'
                lines_tbl.append([roll,'--','--','--',l.comment])
                
                for e in l:
                    lines_txt.append(e.name)
                    c = e.chance
                    if c < 1:
                        c = str(round(c, 2))
                    else:
                        c = no_end_0(round(c, 1))
                    lines_tbl.append([e.name, e.count, c+'%', e.propabilty, e.comment])
                
                lines_txt.append('')
                lines_tbl.append(None)
            
            while lines_txt and not lines_txt[-1]:
                lines_txt.pop(-1)
            if not lines_txt:
                lines_txt.append('empty')
            write_lines(os.path.join(temp, 'lists/loot_tables', name+'.txt'), lines_txt)
            
            
            while lines_tbl and not lines_tbl[-1]:
                lines_tbl.pop(-1)
            if not lines_tbl:
                lines_tbl.append(['empty','','100%','1',''])
            
            for i in range(len(lines_tbl)):
                if lines_tbl[i]:
                    for y in range(len(lines_tbl[i])):
                        d = str(lines_tbl[i][y])
                        if d: lines_tbl[i][y] = no_end_0(d)
            
            write_tbl_csv(os.path.join(temp, 'lists/loot_tables', name+'.csv'), head_tbl, lines_tbl)
            write_tbl_md(os.path.join(temp, 'lists/loot_tables', name+'.md'), head_tbl, lines_tbl)
    
    # worldgen
    dir = 'data/minecraft/worldgen'
    if not os.path.exists(os.path.join(temp, dir)):
        dir = 'reports/minecraft/worldgen' # old
        if not os.path.exists(os.path.join(temp, dir)):
            dir = 'reports/worldgen/minecraft/worldgen' # legacy
    
    for subdir in glob.iglob('*/', root_dir=os.path.join(temp, dir), recursive=False):
        subdir = subdir.strip('/\\')
        entries = set()
        tags = set()
        for dp, p in data_paths:
            entries.update(enum_json(os.path.join(temp, p, dir,                            subdir)))
            tags.update(   enum_json(os.path.join(temp, p, 'data/minecraft/tags/worldgen', subdir), is_tag=True))
        write_lines(os.path.join(temp, 'lists/worldgen', subdir +'.txt'), sorted(entries) + sorted(tags))
    
    dir = os.path.join(temp, 'reports/biomes') #legacy
    if os.path.exists(dir):
        write_lines(os.path.join(temp, 'lists/worldgen', 'biome.txt'), sorted(enum_json(dir)))
    
    
    # blocks
    blockstates = {}
    for k,v in read_json(os.path.join(temp, 'reports/blocks.json')).items():
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
            if vk not in blockstates:
                blockstates[vk] = {}
            
            for vs in v[vk]:
                if vs not in blockstates[vk]:
                    blockstates[vk][vs] = {}
                
                for vv in v[vk][vs]:
                    if vv not in blockstates[vk][vs]:
                        blockstates[vk][vs][vv] = []
                    
                    blockstates[vk][vs][vv].append(namespace(k))
    
    for k,v in blockstates.items():
        if k == 'properties':
            for kk,vv in v.items():
                for zk,zv in vv.items():
                    write_lines(os.path.join(temp, 'lists/blocks/properties', kk+'='+zk+'.txt'), sorted(zv))
        else:
            for kk,vv in v.items():
                write_json(os.path.join(temp, 'lists/blocks/', k, kk+'.json'), vv)
    
    # commands
    lines = []
    
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
                if type not in lines:
                    lines.append(type)
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
            if len(entry['redirect']) > 1:
                raise TypeError("Over number 'redirect' in commands '{}'".format(name))
            
            rslt.append(base +' >>redirect{'+ entry['redirect'][0] +'}')
        
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
        write_json(os.path.join(temp, 'lists/commands/', name+'.json'), v)
        write_lines(os.path.join(temp, 'lists/commands/', name+'.txt'), get_syntaxes(name, v))
    
    lines.sort()
    if lines:
        write_lines(os.path.join(temp, 'lists/command_argument_type.txt'), lines)
    
    
    # registries
    lines = [namespace(k) for k in read_json(os.path.join(temp, 'reports/registries.json')).keys()]
    lines.sort()
    if lines:
        write_lines(os.path.join(temp, 'lists/registries.txt'), lines)
    
    
    for k,v in read_json(os.path.join(temp, 'reports/registries.json')).items():
        name = flatering(k)
        
        dir = os.path.join('data/minecraft', name)
        if not os.path.exists(os.path.join(temp, dir)):
            dir = dir + 's'
        
        tagdir = os.path.join('data/minecraft/tags', name)
        if not os.path.exists(os.path.join(temp, tagdir)):
            tagdir = tagdir + 's'
        
        entries = set()
        tags = set()
        for dp, p in data_paths:
            entries.update([namespace(k) for k in v['entries'].keys()])
            entries.update(enum_json(os.path.join(temp, p, dir)))
            tags.update(   enum_json(os.path.join(temp, p, tagdir), is_tag=True))
        write_lines(os.path.join(temp, 'lists', name +'.txt'), sorted(entries) + sorted(tags))
    
    
    # tags
    entries = set()
    for dp, p in data_paths:
        dir = os.path.join(temp, p, 'data/minecraft/tags')
        entries.update(flatering(j) for j in glob.iglob('**/*.json', root_dir=dir, recursive=True))
    
    for name in entries:
        lines = []
        for dp, p in data_paths:
            j = os.path.join(temp, p, 'data/minecraft/tags', name)
            for v in read_json(j).get('values', []):
                if v not in lines:
                    lines.append(v)
        
        write_lines(os.path.join(temp, 'lists', 'tags', filename(name)+'.txt'), lines)
    
    
    # sounds
    full_lines = set()
    for sounds in ['minecraft/sounds.json', 'sounds.json']:
        sounds = os.path.join(temp, 'assets', sounds)
        if os.path.exists(sounds):
            for k,v in read_json(sounds).items():
                name = flatering(k)
                write_json(os.path.join(temp, 'lists/sounds/', name+'.json'), v)
                
                lines = v['sounds']
                for idx,v in enumerate(lines):
                    if isinstance(v, dict):
                        lines[idx] = v['name']
                    lines[idx] = namespace(lines[idx])
                full_lines.update(lines)
                write_lines(os.path.join(temp, 'lists/sounds/', name+'.txt'), lines)
            
            break
    
    if full_lines:
        write_lines(os.path.join(temp, 'lists/sounds.txt'), sorted(full_lines))
    
    # languages
    src_lang = {}
    search_term = ['code', 'name', 'region']
    for lang in glob.iglob('assets/lang/*.lang', root_dir=temp, recursive=False):
        # old format
        new_lang = {}
        for l in read_lines(os.path.join(temp, lang)):
            for st in search_term:
                if l.startswith('language.'+st+'='):
                    new_lang[st] = l.split('=',1)[1]
            
            if len(search_term) == len(new_lang):
                break
        
        if len(search_term) == len(new_lang):
            src_lang[new_lang['code']] = {'region':new_lang['region'], 'name':new_lang['name']}
    
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
    
    ## need this to update the last edit attribut of the file
    ## to the last parsing
    languages_json = os.path.join(temp, 'lists', 'languages.json')
    languages = read_json(languages_json)
    if languages:
        write_json(languages_json, languages)
    else:
        safe_del(languages_json)
    safe_del(pack_mcmeta)
    
    # list assets.txt
    lst_assets = read_json(os.path.join(temp, 'assets.json')).get('objects', {})
    if lst_assets:
        write_lines(os.path.join(temp, 'assets.txt'), sorted(lst_assets.keys()))
    
    
    # list /assets/
    lst_exlude = ['lang', 'shaders', 'advancements']
    root_dir = os.path.join(temp, 'assets')
    if os.path.exists(os.path.join(temp, 'assets', 'minecraft')):
        lst_namespace = [flatering(d).strip('/') for d in glob.iglob('*/', root_dir=os.path.join(temp, 'assets'), recursive=False)]
        lst_dir = set()
        for ns in lst_namespace:
            lst_dir.update([flatering(d).strip('/') for d in glob.iglob('*/', root_dir=os.path.join(temp, 'assets', ns), recursive=False)])
        
        lst_dir = list(lst_dir)
        for exlude in lst_exlude:
            if exlude in lst_dir:
                lst_dir.remove(exlude)
    else:
        lst_namespace = []
        lst_dir = []
    
    lst_ext = ['json', 'txt', 'png']
    
    def get_lines_assets(dir, ext):
        rslt = []
        for ns in lst_namespace:
            root = os.path.join(root_dir, ns, dir)
            for f in glob.iglob('**/*.'+ext, root_dir=root, recursive=True):
                l = namespace(filename(f), ns=ns)
                if ext == 'png':
                    if os.path.exists(os.path.join(root, f +'.mcmeta')):
                        l = l+ '  [mcmeta]'
                rslt.append(l)
        return rslt
    
    for dir in lst_dir:
        for ext in lst_ext:
            lines = get_lines_assets(dir, ext)
            if lines:
                txt_path = dir + ('' if ext == 'json' else '.'+ext) +'.txt'
                write_lines(os.path.join(temp, 'lists', txt_path), sorted(lines))
    
    lines = {}
    shaders_dir = os.path.join(root_dir, 'shaders')
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
    
    if not lst_dir:
        # old /assets/
        for name, ext in [('textures','png'), ('texts','txt')]:
            lines = [namespace(filename(f)) for f in glob.iglob('**/*.'+ext, root_dir=root_dir, recursive=True)]
            if lines:
                txt_path = name + '.'+ext +'.txt'
                write_lines(os.path.join(temp, 'lists', txt_path), sorted(lines))

if __name__ == "__main__":
    main()