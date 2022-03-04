VERSION = (0, 1, 0)

def as_bytes(x, encoding='utf-8'):
    if isinstance(x, str):
        return x.encode(encoding)
    if isinstance(x, bytes):
        return x
    if isinstance(x, bytearray):
        return bytes(x)
    if isinstance(x, memoryview):
        return x.tobytes()
    ans = str(x)
    if isinstance(ans, str):
        ans = ans.encode(encoding)
    return ans

def as_unicode(x, encoding='utf-8', errors='strict'):
    if isinstance(x, bytes):
        return x.decode(encoding, errors)
    return str(x)

def is_binary(stream):
    mode = getattr(stream, "mode", None)
    if mode:
        return "b" in mode
    return not isinstance(stream, io.TextIOBase)

def prints(*a, **kw):
    " Print either unicode or bytes to either binary or text mode streams "
    import sys
    stream = kw.get('file', sys.stdout)
    if stream is None:
        return
    sep, end = kw.get('sep'), kw.get('end')
    if sep is None:
        sep = ' '
    if end is None:
        end = '\n'
    if is_binary(stream):
        encoding = getattr(stream, 'encoding', None) or 'utf-8'
        a = (as_bytes(x, encoding=encoding) for x in a)
        sep = as_bytes(sep)
        end = as_bytes(end)
    else:
        a = (as_unicode(x, errors='replace') for x in a)
        sep = as_unicode(sep)
        end = as_unicode(end)
    for i, x in enumerate(a):
        if sep and i != 0:
            stream.write(sep)
        stream.write(x)
    if end:
        stream.write(end)
    if kw.get('flush'):
        try:
            stream.flush()
        except Exception:
            pass


first_missing = True
def install(package, test=None):
    global first_missing
    import sys, importlib, subprocess
    
    test = test or package
    spam_spec = importlib.util.find_spec(package)
    found = spam_spec is not None
    
    if not found:
        if first_missing:
            prints('Missing dependency')
            first_missing = False
        prints('Instaling:', package)
        subprocess.check_call([sys.executable, '-m', 'pip', '-q', 'install', package])


import sys, argparse, os.path, json, io, glob, time
import pathlib, urllib.request, shutil
from collections import OrderedDict


install('keyboard')
import keyboard

from github import GitHub

if not first_missing:
    prints('All dependency are instaled')
    prints()

github_data = GitHub('un-pogaz', 'MC-generated-data')
github_builder = GitHub('un-pogaz', 'MC-generated-data-builder')


animation_loop = ['.  ',' . ','  .']

def run_animation(awaitable, text_wait, text_end=None):
    import asyncio
    
    global animation_run
    
    def start_animation():
        global animation_run
        idx = 0
        while animation_run:
            print(text_wait + animation_loop[idx % len(animation_loop)], end="\r")
            idx += 1
            if idx == len(animation_loop): idx == 0
            time.sleep(0.2)
    
    from threading import Thread
    
    animation_run = True
    t = Thread(target=start_animation)
    t.start()
    asyncio.run(awaitable())
    animation_run = False
    prints(text_wait, text_end or '', ' ' * len(animation_loop[0]))
    time.sleep(0.3)
    del t


def json_read(path, default=None):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except:
        return default or {}

def json_write(path, obj):
    with open(path, 'w',) as f:
        json.dump(obj, f, indent=2)

def write_lines(path, lines):
    dir = os.path.dirname(path)
    if dir and not os.path.exists(dir):
        os.makedirs(dir)
    with open(path, 'w') as f:
        f.writelines(l+'\n' for l in lines[:-1])
        f.write(lines[-1])

def safe_del(path):
    def remove(a):
        pass
    
    if os.path.exists(path):
        if os.path.isfile(path):
            remove = os.remove
        if os.path.isdir(path):
            remove = shutil.rmtree
        if os.path.islink(path):
            remove = os.unlink
    
    try:
        remove(path)
    except Exception as ex:
        pass



version_manifest = None

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
    global args, version_manifest
    
    prints(f'--==| Minecraft: Generated data builder {VERSION} |==--')
    prints()
    
    last, _, _ = github_builder.check_versions()
    if last > VERSION:
        prints('A new version is available!')
        prints('A new version is available!')
        prints()
    
    
    if args.manifest_json:
        args.version = json_read(args.manifest_json, {'id': None})['id']
    
    else:
        if not args.version:
            if args.quiet:
                prints('No version or "manifest_json.json" are declared. One of them are require in quiet mode.')
            else:
                prints('Enter the version:\n\tr or release for the latest release / s or snapshot for the latest snapshot')
                args.version = input()
        
        args.version = get_latest(args.version)
        
        version_json = None
        for v in version_manifest['versions']:
            if v['id'] == args.version:
                version_json = v
                break
        
        if not version_json:
            prints( f'The version {args.version} has invalide.' + '' if args.quiet else ' Press any key to exit.')
            if not args.quiet:
                keyboard.read_key()
            return -1
    
    if not args.output:
        args.output = find_output(args.version)
    
    if args.output and os.path.exists(args.output):
        prints(f'The {args.version} already exit at "{args.output}".', 'This output will be overwrited.' if args.overwrite else '' if args.quiet else 'Do you want overwrite them?')
        if (args.quiet and args.overwrite) or input()[:1] == 'y':
            args.overwrite = True
        else:
            return -1
    
    if args.zip == None:
        if args.quiet:
            args.zip = False
        else:
            prints('Do you want to empack the Generated data folder in a ZIP file?')
            args.zip = input()[:1] == 'y'
    
    prints()
    
    error = build_generated_data(args)
    
    prints()
    
    if not error:
        prints('Work done with success.','' if args.quiet else 'Press any key to exit.')
    if not args.quiet:
        keyboard.read_key()
    return error

