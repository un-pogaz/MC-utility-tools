import json
import os
import re
import sys
from json.encoder import INFINITY, JSONEncoder

from github import GitHub

GITHUB_DATA = GitHub('un-pogaz', 'MC-generated-data')
GITHUB_BUILDER = GitHub('un-pogaz', 'MC-utility-tools')


def run_animation(awaitable, text_wait, text_end=None):
    import asyncio
    import time
    from threading import Thread
    
    global animation_run, msg_last
    run_animation.extra = ''
    msg_last = ''
    
    def start_animation():
        global animation_run, msg_last  # noqa: PLW0602
        idx = 0
        while animation_run:
            msg = ' '.join([text_wait, run_animation.loop[idx % len(run_animation.loop)],(run_animation.extra or '')])
            print(msg + ' '*(len(msg_last)-len(msg)+1), end='\r')
            msg_last = msg
            idx += 1
            if idx >= len(run_animation.loop):
                idx = 0
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
    
    from subprocess import DEVNULL, Popen
    
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
    except Exception:  # noqa: BLE001
        return default or {}

def write_json(path, obj, sort_keys: bool=False):
    make_dirname(path)
    with open(path, 'wt', newline='\n', encoding='utf-8') as f:
        f.write(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=sort_keys))

def read_text(path):
    with open(path, 'rt', encoding='utf-8') as f:
        return ''.join(f.readlines())

def write_text(path, text):
    make_dirname(path)
    with open(path, 'wt', newline='\n', encoding='utf-8') as f:
        f.write(text)

def read_lines(path):
    return [x for x in read_text(path).splitlines(False)]

def write_lines(path, lines, newline_end=True):
    make_dirname(path)
    with open(path, 'wt', newline='\n', encoding='utf-8') as f:
        if len(lines) == 0:
            f.write('')
        else:
            n = '\n'
            s = n.join(lines)
            f.write(s)
            if newline_end and s and s[-1] != n:
                f.write(n)


