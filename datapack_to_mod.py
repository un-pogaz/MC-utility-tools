import os
import glob
import unicodedata
import re
import zipfile
from tempfile import gettempdir

from common import read_json, safe_del

temp = os.path.join(gettempdir(), 'package_datapack_to_mod')

def slugify(value, allow_unicode=False):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '_', value).strip('_')


forge = """modLoader = "javafml"
loaderVersion = "[25,)"
license = "Unknow"
showAsResourcePack = true

[[mods]]
modId = "{id}_pdpm"
version = "1-mcmeta-{mcmeta}"
displayName = "{name}"
description = "{description}"
logoFile = "{id}_pack.png"
credits = "Generated by MC-utility-tools"
authors = "un-pogaz"
"""

neoforge = """
modLoader = 'javafml'
loaderVersion = '[1,)'
license = 'Unknow'
showAsResourcePack = false
[[mods]]
modId = "{id}_pdpm"
version = "1-mcmeta-{mcmeta}"
displayName = "{name}"
description = "{description}"
logoFile = "{id}_pack.png"
credits = "Generated by MC-utility-tools"
authors = "un-pogaz"
"""

forge_class = [
    b"\xca\xfe\xba\xbe\x00\x00\x004\x00\x14\x01\x00%net/pdpm/",
    b"/pdpmWrapper\x07\x00\x01\x01\x00\x10java/lang/Object\x07\x00\x03\x01\x00\x14pdpmWrapper.java\x01\x00#Lnet/minecraftforge/fml/common/Mod;\x01\x00\x05value\x01\x00\x0b",
    b"_pdpm\x01\x00\x06<init>\x01\x00\x03()V\x0c\x00\t\x00\n\n\x00\x04\x00\x0b\x01\x00\x04this\x01\x00'Lcom/pdpm/wrappera/pdpmWrapper;\x01\x00\x04Code\x01\x00\x0fLineNumberTable\x01\x00\x12LocalVariableTable\x01\x00\nSourceFile\x01\x00\x19RuntimeVisibleAnnotations\x00!\x00\x02\x00\x04\x00\x00\x00\x00\x00\x01\x00\x01\x00\t\x00\n\x00\x01\x00\x0f\x00\x00\x00/\x00\x01\x00\x01\x00\x00\x00\x05*\xb7\x00\x0c\xb1\x00\x00\x00\x02\x00\x10\x00\x00\x00\x06\x00\x01\x00\x00\x00\x06\x00\x11\x00\x00\x00\x0c\x00\x01\x00\x00\x00\x05\x00\r\x00\x0e\x00\x00\x00\x02\x00\x12\x00\x00\x00\x02\x00\x05\x00\x13\x00\x00\x00\x0b\x00\x01\x00\x06\x00\x01\x00\x07s\x00\x08",
]

fabric = """{{"schemaVersion":1,"id":"{id}_pdpm","version":"1-mcmeta-{mcmeta}","name":"{name}","description":"{description}","license":"Unknow","icon":"{id}_pack.png","environment":"*","depends":{{"fabric-resource-loader-v0":"*"}}}}"""

quilt = """{{"schema_version":1,"quilt_loader":{{"group": "net.pdpm","id":"{id}_pdpm","version":"1-mcmeta-{mcmeta}","metadata":{{"name":"{name}","description":"{description}","icon":"{id}_pack.png"}},"intermediate_mappings":"net.fabricmc:intermediary","depends":[{{"id":"quilt_resource_loader","versions":"*","unless":"fabric-resource-loader-v0"}}]}}}}"""

