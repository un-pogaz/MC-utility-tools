#common

import sys, argparse, os.path, json, io, glob, time
import pathlib, shutil, zipfile
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


def run_animation(awaitable, text_wait, text_end=None):
    import asyncio, time
    global animation_run, msg_last
    run_animation.extra = ''
    msg_last = ''
    
    def start_animation():
        global animation_run, msg_last
        idx = 0
        while animation_run:
            msg = ' '.join([text_wait, run_animation.loop[idx % len(run_animation.loop)],(run_animation.extra or '')])
            print(msg + ' '*(len(msg_last)-len(msg)+1), end='\r')
            msg_last = msg
            idx += 1
            if idx == len(run_animation.loop): idx == 0
            time.sleep(0.2)
    
    from threading import Thread
    
    animation_run = True
    t = Thread(target=start_animation)
    t.start()
    asyncio.run(awaitable())
    animation_run = False
    msg = ' '.join([text_wait, text_end or '> OK'])
    print(msg+' '*(len(msg_last)-len(msg)+1))
    time.sleep(0.2)
    del t
run_animation.extra = ''
run_animation.loop = ['|','/','—','\\']

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
    from subprocess import Popen, DEVNULL, PIPE
    
    if not isinstance(command_line, str):
        for idx in range(len(command_line)):
            if ' ' in command_line[idx]: command_line[idx] = '"'+command_line[idx]+'"'
        command_line = ' '.join(command_line)
    
    #subproc = Popen(command_line, shell=True)
    subproc = Popen(command_line, stdout=DEVNULL, stderr=PIPE, shell=True)
    
    if wait:
        subproc.wait()
    return subproc


def make_dirname(path):
    dir = os.path.dirname(path)
    if dir:
        os.makedirs(dir, exist_ok=True)

def read_json(path, default=None):
    try:
        with open(path, 'rb') as f:
            return json.loads(f.read())
    except:
        return default or {}

def write_json(path, obj):
    make_dirname(path)
    with open(path, 'wt', newline='\n', encoding='utf-8') as f:
        f.write(json.dumps(obj, indent=2, ensure_ascii=False))

def write_lines(path, lines):
    make_dirname(path)
    with open(path, 'wt', newline='\n', encoding='utf-8') as f:
        if len(lines) == 0:
            f.write('')
        else:
            for l in lines[:-1]:
                f.write(l+'\n')
            f.write(lines[-1])

def read_text(path):
    with open(path, 'rt', encoding='utf-8') as f:
        return ''.join(f.readlines())

def write_text(path, text):
    with open(path, 'wt', newline='\n', encoding='utf-8') as f:
        f.write(text)


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
def hash_file(file):
    if os.path.exists(file):
        import hashlib
        algo = hashlib.sha1()
        with open(file, 'rb') as f:
            while True:
                data = f.read(BUF_SIZE)
                if not data:
                    break
                algo.update(data)
        
        return algo.hexdigest()
    
    return None

def hash_test(hash, file):
    if hash and os.path.exists(file):
        return hash == hash_file(file)
    return False


def urlretrieve(url, filename, reporthook=None, data=None):
    import urllib.request
    url = url.replace('http://', 'https://')
    return urllib.request.urlretrieve(url, filename, reporthook, data)

def urlopen(url) :
    import urllib.request
    url = url.replace('http://', 'https://')
    return urllib.request.urlopen(url, )


VERSION_MANIFEST = None
def update_version_manifest():
    global VERSION_MANIFEST
    
    version_manifest_path = os.path.join('version_manifest.json')
    VERSION_MANIFEST = read_json(version_manifest_path, { 'latest':{'release': None, 'snapshot': None}, 'versions':[], 'pack_format':{}, 'versioning':{}})
    
    edited = not os.path.exists(version_manifest_path)
    _init_release = VERSION_MANIFEST['latest']['release']
    _init_snapshot = VERSION_MANIFEST['latest']['snapshot']
    def update_version_manifest(read_manifest):
            edited = False
            if VERSION_MANIFEST['latest']['release'] != read_manifest['latest']['release']:
                VERSION_MANIFEST['latest']['release'] = read_manifest['latest']['release']
            
            if VERSION_MANIFEST['latest']['snapshot'] != read_manifest['latest']['snapshot']:
                VERSION_MANIFEST['latest']['snapshot'] = read_manifest['latest']['snapshot']
            
            versions = { v['id']:v for v in VERSION_MANIFEST['versions'] }
            
            for k,v in { v['id']:v for v in read_manifest['versions'] }.items():
                if 'sha1' in v: del v['sha1']
                if 'complianceLevel' in v: del v['complianceLevel']
                
                if k not in versions:
                    versions[k] = v
                    edited = True
            
            VERSION_MANIFEST['versions'] = versions.values()
            return edited
    
    try:
        with urlopen(GITHUB_DATA.get_raw('main', 'version_manifest.json')) as fl:
            github_manifest = json.load(fl)
    except:
        github_manifest = None
    
    if github_manifest:
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
    
    with urlopen('https://launchermeta.mojang.com/mc/game/version_manifest_v2.json') as fl:
        if update_version_manifest(json.load(fl)):
            edited = True
    
    if _init_release != VERSION_MANIFEST['latest']['release']:
        edited = True
    if _init_snapshot != VERSION_MANIFEST['latest']['snapshot']:
        edited = True
    
    if edited:
        VERSION_MANIFEST['versions'] = sorted(VERSION_MANIFEST['versions'], key=lambda item: item['releaseTime'], reverse=True)
        print('INFO: version_manifest.json has been updated')
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
    
    return version

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
        sys.exit()

def valide_output(args):
    if args.output and os.path.exists(args.output):
        prints(f'The {args.version} already exit at "{args.output}".', 'This output will be overwrited.' if args.overwrite else '' if args.quiet else 'Do you want overwrite them?')
        if (args.quiet and args.overwrite) or input()[:1] == 'y':
            args.overwrite = True
        else:
            sys.exit()


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
        safe_del(manifest_json_path)
        urlretrieve(manifest_url, manifest_json_path)
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

def info_latest_version():
    for v in VERSION_MANIFEST['versions']:
        if v['id'] == LATEST_SNAPSHOT:
            latest = v
    for v in VERSION_MANIFEST['versions']:
        if v['id'] == LATEST_RELEASE:
            release = v
    prints('latest:', LATEST_SNAPSHOT, '['+latest['releaseTime']+']')
    prints('release:', LATEST_RELEASE, '['+release['releaseTime']+']')

if __name__ == "__main__":
    info_latest_version()
    print()