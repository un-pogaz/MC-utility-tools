#common

import json
import os.path

from github import GitHub

GITHUB_DATA = GitHub('un-pogaz', 'MC-generated-data')
GITHUB_DATA_LATEST = GitHub('un-pogaz', 'MC-generated-data-latest')
GITHUB_BUILDER = GitHub('un-pogaz', 'MC-utility-tools')


def run_animation(awaitable, text_wait, text_end=None):
    import asyncio
    import time
    from threading import Thread
    
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
    
    :type command_line:     string
    :param command_line:    commands to execute
    :type wait:             bool
    :param wait:            Wait for the file to be closed
    :rtype:                 subprocess
    :return:                The pointer the subprocess returned by the Popen call
    """
    
    from subprocess import DEVNULL, PIPE, Popen
    
    if not isinstance(command_line, str):
        for idx in range(len(command_line)):
            if ' ' in command_line[idx]: command_line[idx] = '"'+command_line[idx]+'"'
        command_line = ' '.join(command_line)
    
    #subproc = Popen(command_line, shell=True)
    subproc = Popen(command_line, stdout=DEVNULL, stderr=DEVNULL, shell=True)
    
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

def write_json(path, obj, sort_keys: bool=False):
    make_dirname(path)
    with open(path, 'wt', newline='\n', encoding='utf-8') as f:
        f.write(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=sort_keys))

def read_text(path):
    with open(path, 'rt', encoding='utf-8') as f:
        return ''.join(f.readlines())

def write_text(path, text):
    with open(path, 'wt', newline='\n', encoding='utf-8') as f:
        f.write(text)

def read_lines(path):
    return [l for l in read_text(path).splitlines(False)]

def write_lines(path, lines):
    make_dirname(path)
    with open(path, 'wt', newline='\n', encoding='utf-8') as f:
        if len(lines) == 0:
            f.write('')
        else:
            f.write('\n'.join(lines))


def safe_del(path):
    import shutil
    
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

def remove_empty(path):
    """
    recursive remove empty folder
    """
    import os
    
    for p, _, _ in list(os.walk(path))[::-1]:
        if len(os.listdir(p)) == 0:
            os.rmdir(p)


def hash_file(file, buffer_size=65536):
    if os.path.exists(file):
        import hashlib
        
        algo = hashlib.sha1()
        with open(file, 'rb') as f:
            while True:
                data = f.read(buffer_size)
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
    from urllib import request
    
    url = url.replace('http://', 'https://')
    return request.urlretrieve(url, filename, reporthook, data)

def urlopen(url) :
    from urllib import request
    
    url = url.replace('http://', 'https://')
    return request.urlopen(url, )


VERSION_MANIFEST = None
def update_version_manifest():
    global VERSION_MANIFEST
    
    version_manifest_path = os.path.join('version_manifest.json')
    VERSION_MANIFEST = read_json(version_manifest_path, {'latest':{'release': None, 'snapshot': None}, 'versions':[], 'pack_format':{}, 'versioning':{}, 'versions_history':[]})
    
    edited = not os.path.exists(version_manifest_path)
    _init_release = VERSION_MANIFEST['latest']['release']
    _init_snapshot = VERSION_MANIFEST['latest']['snapshot']
    def read_version_manifest(read_manifest):
            edited = False
            if VERSION_MANIFEST['latest']['release'] != read_manifest['latest']['release']:
                VERSION_MANIFEST['latest']['release'] = read_manifest['latest']['release']
            
            if VERSION_MANIFEST['latest']['snapshot'] != read_manifest['latest']['snapshot']:
                VERSION_MANIFEST['latest']['snapshot'] = read_manifest['latest']['snapshot']
            
            versions = { v['id']:v for v in VERSION_MANIFEST['versions'] }
            
            for k,v in { v['id']:v for v in read_manifest['versions'] }.items():
                v.pop('sha1', None)
                v.pop('complianceLevel', None)
                
                if k not in versions:
                    versions[k] = v
                    edited = True
            
            VERSION_MANIFEST['versions'] = versions.values()
            VERSION_MANIFEST['versions_history'] = list(versions.keys())
            return edited
    
    try:
        with urlopen(GITHUB_DATA.get_raw('main', 'version_manifest.json')) as fl:
            github_manifest = json.load(fl)
    except:
        github_manifest = None
    
    if github_manifest:
        if read_version_manifest(github_manifest):
            edited = True
        
        def sub_tree(sub_name):
            edited = False
            for v in github_manifest[sub_name]:
                i = VERSION_MANIFEST[sub_name]
                ni = github_manifest[sub_name]
                if v == 'specials':
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
            
            return edited
        
        if sub_tree('versioning'):
            edited = True
        if sub_tree('pack_format'):
            edited = True
    
    with urlopen('https://launchermeta.mojang.com/mc/game/version_manifest_v2.json') as fl:
        if read_version_manifest(json.load(fl)):
            edited = True
    
    if _init_release != VERSION_MANIFEST['latest']['release']:
        edited = True
    if _init_snapshot != VERSION_MANIFEST['latest']['snapshot']:
        edited = True
    
    if edited:
        VERSION_MANIFEST['versions'] = sorted(VERSION_MANIFEST['versions'], key=lambda item: item['releaseTime'], reverse=True)
        VERSION_MANIFEST['versions_history'] = [v['id'] for v in VERSION_MANIFEST['versions']]
        print('INFO: version_manifest.json has been updated')
        write_json(version_manifest_path, VERSION_MANIFEST)

update_version_manifest()

LATEST_RELEASE = VERSION_MANIFEST.get('latest', {}).get('release', None)
LATEST_SNAPSHOT = VERSION_MANIFEST.get('latest', {}).get('snapshot', None)

def version_path(version):
    for k,v in VERSION_MANIFEST['versioning'].items():
        if k == 'specials':
            if version in v:
                return os.path.join('specials', version)
        else:
            if version in v.get('releases', []):
                return os.path.join('releases', version)
            
            for kk,vv in v.items():
                if version in vv:
                    return os.path.join('snapshots', k, kk, version)
    
    return version

def find_output(version):
    import glob
    
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
                print('No version or "manifest_json.json" are declared. One of them are require in quiet mode.')
            else:
                print(f'Enter the version:\nid of the version / r or release for the latest release "{LATEST_RELEASE}" / s or snapshot for the latest snapshot "{LATEST_SNAPSHOT}"')
                version = input()
        
        version = get_latest(version)
        
        for v in VERSION_MANIFEST['versions']:
            if v['id'] == version:
                return version
        
        
        print(f'The version {version} has invalide.', '' if quiet else ' Press any key to exit.')
        if not quiet:
            input()
        exit()

def valide_output(args):
    if args.output and os.path.exists(args.output):
        print(f'The {args.version} already exit at "{args.output}".', 'This output will be overwrited.' if args.overwrite else '' if args.quiet else 'Do you want overwrite them?')
        if (args.quiet and args.overwrite) or input()[:1] == 'y':
            args.overwrite = True
        else:
            exit()


def read_manifest_json(temp, version, manifest_json_path = None):
    import zipfile
    
    manifest_url = None
    for v in VERSION_MANIFEST['versions']:
        if v['id'] == version:
            manifest_url = v['url']
            break
    
    if not manifest_json_path and not manifest_url:
        print(f'Imposible to build Generated data for {version}. The requested version is not in the "version_manifest.json".')
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
    print()
    
    if not error:
        print('Work done with success.','' if quiet else 'Press any key to exit.')
    if not quiet:
        input()


def serialize_nbt(file):
    from nbtlib import nbt
    from nbtlib.literal.serializer import serialize_tag
    snbt = serialize_tag(nbt.load(file), indent=2, compact=False, quote='"').replace('\r\n', '\n').replace('\r', '\n')
    while ' \n' in snbt:
        snbt = snbt.replace(' \n', '\n')
    
    file = os.path.splitext(file)[0]+'.snbt'
    with open(file, mode='wt', newline='\n') as f:
        f.write(snbt)


def info_latest_version():
    for v in VERSION_MANIFEST['versions']:
        if v['id'] == LATEST_SNAPSHOT:
            latest = v
    for v in VERSION_MANIFEST['versions']:
        if v['id'] == LATEST_RELEASE:
            release = v
    print('latest:', LATEST_SNAPSHOT, '['+latest['releaseTime']+']')
    print('release:', LATEST_RELEASE, '['+release['releaseTime']+']')

if __name__ == "__main__":
    info_latest_version()
    print()
