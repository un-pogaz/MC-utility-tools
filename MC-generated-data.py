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
parser.add_argument('-v', '--version', help='Target version ; the version must be installed')
parser.add_argument('-z', '--zip', help='Empack the folder in a zip after its creation', action='store_true')
parser.add_argument('--minecraft-path', help='Minecraft directory path', type=pathlib.Path)
parser.add_argument('--manifest-json', help='JSON manifest of the target version', type=pathlib.Path)

args = parser.parse_args()

if not first_missing:
    prints("All dependency are instaled")
    prints()

def main():
    global args
    
    prints("--==| Minecraft: Generated data helper |==--")
    prints()
    
    temp = os.path.join(tempfile.gettempdir(), "MC Generated data")
    if not os.path.exists(temp):
        os.makedirs(temp)
    
    try:
        index = json_read("index.json")
    except:
        index = {"latest":{"release": "", "snapshot": ""}, "paths":{}, "versions":{}}
    
    with urllib.request.urlopen("https://raw.githubusercontent.com/un-pogaz/MC-generated-data/main/index.json") as fl:
        new_index = json.load(fl)
    
    edited = False
    if index["latest"]["release"] != new_index["latest"]["release"]:
        index["latest"]["release"] = new_index["latest"]["release"]
        edited = True
    
    if index["latest"]["snapshot"] != new_index["latest"]["snapshot"]:
        index["latest"]["snapshot"] = new_index["latest"]["snapshot"]
        edited = True
    
    for k in reversed(new_index["paths"]):
        if k not in index["paths"]:
            index["paths"][k] = new_index["paths"][k]
            edited = True
    
    for v in new_index["versions"]:
        i = index["versions"]
        if v == "special":
            if v not in i:
                i[v] = []
                edited = True
            
            iv = i[v]
            for idx, e in enumerate(new_index["versions"][v], start=0):
                if e not in iv:
                    iv.insert(idx, e)
                    edited = True
            
        else:
            if v not in i:
                i[v] = {}
                edited = True
            
            iv = i[v]
            for t in new_index["versions"][v]:
                if t not in iv:
                    iv[t] = []
                    edited = True
                
                ivt = iv[t]
                for idx, e in enumerate(new_index["versions"][v][t], start=0):
                    if e not in ivt:
                        ivt.insert(idx, e)
                        edited = True
    
    if edited:
        json_write("index.json", index)
    
    if not args.manifest_json:
        ## update version_manifest
        
        if not args.minecraft_path:
            args.minecraft_path = os.path.join(os.getenv("APPDATA"), ".minecraft")
        
        minecraft_manifest = os.path.join(args.minecraft_path, "versions", "version_manifest_v2.json")
        
        if not os.path.exists(minecraft_manifest):
            prints(f'The minecraft_path "{args.minecraft_path}" dosen\'t containt "versions/version_manifest_v2.json". Press any key to exit.')
            keyboard.read_key()
            return -1
        
        minecraft_manifest = json_read(minecraft_manifest)
        
        version_manifest = os.path.join("version_manifest.json")
        try:
            manifest_json = json_read(version_manifest)
        except:
            manifest_json = { "latest":{"release": None, "snapshot": None}, "versions":[] }
        
        edited = False
        
        if manifest_json["latest"]["release"] != minecraft_manifest["latest"]["release"]:
            manifest_json["latest"]["release"] = minecraft_manifest["latest"]["release"]
            edited = True
        
        if manifest_json["latest"]["snapshot"] != minecraft_manifest["latest"]["snapshot"]:
            manifest_json["latest"]["snapshot"] = minecraft_manifest["latest"]["snapshot"]
            edited = True
        
        versions = { v["id"]:v for v in manifest_json["versions"] }
        
        for k,v in { v["id"]:v for v in minecraft_manifest["versions"] }.items():
            del v["sha1"]
            del v["complianceLevel"]
        
            if k not in versions:
                versions[k] = v
                edited = True
        
        if edited:
            manifest_json["versions"] = sorted(versions.values(), key=lambda item: item["releaseTime"], reverse=True)
            json_write(version_manifest, manifest_json)
        
        ##end update version_manifest
        
        ##
        
        if not args.version:
            prints("Enter the version:")
            args.version = input()
        
        version_json = None
        for v in manifest_json["versions"]:
            if v["id"] == args.version:
                version_json = v
                break
            
        if not version_json:
            prints(f"The version {args.version} has invalide. Press any key to exit.")
            keyboard.read_key()
            return -1
    
    
    if args.manifest_json:
        manifest_json = json_read(args.manifest_json)
        args.version = manifest_json["id"]
    
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
    if not args.manifest_json:
        manifest_url = version_json["url"]
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
        write_lines(os.path.join(temp, "generated/list/registries", name +".txt"), entries + tags)
    
    for dir in os.scandir(os.path.join(temp, "generated/reports/worldgen/minecraft/worldgen")):
        if dir.is_dir:
            folder = ['minecraft:'+j for j in enum_json(dir.path)]
            tags = ['#minecraft:'+j for j in enum_json(os.path.join(temp,"generated/data/minecraft/tags", dir.name))]
            write_lines(os.path.join(temp, "generated/list/worldgen", dir.name +".txt"), folder + tags)
    
    
    #def Worldgen(name)
    #
    #    static void Worldgen(string temp, string name)
    #    {
    #        string dir = Path.Combine(temp, "generated", "list", "worldgen");
    #        Directory.CreateDirectory(dir);
    #        using (StreamWriter writer = new StreamWriter(Path.Combine(dir, name) + ".txt", false, UTF8SansBomEncoding.UTF8SansBom))
    #        {
    #            foreach (var item in EnumerateJsonName(temp, Path.Combine("reports/worldgen/minecraft/worldgen", name)))
    #                writer.WriteLine("minecraft:" + item);
    #            foreach (var item in EnumerateJsonName(temp, Path.Combine("data/minecraft/tags/worldgen", name)))
    #                writer.WriteLine("#minecraft:" + item);
    #        }
    #    }
    #
    #shutil.move(src, dst)
    
    prints("Work done. Press any key to exit.")
    keyboard.read_key()
    return 0


def json_read(path):
    with open(path, 'r') as f:
        return json.load(f)

def json_write(path, obj):
    with open(path, 'w',) as f:
        json.dump(obj, f, indent=2)

def write_lines(path, lines):
    dir = os.path.dirname(path)
    if dir and not os.path.exists(dir):
        os.makedirs(dir)
    with open(path, 'w') as f:
        f.writelines(l+'\n' for l in lines)


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