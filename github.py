
class GitHub:
    def __init__(self, user, repository):
        self.user = user
        self.repository = repository
        self.url = 'https://github.com/' + self.user + '/' + self.repository
        self.api = 'https://api.github.com/repos/' + self.user + '/' + self.repository
        self.raw = 'https://raw.githubusercontent.com/' + self.user + '/' + self.repository
    
    def get_json(self, url):
        import json
        from urllib import request
        with request.urlopen(url) as fl:
            return json.load(fl)
    
    def releases(self, tag=None):
        if not tag:
            return self.get_json(self.api + '/releases')
        else:
            for rslt in self.releases():
                if rslt['tag_name'] == tag:
                    return rslt
    
    def tags(self, tag=None):
        if not tag:
            return self.get_json(self.api + '/tags')
        else:
            for rslt in self.releases():
                if rslt['name'] == tag:
                    return rslt
    
    def html_release(self, tag=None):
        if not tag:
            return self.url + '/releases'
        else:
            return self.html_release() +'/tag/' + tag
    
    def get_raw(self, branche_tag, file):
        return self.raw + '/' + branche_tag + '/' + file.replace('\\','/')
    
    def check_releases(self):
        '''return <latest: tuple>, <versions: list>, <versions_info: dict>'''
        versions_info = {}
        json = self.releases()
        if len(json):
            for item in json:
                tag = item['tag_name']
                versions_info[tuple(intTryParse(v)[0] for v in tag.split('.', 4))] = item
            
            versions = [ v[0] for v in sorted(versions_info.items(), key=lambda item : item[1]['id'])]
            return versions[-1], versions, versions_info
        
        else:
            return None, [], {}
    
    def check_tags(self):
        '''return <latest: tuple>, <tags: list>, <tags_info: dict>'''
        tags_info = {}
        json = self.tags()
        if len(json):
            for item in json:
                tag = item['name']
                tags_info[tuple(intTryParse(v)[0] for v in tag.split('.', 4))] = item
            
            tags = [ v[0] for v in sorted(tags_info.items())]
            return tags[-1], tags, tags_info
        
        else:
            return None, [], {}

def intTryParse(value, default=None):
    try:
        return int(value), True
    except ValueError:
        return default if default else value, False
