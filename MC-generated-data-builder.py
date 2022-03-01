VERSION = (0, 1, 0)

def as_bytes(x, encoding="utf-8"):
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

def as_unicode(x, encoding="utf-8", errors="strict"):
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
    stream = kw.get("file", sys.stdout)
    if stream is None:
        return
    sep, end = kw.get("sep"), kw.get("end")
    if sep is None:
        sep = " "
    if end is None:
        end = "\n"
    if is_binary(stream):
        encoding = getattr(stream, "encoding", None) or "utf-8"
        a = (as_bytes(x, encoding=encoding) for x in a)
        sep = as_bytes(sep)
        end = as_bytes(end)
    else:
        a = (as_unicode(x, errors="replace") for x in a)
        sep = as_unicode(sep)
        end = as_unicode(end)
    for i, x in enumerate(a):
        #if sep and i != 0:
        #    stream.write(sep)
        stream.write(x)
    if end:
        stream.write(end)
    if kw.get("flush"):
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
            prints("Missing dependency")
            first_missing = False
        prints("Instaling: ", package)
        subprocess.check_call([sys.executable, "-m", "pip", "-q", "install", package])


import sys, argparse, os.path, json, io, glob
import pathlib, tempfile, urllib.request, datetime, subprocess, zipfile, shutil
from collections import OrderedDict

install("keyboard")
import keyboard


parser = argparse.ArgumentParser()
parser.add_argument('-v', '--version', help='Target version ; the version must be installed.\nr or release for the last release\ns or snapshot for the last snapshot')
parser.add_argument('-z', '--zip', help='Empack the folder in a zip after its creation', action='store_true')
parser.add_argument('-q', '--quiet', help='JSON manifest of the target version', action='store_true')
parser.add_argument('--manifest-json', help='JSON manifest of the target version', type=pathlib.Path)

args = parser.parse_args()

class GitHub:
    def __init__(self, user, repository):
        self.user = user
        self.repository = repository
        self.url = "https://github.com/" + self.user + "/" + self.repository + "/releases"
        self.api = "https://api.github.com/repos/" + self.user + "/" + self.repository + "/releases"
        self.raw = "https://raw.githubusercontent.com/" + self.user + "/" + self.repository
    
    def api_zip(self, tag):
        return self.api + "/" + tag
    
    def html_release(self, tag):
        return self.url + "/tag/" + tag
    
    def get_raw(self, branche_tag, file):
        return self.raw + "/" + branche_tag + "/" + file.replace('\\','/')
    
    def check_versions(self):
        '''return <latest: tuple>, <versions: list>, <versions_info: dict>'''
        versions_info = {}
        with urllib.request.urlopen(self.api) as fl:
            for item in json.load(fl):
                tag = item["tag_name"]
                versions_info[tuple(tag.split('.', 3))] = item
        
        versions = [ v[0] for v in sorted(versions_info.items(), key=lambda item : item[1]["id"])]
        return versions[-1] if len(versions) else None, versions, versions_info

if not first_missing:
    prints("All dependency are instaled")
    prints()

github_data = GitHub("un-pogaz", "MC-generated-data")
github_builder = GitHub("un-pogaz", "MC-generated-data-builder")

