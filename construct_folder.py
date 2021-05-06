import os
from collections import defaultdict

import configparser
import json

from shutil import copyfile
from networks import prefix, headers, get_last_modified_version, download_lists, list_to_dict
from backend import *

parser = configparser.ConfigParser()
parser.read('zotsyncfolder.conf')
config = parser['DEFAULT']

user_id = config['user_id']
api_key = config['api_key']
json_folder = config['json_folder']
output_folder = config['output_folder']
zotero_folder = config['zotero_folder']
target_ext_list = config['target_ext_list']
load_from_cache = config.getboolean('load_from_cache')


print('기본 메타데이터들 저장')
global_metadata_json = f'{json_folder}/global_metadata.json'
if load_from_cache:
    global_metadata = json.load(open(global_metadata_json, 'r'))
else:
    global_metadata = dict()
    global_metadata['last_modified_version'] = get_last_modified_version()
    os.makedirs(json_folder, exist_ok=True)
    f = open(global_metadata_json, 'w')
    print(json.dumps(global_metadata, indent=4), file=f)
    f.close()


print('모든 Collection 정보를 받아서, collection_key: real_path 형태로 저장')
collection_metadatas_json = f'{json_folder}/collection_metadatas.json'
if load_from_cache:
    collection_metadatas = json.load(open(collection_metadatas_json, 'r'))
else:
    collection_metadatas = defaultdict(dict)
    collections = list_to_dict(download_lists(f"{prefix}/collections", headers))
    collection_key_tree = build_key_tree(collections)
    set_collection_metadata(collection_key_tree, collections, output_folder, collection_metadatas)
    f = open(collection_metadatas_json, 'w')
    print(json.dumps(collection_metadatas, indent=4), file=f)
    f.close()

print('모든 item 정보를 받아서, collection_key: [file_name] 형태로 저장')
item_metadatas_json = f'{json_folder}/item_metadatas.json'
if load_from_cache:
    item_metadatas = json.load(open(item_metadatas_json, 'r'))
else:
    item_metadatas = defaultdict(lambda: defaultdict(list))
    items = list_to_dict(download_lists(f"{prefix}/items", headers))
    for item in items.values():
        if is_real_item(item):
            item_key = item['key']
            item_metadatas[item_key]['key'] = item['key']
            item_metadatas[item_key]['version'] = item['version']
            item_metadatas[item_key]['collections'] = item['data']['collections']
        elif is_real_attachment(item, target_ext_list):
            attachment_key = item['key']
            parent_key = item['data']['parentItem']
            item_metadatas[attachment_key]['key'] = item['key']
            item_metadatas[attachment_key]['version'] = item['version']
            item_metadatas[attachment_key]['filename'] = item["data"]['filename']
            item_metadatas[attachment_key]['md5'] = item["data"]['md5']
            item_metadatas[parent_key]['attachment_keys'].append(item['key'])
        else:
            pass

    f = open(item_metadatas_json, 'w')
    print(json.dumps(item_metadatas, indent=4), file=f)
    f.close()

print('Collection의 real_path에 따라 폴더 생성')
for collection_key, collection_metadata in collection_metadatas.items():
    os.makedirs(collection_metadata['zsf_full_path'], exist_ok=True)

print('Zotero 원본 데이터 폴더에서 각 collection 폴더로 item 실제 파일(pdf) 복사')
for item_key, item_metadata in item_metadatas.items():
    if 'attachment_keys' in item_metadata:
        for attachment_key in item_metadata['attachment_keys']:
            attachment = item_metadatas[attachment_key]
            original_file_path = generate_original_file_path(zotero_folder, attachment)

            if not os.path.exists(original_file_path):
                print(f'원 폴더에 {original_file_path} 없음;;')
                continue

            if 'key' not in item_metadata:
                print(f'이상한 부모 {item_key}를 갖고 있는 {attachment_key}!')
                continue

            for collection_key in item_metadata['collections']:
                collection = collection_metadatas[collection_key]
                new_file_path = generate_new_file_path(collection, attachment)
                copyfile(original_file_path, new_file_path)

                # TODO: attachment가 여러 collection에 있을 경우에 파일 시각 처리
                attachment['original_modified'] = os.path.getmtime(original_file_path)
                attachment['new_modified'] = os.path.getmtime(new_file_path)


f = open(item_metadatas_json, 'w')
print(json.dumps(item_metadatas, indent=4), file=f)
f.close()

print('done')