def update_version_manifest():
    global version_manifest
    
    version_manifest_path = os.path.join('version_manifest.json')
    version_manifest = json_read(version_manifest_path, { 'latest':{'release': None, 'snapshot': None}, 'versions':[], 'paths':{}, 'versioning':{}})
    
    edited = False
    def update_version_manifest(read_manifest):
            edited = False
            if version_manifest['latest']['release'] != read_manifest['latest']['release']:
                version_manifest['latest']['release'] = read_manifest['latest']['release']
                edited = True
            
            if version_manifest['latest']['snapshot'] != read_manifest['latest']['snapshot']:
                version_manifest['latest']['snapshot'] = read_manifest['latest']['snapshot']
                edited = True
            
            versions = { v['id']:v for v in version_manifest['versions'] }
            
            for k,v in { v['id']:v for v in read_manifest['versions'] }.items():
                if 'sha1' in v: del v['sha1']
                if 'complianceLevel' in v: del v['complianceLevel']
                
                if k not in versions:
                    versions[k] = v
                    edited = True
            
            version_manifest['versions'] = versions.values()
            
            return edited
    
    with urllib.request.urlopen(github_data.get_raw('main', 'version_manifest.json')) as fl:
            github_manifest = json.load(fl)
            
            if update_version_manifest(github_manifest):
                edited = True
            
            for k in github_manifest['paths']:
                if k not in version_manifest['paths']:
                    version_manifest['paths'][k] = github_manifest['paths'][k]
                    edited = True
            
            for v in github_manifest['versioning']:
                i = version_manifest['versioning']
                ni = github_manifest['versioning']
                if v == 'special':
                    if v not in i:
                        i[v] = []
                        edited = True
                    
                    iv = i[v]
                    for idx, e in enumerate(ni[v], start=0):
                        if e not in iv:
                            iv.insert(idx, e)
                            edited = True
                        
                else:
                    if v not in i:
                        i[v] = {}
                        edited = True
                    
                    iv = i[v]
                    niv = ni[v]
                    for t in niv:
                        if t not in iv:
                            iv[t] = []
                            edited = True
                        
                        ivt = iv[t]
                        nivt = niv[t]
                        for idx, e in enumerate(nivt, start=0):
                            if e not in ivt:
                                ivt.insert(idx, e)
                                edited = True
    
    with urllib.request.urlopen('https://launchermeta.mojang.com/mc/game/version_manifest_v2.json') as fl:
            if update_version_manifest(json.load(fl)):
                edited = True
    
    
    if edited:
        version_manifest['versions'] = sorted(version_manifest['versions'], key=lambda item: item['releaseTime'], reverse=True)
        json_write(version_manifest_path, version_manifest)
    
update_version_manifest()

def find_output(version):
    output = glob.glob(f'**/{version}/', root_dir='.', recursive=True)
    if len(output):
        return output[0]
    else:
        return None

def get_latest(version):
    if version in ['r','release']:
        return version_manifest['latest']['release']
    if version in ['s','snapshot', 'l', 'latest']:
        return version_manifest['latest']['snapshot']
    
    return version

