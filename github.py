class GitHub:
    def __init__(self, user, repository):
        self.user = user
        self.repository = repository
        self.url = 'https://github.com/' + self.user + '/' + self.repository + '/releases'
        self.api = 'https://api.github.com/repos/' + self.user + '/' + self.repository + '/releases'
        self.raw = 'https://raw.githubusercontent.com/' + self.user + '/' + self.repository
    
    def api_zip(self, tag):
        return self.api + '/' + tag
    
    def html_release(self, tag):
        return self.url + '/tag/' + tag
    
    def get_raw(self, branche_tag, file):
        return self.raw + '/' + branche_tag + '/' + file.replace('\\','/')
    
    def check_versions(self):
        '''return <latest: tuple>, <versions: list>, <versions_info: dict>'''
        versions_info = {}
        with urllib.request.urlopen(self.api) as fl:
            for item in json.load(fl):
                tag = item['tag_name']
                
                for v in tag.split('.', 4):
                    pass
                
                versions_info[tuple(intTryParse(v)[0] for v in tag.split('.', 4))] = item
        
        versions = [ v[0] for v in sorted(versions_info.items(), key=lambda item : item[1]['id'])]
        return versions[-1], versions, versions_info

def intTryParse(value, default=None):
    try:
        return int(value), True
    except ValueError:
        return default if default else value, False