class LUAEncoder(JSONEncoder):
    item_separator = ', '
    key_separator = '= '
    def iterencode(self, o, _one_shot=False):
        from json.encoder import encode_basestring
        if self.check_circular:
            markers = {}
        else:
            markers = None
        _encoder = encode_basestring
    
        def floatstr(o, allow_nan=self.allow_nan,
                _repr=float.__repr__, _inf=INFINITY, _neginf=-INFINITY):
            # Check for specials.  Note that this type of test is processor
            # and/or platform-specific, so do tests which don't depend on the
            # internals.

            if o != o:
                text = 'NaN'
            elif o == _inf:
                text = 'Infinity'
            elif o == _neginf:
                text = '-Infinity'
            else:
                return _repr(o)

            if not allow_nan:
                raise ValueError(
                    "Out of range float values are not JSON compliant: " +
                    repr(o))

            return text
        
        if self.indent is None or isinstance(self.indent, str):
            indent = self.indent
        else:
            indent = ' ' * self.indent
        
        _iterencode = self._make_iterencode(
                markers, self.default, _encoder, indent, floatstr,
                self.key_separator, self.item_separator, self.sort_keys,
                self.skipkeys, _one_shot)
        return _iterencode(o, 0)

    def _make_iterencode(self, markers, _default, _encoder, _indent, _floatstr,
            _key_separator, _item_separator, _sort_keys, _skipkeys, _one_shot,
            ## HACK: hand-optimized bytecode; turn globals into locals
            ValueError=ValueError,
            dict=dict,
            float=float,
            id=id,
            int=int,
            isinstance=isinstance,
            list=list,
            str=str,
            tuple=tuple,
            _intstr=int.__repr__,
        ):

        def _iterencode_list(lst, _current_indent_level):
            if not lst:
                yield '{}'
                return
            if markers is not None:
                markerid = id(lst)
                if markerid in markers:
                    raise ValueError("Circular reference detected")
                markers[markerid] = lst
            if _indent is not None:
                _current_indent_level += 1
                newline_indent = '\n' + _indent * _current_indent_level
            else:
                newline_indent = None
            yield '{'
            for i, value in enumerate(lst):
                if newline_indent:
                    yield newline_indent
                try:
                    if isinstance(value, str):
                        yield _encoder(value)
                    elif value is None:
                        yield 'nil'
                    elif value is True:
                        yield 'true'
                    elif value is False:
                        yield 'false'
                    elif isinstance(value, int):
                        # Subclasses of int/float may override __repr__, but we still
                        # want to encode them as integers/floats in JSON. One example
                        # within the standard library is IntEnum.
                        yield _intstr(value)
                    elif isinstance(value, float):
                        # see comment above for int
                        yield _floatstr(value)
                    else:
                        if isinstance(value, (list, tuple)):
                            chunks = _iterencode_list(value, _current_indent_level)
                        elif isinstance(value, dict):
                            chunks = _iterencode_dict(value, _current_indent_level)
                        else:
                            chunks = _iterencode(value, _current_indent_level)
                        yield from chunks
                    yield _item_separator
                except GeneratorExit:
                    raise
                except BaseException as exc:
                    exc.add_note(f'when serializing {type(lst).__name__} item {i}')
                    raise
            if newline_indent is not None:
                _current_indent_level -= 1
                yield '\n' + _indent * _current_indent_level
            yield '}'
            if markers is not None:
                del markers[markerid]

        def _iterencode_dict(dct, _current_indent_level):
            if not dct:
                yield '{}'
                return
            if markers is not None:
                markerid = id(dct)
                if markerid in markers:
                    raise ValueError("Circular reference detected")
                markers[markerid] = dct
            yield '{'
            if _indent is not None:
                _current_indent_level += 1
                newline_indent = '\n' + _indent * _current_indent_level
            else:
                newline_indent = None
            if _sort_keys:
                items = sorted(dct.items())
            else:
                items = dct.items()
            for key, value in items:
                if isinstance(key, str):
                    key = _encoder(key)
                # JavaScript is weakly typed for these, so it makes sense to
                # also allow them.  Many encoders seem to do something like this.
                elif isinstance(key, float):
                    # see comment for int/float in _make_iterencode
                    key = _floatstr(key)
                elif key is True:
                    key = 'true'
                elif key is False:
                    key = 'false'
                elif key is None:
                    key = 'nil'
                elif isinstance(key, int):
                    # see comment for int/float in _make_iterencode
                    key = _intstr(key)
                elif _skipkeys:
                    continue
                else:
                    raise TypeError(f'keys must be str, int, float, bool or None, '
                                    f'not {key.__class__.__name__}')
                if newline_indent is not None:
                        yield newline_indent
                yield '['
                yield key
                yield ']'
                yield _key_separator
                try:
                    if isinstance(value, str):
                        yield _encoder(value)
                    elif value is None:
                        yield 'nil'
                    elif value is True:
                        yield 'true'
                    elif value is False:
                        yield 'false'
                    elif isinstance(value, int):
                        # see comment for int/float in _make_iterencode
                        yield _intstr(value)
                    elif isinstance(value, float):
                        # see comment for int/float in _make_iterencode
                        yield _floatstr(value)
                    else:
                        if isinstance(value, (list, tuple)):
                            chunks = _iterencode_list(value, _current_indent_level)
                        elif isinstance(value, dict):
                            chunks = _iterencode_dict(value, _current_indent_level)
                        else:
                            chunks = _iterencode(value, _current_indent_level)
                        yield from chunks
                except GeneratorExit:
                    raise
                except BaseException as exc:
                    exc.add_note(f'when serializing {type(dct).__name__} item {key!r}')
                    raise
                yield _item_separator
            if newline_indent is not None:
                _current_indent_level -= 1
                yield '\n' + _indent * _current_indent_level
            yield '}'
            if markers is not None:
                del markers[markerid]

        def _iterencode(o, _current_indent_level):
            if isinstance(o, str):
                yield _encoder(o)
            elif o is None:
                yield 'nil'
            elif o is True:
                yield 'true'
            elif o is False:
                yield 'false'
            elif isinstance(o, int):
                # see comment for int/float in _make_iterencode
                yield _intstr(o)
            elif isinstance(o, float):
                # see comment for int/float in _make_iterencode
                yield _floatstr(o)
            elif isinstance(o, (list, tuple)):
                yield from _iterencode_list(o, _current_indent_level)
            elif isinstance(o, dict):
                yield from _iterencode_dict(o, _current_indent_level)
            else:
                if markers is not None:
                    markerid = id(o)
                    if markerid in markers:
                        raise ValueError("Circular reference detected")
                    markers[markerid] = o
                newobj = _default(o)
                try:
                    yield from _iterencode(newobj, _current_indent_level)
                except GeneratorExit:
                    raise
                except BaseException as exc:
                    exc.add_note(f'when serializing {type(o).__name__} object')
                    raise
                if markers is not None:
                    del markers[markerid]
        return _iterencode