def build_generated_data(args):
    import subprocess, zipfile, zipimport
    from tempfile import gettempdir
    from datetime import datetime
    
    global version_manifest
    
    if args.manifest_json:
        version = json_read(args.manifest_json, {'id': None})['id']
    else:
        version = get_latest(args.version)
    
    overwrite = args.overwrite
    zip       = args.zip
    
    temp = os.path.join(gettempdir(), 'MC Generated data', version)
    if not os.path.exists(temp):
        os.makedirs(temp)
    
    manifest_url = None
    for v in version_manifest['versions']:
        if v['id'] == version:
            manifest_url = v['url']
            break
    
    if not args.manifest_json and not manifest_url:
        prints(f'Imposible to build Generated data for {version}. The requested version is not in the "version_manifest.json".')
        return -1
    
    if args.manifest_json:
        manifest_json = json_read(args.manifest_json)
    else:
        manifest = os.path.join(temp, version+'.json')
        urllib.request.urlretrieve(manifest_url, manifest)
        manifest_json = json_read(manifest)
    
    
    version_json = OrderedDict()
    version_json['id'] = manifest_json['id']
    version_json['type'] = manifest_json['type']
    version_json['time'] = manifest_json['time']
    version_json['releaseTime'] = manifest_json['releaseTime']
    version_json['url'] = manifest_url
    
    if 'assetIndex' in manifest_json:
        #minecraft/original manifest
        version_json['asset_index'] = manifest_json['assetIndex']['url']
        version_json['client'] = manifest_json['downloads']['client']['url']
        version_json['client_mappings'] = manifest_json['downloads']['client_mappings']['url']
        version_json['server'] = manifest_json['downloads']['server']['url']
        version_json['server_mappings'] = manifest_json['downloads']['server_mappings']['url']
    else:
        #mc Generated data manifest
        version_json['asset_index'] = manifest_json['asset_index']
        version_json['client'] = manifest_json['client']
        version_json['client_mappings'] = manifest_json['client_mappings']
        version_json['server'] = manifest_json['server']
        version_json['server_mappings'] = manifest_json['server_mappings']
    
    output = args.output or find_output(version) or version_manifest['paths'][version] or os.path.join(version_json['type'], version)
    
    
    if os.path.exists(output) and not overwrite:
        prints(f'Imposible to build Generated data for {version}. The output "{output}" already exit and the overwrite is not enabled.')
        return -1
    
    
    prints(f'Build Generated data for {version}')
    
    fix = datetime.fromisoformat('2021-09-21T14:36:06+00:00')
    dt = datetime.fromisoformat(version_json['releaseTime'])
    
    cmd = '-DbundlerMainClass=net.minecraft.data.Main -jar server.jar --all'
    if dt < fix:
        cmd = '-cp server.jar net.minecraft.data.Main --all'
    
    prints()
    
    client = os.path.join(temp, 'client.jar')
    async def client_dl():
        if not os.path.exists(client):
            urllib.request.urlretrieve(version_json['client'], client)
    run_animation(client_dl, 'Downloading client.jar', '> OK')
    
    server = os.path.join(temp, 'server.jar')
    async def server_dl():
        if not os.path.exists(server):
            urllib.request.urlretrieve(version_json['server'], server)
    run_animation(server_dl, 'Downloading server.jar', '> OK')
    
    async def data_server():
        subprocess.run('java ' + cmd, cwd=temp, shell=False, capture_output=False, stdout=subprocess.DEVNULL)
    run_animation(data_server, 'Extracting data server', '> OK')
    
    
    async def data_client():
        with zipfile.ZipFile(client, mode='r') as zip:
            for entry in zip.filelist:
                if entry.filename.startswith('assets/') or entry.filename.startswith('data/'):
                    safe_del(os.path.join(temp, 'generated', entry.filename))
                    zip.extract(entry.filename, os.path.join(temp, 'generated'))
    run_animation(data_client, 'Extracting data client', '> OK')
    
    
    json_write(os.path.join(temp, 'generated', version+'.json') , version_json)
    
    async def listing_various():
        
        for dir in ['libraries', 'logs', 'versions', 'generated/.cache', 'generated/assets/.mcassetsroot', 'generated/data/.mcassetsroot']:
            safe_del(os.path.join(temp, dir))
        
        
        def enum_json(dir):
            return [j[:-5].replace('\\', '/') for j in glob.glob(f'**/*.json', root_dir=dir, recursive=True)]
        
        for k,v in json_read(os.path.join(temp, 'generated/reports/registries.json')).items():
            name = k.split(':', maxsplit=2)[-1]
            
            tags = os.path.join(temp,'generated/data/minecraft/tags', name)
            if not os.path.exists(tags):
                tags = tags + 's'
            
            entries = [k for k in v['entries'].keys()]
            tags = ['#minecraft:'+j for j in enum_json(tags)]
            write_lines(os.path.join(temp, 'generated/lists', name +'.txt'), entries + tags)
        
        for dir in os.scandir(os.path.join(temp, 'generated/reports/worldgen/minecraft/worldgen')):
            if dir.is_dir:
                folder = ['minecraft:'+j for j in enum_json(dir.path)]
                tags = ['#minecraft:'+j for j in enum_json(os.path.join(temp,'generated/data/minecraft/tags/worldgen', dir.name))]
                write_lines(os.path.join(temp, 'generated/lists/worldgen', dir.name +'.txt'), folder + tags)
        
        
    
    run_animation(listing_various, 'Listing elements and various', '> OK')
    
    
    if zip:
        async def make_zip():
            zip_path = os.path.join(temp, 'zip.zip')
            safe_del(zip_path)
            shutil.make_archive(os.path.splitext(zip_path)[0], 'zip', root_dir=os.path.join(temp, 'generated'))
            os.rename(zip_path, os.path.join(temp, 'generated', version+'.zip'))
        run_animation(make_zip, 'Empack into a ZIP', '> OK')
    
    async def move_generated_data():
        if os.path.exists(output):
            if overwrite:
                safe_del(output)
            else:
                prints(f'The output at "{output}" already exit and the overwrite is not enable')
                return -1
        
        os.makedirs(output)
        for dir in os.listdir(os.path.join(temp, 'generated')):
            shutil.move(os.path.join(temp, 'generated', dir), os.path.join(output, dir))
        
    run_animation(move_generated_data, f'Move generated data to "{output}"', '> OK')
    



if __name__ == "__main__":
    
    main()