def main():
    global args, temp
    
    last, _, _ = github_builder.check_versions()
    
    prints(f"--==| Minecraft: Generated data builder {VERSION} |==--")
    prints()
    
    temp = os.path.join(tempfile.gettempdir(), "MC Generated data")
    if not os.path.exists(temp):
        os.makedirs(temp)
    
    
    if True: ## update version_manifest
        version_manifest_path = os.path.join("version_manifest.json")
        version_manifest = json_read(version_manifest_path, { "latest":{"release": None, "snapshot": None}, "versions":[], "paths":{}, "versioning":{}})
        
        edited = False
        def update_version_manifest(read_manifest):
            edited = False
            if version_manifest["latest"]["release"] != read_manifest["latest"]["release"]:
                version_manifest["latest"]["release"] = read_manifest["latest"]["release"]
                edited = True
            
            if version_manifest["latest"]["snapshot"] != read_manifest["latest"]["snapshot"]:
                version_manifest["latest"]["snapshot"] = read_manifest["latest"]["snapshot"]
                edited = True
            
            versions = { v["id"]:v for v in version_manifest["versions"] }
            
            for k,v in { v["id"]:v for v in read_manifest["versions"] }.items():
                if "sha1" in v: del v["sha1"]
                if "complianceLevel" in v: del v["complianceLevel"]
                
                if k not in versions:
                    versions[k] = v
                    edited = True
            
            version_manifest["versions"] = versions.values()
            
            return edited
        
        with urllib.request.urlopen(github_data.get_raw("main", "version_manifest.json")) as fl:
            github_manifest = json.load(fl)
            
            if update_version_manifest(github_manifest):
                edited = True
            
            for k in github_manifest["paths"]:
                if k not in version_manifest["paths"]:
                    version_manifest["paths"][k] = github_manifest["paths"][k]
                    edited = True
            
            for v in github_manifest["versioning"]:
                i = version_manifest["versioning"]
                ni = github_manifest["versioning"]
                if v == "special":
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
        
        with urllib.request.urlopen("https://launchermeta.mojang.com/mc/game/version_manifest_v2.json") as fl:
            if update_version_manifest(json.load(fl)):
                edited = True
        
        if edited:
            version_manifest["versions"] = sorted(version_manifest["versions"], key=lambda item: item["releaseTime"], reverse=True)
            json_write(version_manifest_path, version_manifest)
    
    
    if args.manifest_json:
        args.version = json_read(args.manifest_json, {"id": None})["id"]
    
    else:
        if not args.version:
            prints("Enter the version:")
            args.version = input()
        
        if args.version in ['r','release','s','snapshot']:
            pass
        
        for v in version_manifest["versions"]:
            if v["id"] == args.version:
                version_json = v
                break
    
        if not version_json:
            prints(f"The version {args.version} has invalide. Press any key to exit.")
            keyboard.read_key()
            return -1
    
    
    
    temp = os.path.join(temp, args.version)
    if not os.path.exists(temp):
        os.makedirs(temp)
    
    output = glob.glob(f"**/{args.version}/{args.version}.json", root_dir='.', recursive=True)
    if len(output):
        output = output[0]
    else:
        output = None
    
    if output:
        prints(f'The {args.version} already exit at "{output}". Do you want overide them?')
        if input()[:1] == "y":
            prints()
        else:
            return -1
    
    
    manifest = os.path.join(temp, "generated")
    if not os.path.exists(manifest):
        os.makedirs(manifest)
    manifest = os.path.join(manifest, args.version+".json")
    
    
    manifest_url = None
    for v in version_manifest["versions"]:
        if v["id"] == args.version:
            manifest_url = v["url"]
            break
    
    if not args.manifest_json:
        urllib.request.urlretrieve(manifest_url, manifest)
    else:
        manifest = args.manifest_json
    
    manifest_json = json_read(manifest)
    
    version_json = OrderedDict()
    version_json["id"] = manifest_json["id"]
    version_json["type"] = manifest_json["type"]
    version_json["time"] = manifest_json["time"]
    version_json["releaseTime"] = manifest_json["releaseTime"]
    version_json["url"] = manifest_url
    version_json["asset"] = manifest_json["assetIndex"]["id"]
    version_json["asset_url"] = manifest_json["assetIndex"]["url"]
    version_json["client"] = manifest_json["downloads"]["client"]["url"]
    version_json["client_mappings"] = manifest_json["downloads"]["client_mappings"]["url"]
    version_json["server"] = manifest_json["downloads"]["server"]["url"]
    version_json["server_mappings"] = manifest_json["downloads"]["server_mappings"]["url"]
    
    json_write(manifest, version_json)
    
    output = index["paths"][args.version] or os.path.join(version_json["type"], args.version)
    
    
    fix = datetime.datetime.fromisoformat("2021-09-21T14:36:06+00:00")
    dt = datetime.datetime.fromisoformat(version_json["releaseTime"])
    
    cmd = "-DbundlerMainClass=net.minecraft.data.Main -jar server.jar --all"
    if dt < fix:
        cmd = "-cp server.jar net.minecraft.data.Main --all"
    
    prints()
    
    client = os.path.join(temp, "client.jar")
    if not os.path.exists(client):
        prints(f"Downloading client.jar...")
        urllib.request.urlretrieve(version_json["client"], client)
    
    server = os.path.join(temp, "server.jar")
    if not os.path.exists(server):
        prints(f"Downloading server.jar...")
        urllib.request.urlretrieve(version_json["server"], server)
    
    prints(f"Extracting data server...")
    subprocess.run("java " + cmd, cwd=temp, shell=False, capture_output=False, stdout=subprocess.DEVNULL)
    
    prints(f"Extracting data client...")
    with zipfile.ZipFile(client, mode='r') as zip:
        for entry in zip.filelist:
            if entry.filename.startswith("assets/") or entry.filename.startswith("data/"):
                safe_del(temp, [os.path.join("generated", entry.filename)])
                zip.extract(entry.filename, os.path.join(temp, "generated"))
    
    safe_del(temp, ["libraries", "logs", "versions",
            "generated/.cache", "generated/assets/.mcassetsroot", "generated/data/.mcassetsroot"])
    
    prints("Listing elements and various...")
    
    def enum_json(dir):
        return [j[:-5].replace('\\', '/') for j in glob.glob(f"**/*.json", root_dir=dir, recursive=True)]
    
    for k,v in json_read(os.path.join(temp, "generated/reports/registries.json")).items():
        name = k.split(':', maxsplit=2)[-1]
        
        tags = os.path.join(temp,"generated/data/minecraft/tags", name)
        if not os.path.exists(tags):
            tags = tags + "s"
        
        entries = [k for k in v["entries"].keys()]
        tags = ['#minecraft:'+j for j in enum_json(tags)]
        write_lines(os.path.join(temp, "generated/lists/registries", name +".txt"), entries + tags)
    
    for dir in os.scandir(os.path.join(temp, "generated/reports/worldgen/minecraft/worldgen")):
        if dir.is_dir:
            folder = ['minecraft:'+j for j in enum_json(dir.path)]
            tags = ['#minecraft:'+j for j in enum_json(os.path.join(temp,"generated/data/minecraft/tags/worldgen", dir.name))]
            write_lines(os.path.join(temp, "generated/lists/worldgen", dir.name +".txt"), folder + tags)
    
    #shutil.move(src, dst)
    
    prints()
    prints("Work done. Press any key to exit.")
    keyboard.read_key()
    return 0


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


def safe_del(temp, paths):
    def remove(a):
        pass
    
    for path in paths:
        path = os.path.join(temp, path)
        if os.path.exists(path):
            if os.path.isfile(path):
                remove = os.remove
            else:
                remove = shutil.rmtree
        
        try:
            remove(path)
        except Exception as ex:
            pass












if __name__ == "__main__":
    
    main()