def write_lua(path, obj, sort_keys: bool=False):
    make_dirname(path)
    with open(path, 'wt', newline='\n', encoding='utf-8') as f:
        f.write('return ')
        f.write(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=sort_keys, cls=LUAEncoder))


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
    except Exception:  # noqa: BLE001, S110
        pass

def remove_empty(path):
    """
    recursive remove empty folder
    """
    import os
    
    for p, _, _ in list(os.walk(path))[::-1]:
        if len(os.listdir(p)) == 0:
            os.rmdir(p)


def hash_file(file):
    if os.path.exists(file):
        import hashlib
        with open(file, 'rb') as f:
            hash = hashlib.file_digest(f, 'sha1')
        return hash.hexdigest()
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


_VERSION_MANIFEST_PATH = os.path.join('version_manifest.json')
VERSION_MANIFEST = read_json(_VERSION_MANIFEST_PATH, {'latest':{'release': None, 'snapshot': None}, 'versions':[], 'pack_format':{}, 'versioning':{}, 'versions_history':[]})

LATEST_RELEASE = VERSION_MANIFEST.get('latest', {}).get('release')
LATEST_SNAPSHOT = VERSION_MANIFEST.get('latest', {}).get('snapshot')

def update_version_manifest():
    global VERSION_MANIFEST, LATEST_RELEASE, LATEST_SNAPSHOT
    
    edited = not os.path.exists(_VERSION_MANIFEST_PATH)
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
    except Exception:  # noqa: BLE001
        github_manifest = None
    
    if github_manifest:
        if read_version_manifest(github_manifest):
            edited = True
        
        def sub_tree(sub_name):
            edited = False
            for v in github_manifest[sub_name]:
                i = VERSION_MANIFEST[sub_name]
                ni = github_manifest[sub_name]
                if isinstance(i[v], list):
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
        write_json(_VERSION_MANIFEST_PATH, VERSION_MANIFEST)
        print('INFO: version_manifest.json has been updated')
    
    VERSION_MANIFEST = read_json(_VERSION_MANIFEST_PATH)
    LATEST_RELEASE = VERSION_MANIFEST.get('latest', {}).get('release')
    LATEST_SNAPSHOT = VERSION_MANIFEST.get('latest', {}).get('snapshot')

def update_pack_format(path_version_json, version):
    global VERSION_MANIFEST  # noqa: PLW0602
    
    if not os.path.exists(path_version_json):
        return
    
    edited = False
    pack_version = read_json(path_version_json).get("pack_version", {})
    pack_format = VERSION_MANIFEST['pack_format']
    if isinstance(pack_version, int):
        pack_version = {"resource": pack_version}
    for k,v in tuple(pack_version.items()):
        if k.endswith('_major'):
            k = k.removesuffix('_major')
            pack_version[k] = eval(f'{pack_version.pop(k+'_major')}.{pack_version.pop(k+'_minor')}')
    for k,v in pack_version.items():
        v = str(v)
        if k not in pack_format:
            pack_format[k] = {}
        if v not in pack_format[k]:
            pack_format[k][v] = []
        if version not in pack_format[k][v]:
            pack_format[k][v].insert(0, version)
            edited = True
    
    if edited:
        def key_sort(entry):
            return tuple(map(int, entry[0].split('.')))
        VERSION_MANIFEST['pack_format'] = dict(sorted(
            (k, dict(sorted(v.items(), key=key_sort, reverse=True))) for k,v in pack_format.items()
        ))
        write_json(_VERSION_MANIFEST_PATH, VERSION_MANIFEST)
        print("INFO: 'pack_format' in version_manifest.json has been updated")