def package_datapack(path):
    safe_del(temp)
    safe_del(temp+'.zip')
    os.makedirs(temp, exist_ok=True)
    path = os.path.abspath(path)
    
    if not os.path.exists(path):
        print("Target path don't exist.")
        return None
    
    if os.path.isdir(path):
        is_folder = True
        name = os.path.basename(path)
        _path_jar = os.path.join(path, name)+'.jar'
        _path_zip = os.path.join(path, name)+'.zip'
        update_jar = False
        if os.path.exists(_path_jar) or os.path.exists(_path_zip):
            print('The target folder already have a mod/zip with the same name.')
            print('Do you want update this one?')
            update_jar = input().lower().startswith('y')
        
        if update_jar:
            path_jar = _path_jar
            path_zip = _path_zip
        else:
            path_jar = os.path.abspath(path)+'.jar'
            path_zip = os.path.abspath(path)+'.zip'
        
    else:
        is_folder = False
        update_jar = False
        name = os.path.splitext(os.path.basename(path))[0]
        path_jar = os.path.splitext(path)[0]+'.jar'
        path_zip = os.path.splitext(path)[0]+'.zip'
    
    if (
        is_folder and not update_jar and (os.path.exists(path_jar) or os.path.exists(path_zip))
        ) or (
        not is_folder and os.path.exists(path_jar)
        ):
        print('Error: packaged Datapack already exist {!r}'.format(os.path.basename(path_jar)))
        return None
    
    id = slugify(name)
    id = re.sub(r'^([0-9])',r'n\1', id)
    id = re.sub(r'^([^\w])',r'a\1', id)
    
    if is_folder:
        print('Building zip...')
        with zipfile.ZipFile(path_zip, mode='w') as zip:
            for f in glob.iglob('**/*', recursive=True, root_dir=path):
                if f.lower().endswith(('.zip', '.jar')):
                    continue
                if not os.path.isfile(os.path.join(path, f)):
                    continue
                zip.write(os.path.join(path, f), f)
    
    print('Writing metadata...')
    try:
        j = read_json(os.path.join(path, 'pack.mcmeta'))
        mcmeta = j['pack']['pack_format']
        range_formats = j['pack'].get('supported_formats')
        if isinstance(range_formats, dict):
            range_formats = [range_formats['min_inclusive'], range_formats['max_inclusive']]
        if isinstance(range_formats, list):
            mcmeta = f'{range_formats[0]}-{range_formats[1]}'
        description = j['pack'].get('description', '')
        if isinstance(description, list):
            for i in range(len(description)):
                if isinstance(description[i], dict):
                    description[i] = description[i].get('text', '')
            
            description = ''.join(description).replace('\r\n','\n')
        
    except Exception:
        print('Error: invalide Datapack')
        return None
    
    with open(path_zip, 'rb') as fi:
        with open(path_jar, 'wb') as fo:
            while (b := fi.read(2**16)):
                fo.write(b)
    
    map = {'id': id, 'mcmeta': mcmeta, 'name': name, 'description': description.replace('\n', '\\n').replace('"', '\\"')}
    
    with zipfile.ZipFile(path_jar, mode='a') as zip:
        if 'pack.png' in zip.namelist():
            zip.writestr(f'{id}_pack.png', zip.open('pack.png').read())
        zip.writestr('META-INF/mods.toml', forge.format(**map))
        zip.writestr('META-INF/neoforge.mods.toml', neoforge.format(**map))
        zip.writestr('fabric.mod.json', fabric.format(**map))
        zip.writestr('quilt.mod.json', quilt.format(**map))
        # fc = id.encode('utf-8').join(forge_class)
        # zip.writestr(f'net/pdpm/{id}/pdpmWrapper.class', fc)


if __name__ == "__main__":
    import sys
    
    print('{|[ Package Datapack to mod ]|}')
    args = sys.argv[1:]
    if args:
        for a in args:
            print('>> '+os.path.basename(a))
            package_datapack(a)
            print()
    
    else:
        while True:
            print('Enter a Datapack (folder or zip) to package:')
            print('(Enter empty value to quit)')
            a = input().strip().strip('"')
            if not a:
                exit()
            package_datapack(a)
            print()
