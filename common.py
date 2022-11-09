#common

import sys, argparse, os.path, json, io, glob, time
import pathlib, urllib.request, shutil, zipfile
from collections import OrderedDict


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


# dependency package

missing_package = False
def install(package, test=None):
    global missing_package
    import sys, importlib, subprocess
    
    test = test or package
    spam_spec = importlib.util.find_spec(package)
    found = spam_spec is not None
    
    if not found:
        if missing_package:
            prints('Missing dependency')
            missing_package = True
        prints('Instaling:', package)
        subprocess.check_call([sys.executable, '-m', 'pip', '-q', 'install', package])

install('keyboard')

if missing_package:
    prints('All dependency are instaled')
    prints()

import keyboard



from github import GitHub

GITHUB_DATA = GitHub('un-pogaz', 'MC-generated-data')
GITHUB_DATA_LATEST = GitHub('un-pogaz', 'MC-generated-data-latest')
GITHUB_BUILDER = GitHub('un-pogaz', 'MC-utility-tools')


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

def run_command(command_line, wait=True):
    """
    Lauch a command line and return the subprocess
    
    :type filepath:     string
    :param filepath:    Path to the file to open
    :type wait:         bool
    :param wait:        Wait for the file to be closed
    :rtype:             subprocess
    :return:            The pointer the subprocess returned by the Popen call
    """
    
    import os
    from subprocess import Popen, PIPE
    
    if not isinstance(command_line, str):
        for idx in range(len(command_line)):
            if ' ' in command_line[idx]: command_line[idx] = '"'+command_line[idx]+'"'
        command_line = ' '.join(command_line)
    
    subproc = Popen(command_line, shell=True)
    #subproc = Popen(command_line, stdout=PIPE, stderr=PIPE, shell=True)
    
    if wait:
        subproc.wait()
    return subproc


def make_dirname(path):
    dir = os.path.dirname(path)
    if dir:
        os.makedirs(dir, exist_ok=True)

def read_json(path, default=None):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except:
        return default or {}

def write_json(path, obj):
    make_dirname(path)
    with open(path, 'w',) as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def write_lines(path, lines):
    make_dirname(path)
    with open(path, 'w') as f:
        if len(lines) == 0:
            f.write('')
        else:
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


BUF_SIZE = 65536
def hash_file(algo, path):
    import hashlib
    if os.path.exists(path):
        with open(path, 'rb') as f:
            while True:
                data = f.read(BUF_SIZE)
                if not data:
                    break
                algo.update(data)
        
        return algo.hexdigest()



VERSION_MANIFEST = None
def update_version_manifest():
    global VERSION_MANIFEST
    
    version_manifest_path = os.path.join('version_manifest.json')
    VERSION_MANIFEST = read_json(version_manifest_path, { 'latest':{'release': None, 'snapshot': None}, 'versions':[], 'pack_format':{}, 'versioning':{}})
    
    edited = not os.path.exists(version_manifest_path)
    def update_version_manifest(read_manifest):
            edited = False
            if VERSION_MANIFEST['latest']['release'] != read_manifest['latest']['release']:
                VERSION_MANIFEST['latest']['release'] = read_manifest['latest']['release']
                edited = True
            
            if VERSION_MANIFEST['latest']['snapshot'] != read_manifest['latest']['snapshot']:
                VERSION_MANIFEST['latest']['snapshot'] = read_manifest['latest']['snapshot']
                edited = True
            
            versions = { v['id']:v for v in VERSION_MANIFEST['versions'] }
            
            for k,v in { v['id']:v for v in read_manifest['versions'] }.items():
                if 'sha1' in v: del v['sha1']
                if 'complianceLevel' in v: del v['complianceLevel']
                
                if k not in versions:
                    versions[k] = v
                    edited = True
            
            VERSION_MANIFEST['versions'] = versions.values()
            
            return edited
    
    with urllib.request.urlopen(GITHUB_DATA.get_raw('main', 'version_manifest.json')) as fl:
        github_manifest = json.load(fl)
        
        if update_version_manifest(github_manifest):
            edited = True
        
        def sub_tree(sub_name):
            for v in github_manifest[sub_name]:
                i = VERSION_MANIFEST[sub_name]
                ni = github_manifest[sub_name]
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
        
        sub_tree('versioning')
        sub_tree('pack_format')
    
    with urllib.request.urlopen('https://launchermeta.mojang.com/mc/game/version_manifest_v2.json') as fl:
            if update_version_manifest(json.load(fl)):
                edited = True
    
    
    if edited:
        VERSION_MANIFEST['versions'] = sorted(VERSION_MANIFEST['versions'], key=lambda item: item['releaseTime'], reverse=True)
        VERSION_MANIFEST['pack_format'] = github_manifest['pack_format']
        VERSION_MANIFEST['versioning'] = github_manifest['versioning']
        write_json(version_manifest_path, VERSION_MANIFEST)