CALENDAR_VERSION = re.compile(r'^(\d{2}\.\d)(\.\d)?(?:-([\w\-]+)-\d+)?$')

def update_calendar_versioning(version):
    if not (match_id := CALENDAR_VERSION.match(version)):
        print(f'The version {version!r} is not a calendar format.')
        return False
    global VERSION_MANIFEST  # noqa: PLW0602
    
    version_id = match_id.group(0)
    version = match_id.group(1)
    
    version_dic = VERSION_MANIFEST['versioning'].get(version)
    if not version_dic:
        print(f'Appending {version!r} to versioning data.')
        version_dic = {
            "snapshots": [],
            "pre-releases": [],
            "releases-candidate": [],
            "releases": [],
        }
        new_val = {version: version_dic}
        new_val.update(VERSION_MANIFEST['versioning'].items())
        VERSION_MANIFEST['versioning'] = new_val
    
    type_map = {
        'snapshot': 'snapshots',
        'pre': 'pre-releases',
        'rc': 'releases-candidate',
        None: 'releases',
    }
    if not (type_added := type_map.get(match_id.group(3))):
        print(f'The version {version!r} is of a unknow type.')
        return False
    
    type_lst = version_dic.get(type_added)
    if not isinstance(type_lst, list):
        version_dic[type_added] = type_lst = []
    
    if version_id in type_lst:
        return True
    
    type_lst.insert(0, version_id)
    
    write_json(_VERSION_MANIFEST_PATH, VERSION_MANIFEST)
    print("INFO: 'versioning' in version_manifest.json has been updated")
    return True

def version_path(version):
    for k,v in VERSION_MANIFEST['versioning'].items():
        if isinstance(v, list):
            if version in v:
                return os.path.join(k, version)
        else:
            if version in v.get('releases', []):
                return os.path.join('releases', version)
            
            for kk,vv in v.items():
                if version in vv:
                    return os.path.join('snapshots', k, kk, version)
    
    return version

def version_developement(version):
    # get the version cycle of a snapshot
    for k,v in VERSION_MANIFEST['versioning'].items():
        if isinstance(v, list):
            if version in v:
                return version, k
        else:
            if version in v.get('releases', []):
                return version, None
            
            for vv in v.values():
                if version in vv:
                    return k, version
    
    return version, None

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
            if v['id'] == version and v['url']:
                return version
        
        
        print(f'The version {version} has invalide.', '' if quiet else ' Press any key to exit.')
        if not quiet:
            input()
        sys.exit()

def valide_output(args):
    if args.output and os.path.exists(args.output):
        print(f'The {args.version} already exit at "{args.output}".', 'This output will be overwrited.' if args.overwrite else '' if args.quiet else 'Do you want overwrite them?')
        if (args.quiet and args.overwrite) or input()[:1] == 'y':
            args.overwrite = True
        else:
            sys.exit()


def read_manifest_json(temp, version, manifest_json_path = None):
    import zipfile
    
    manifest_url = None
    for v in VERSION_MANIFEST['versions']:
        if v['id'] == version and v['url']:
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


def serialize_nbt(file, output_file=None):
    from nbtlib import nbt
    from nbtlib.literal.serializer import serialize_tag
    
    snbt = serialize_tag(nbt.load(file), indent=2, compact=False, quote='"').replace('\r\n', '\n').replace('\r', '\n')
    while ' \n' in snbt:
        snbt = snbt.replace(' \n', '\n')
    
    if not output_file:
        output_file = os.path.splitext(file)[0]+'.snbt'
    write_text(output_file, snbt)


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
