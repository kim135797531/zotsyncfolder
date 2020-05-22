import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry

import configparser


parser = configparser.ConfigParser()
parser.read('zotsyncfolder.conf')
config = parser['DEFAULT']

user_id = config['user_id']
api_key = config['api_key']
output_folder = config['output_folder']
zotero_folder = config['zotero_folder']

base_url = "https://api.zotero.org"
prefix = f"{base_url}/users/{user_id}"
headers = {
    'Zotero-API-Version': '3',
    'Zotero-API-Key': api_key
}


class TimeoutHTTPAdapter(HTTPAdapter):
    def __init__(self, *args, **kwargs):
        self.timeout = 5
        if "timeout" in kwargs:
            self.timeout = kwargs["timeout"]
            del kwargs["timeout"]
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        timeout = kwargs.get("timeout")
        if timeout is None:
            kwargs["timeout"] = self.timeout
        return super().send(request, **kwargs)


retry_strategy = Retry(total=3, backoff_factor=3)
s = requests.Session()
s.mount("https://", TimeoutHTTPAdapter(timeout=30, max_retries=retry_strategy))


def get_last_modified_version():
    result = s.get(f"{prefix}/collections", headers=headers)
    return int(result.headers['Last-Modified-Version'])


def download(url, headers):
    result = s.get(url, headers=headers)
    return result


def download_lists(url, headers):
    elements = []
    url += '&' if '?' in url else '?'
    url += 'limit=100'
    while True:
        result = s.get(url, headers=headers)
        elements.extend(result.json())
        if 'next' in result.links:
            url = result.links['next']['url']
        else:
            break
    return elements


def list_to_dict(elements):
    element_dict = dict()
    for element in elements:
        element_dict[element['key']] = element

    return element_dict


def upload(url, headers, datas, files=None):
    result = s.post(url, headers=headers, data=datas, files=files)
    return result