update_version_manifest()

LATEST_RELEASE = VERSION_MANIFEST.get('latest', {}).get('release', None)
LATEST_SNAPSHOT = VERSION_MANIFEST.get('latest', {}).get('snapshot', None)

def version_path(version):
    for k,v in VERSION_MANIFEST['versioning'].items():
        if k == 'special':
            if version in v:
                return os.path.join('special', version)
        else:
            if version in v.get('releases', []):
                return os.path.join('releases', version)
            
            for kk,vv in v.items():
                if version in vv:
                    return os.path.join('snapshots', k, kk, version)

def find_output(version):
    output = glob.glob(f'/{version}/', root_dir='.', recursive=False)
    if len(output):
        return output[0]

def get_latest(version, manifest_json_path=None):
    if manifest_json_path:
        return read_json(manifest_json_path, {'id': None})['id']
    
    if version in ['r','release']:
        return LATEST_RELEASE
    if version in ['s','snapshot', 'l', 'latest']:
        return LATEST_SNAPSHOT
    
    return version


def valide_version(version, quiet = False, manifest_json_path = None):
    if manifest_json_path:
        return read_json(manifest_json_path, {'id': None})['id']
    
    else:
        if not version:
            if quiet:
                prints('No version or "manifest_json.json" are declared. One of them are require in quiet mode.')
            else:
                prints(f'Enter the version:\nid of the version / r or release for the latest release "{LATEST_RELEASE}" / s or snapshot for the latest snapshot "{LATEST_SNAPSHOT}"')
                version = input()
        
        version = get_latest(version)
        
        for v in VERSION_MANIFEST['versions']:
            if v['id'] == version:
                return version
        
        
        prints(f'The version {version} has invalide.', '' if quiet else ' Press any key to exit.')
        if not quiet:
            keyboard.read_key()
        sys.exit(-1)

def valide_output(args):
    if args.output and os.path.exists(args.output):
        prints(f'The {args.version} already exit at "{args.output}".', 'This output will be overwrited.' if args.overwrite else '' if args.quiet else 'Do you want overwrite them?')
        if (args.quiet and args.overwrite) or input()[:1] == 'y':
            args.overwrite = True
        else:
            sys.exit(-1)


def read_manifest_json(temp, version, manifest_json_path = None):
    
    manifest_url = None
    for v in VERSION_MANIFEST['versions']:
        if v['id'] == version:
            manifest_url = v['url']
            break
    
    if not manifest_json_path and not manifest_url:
        prints(f'Imposible to build Generated data for {version}. The requested version is not in the "version_manifest.json".')
        return -1
    
    
    if not manifest_json_path:
        manifest_json_path = os.path.join(temp, version+'.json')
        urllib.request.urlretrieve(manifest_url, manifest_json_path)
        if os.path.splitext(manifest_url)[1].lower() == '.zip':
            with zipfile.ZipFile(manifest_json_path) as zip:
                for file in zip.filelist:
                    if os.path.splitext(file.filename)[1].lower() == '.json':
                        with zip.open(file) as zi:
                            manifest_json = json.load(zi)
                        break
            
            write_json(manifest_json_path, manifest_json)
        
    return read_json(manifest_json_path), manifest_url


def work_done(error, quiet = False):
    prints()
    
    if not error:
        prints('Work done with success.','' if quiet else 'Press any key to exit.')
    if not quiet:
        keyboard.read_key()
